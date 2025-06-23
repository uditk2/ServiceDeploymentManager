import logging
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient
from typing import Dict, Optional, List
import time
import os
from azure.core.exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)

class SpotVMCreator:
    def __init__(self, subscription_id: str, resource_group: str, vnet_resource_group: str, vnet_name: str, subnet_name: str, location: str = "East US"):
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.vnet_resource_group = vnet_resource_group  # Resource group of the virtual network
        self.vnet_name = vnet_name
        self.subnet_name = subnet_name
        self.location = location
        
        # Use managed identity credentials
        self.credential = DefaultAzureCredential()
        
        # Initialize Azure clients
        self.compute_client = ComputeManagementClient(self.credential, subscription_id)
        self.network_client = NetworkManagementClient(self.credential, subscription_id)
        self.resource_client = ResourceManagementClient(self.credential, subscription_id)
    
    def create_spot_vm(self, vm_name: str, vm_size: str = "Standard_B2s", 
                       admin_username: str = "azureuser", ssh_public_key: str = None) -> Dict:
        """
        Create a spot VM and return its configuration including IP address
        """
        try:
            # Check if VM already exists
            if self.vm_exists(vm_name):
                logger.warning(f"VM {vm_name} already exists")
                return self.get_vm_details(vm_name)
            # If no SSH public key provided, fetch from Azure SSH public key resource 'spot_vm_key'
            if not ssh_public_key:
                logger.info("Fetching SSH public key from Azure resource 'spot_vm_key'")
                try:
                    ssh_key_resource = self.compute_client.ssh_public_keys.get(self.resource_group, 'spot_vm_key')
                    ssh_public_key = ssh_key_resource.public_key
                except ResourceNotFoundError:
                    raise ValueError("SSH public key resource 'spot_vm_key' not found in resource group {self.resource_group}")
                except Exception as e:
                    logger.error(f"Error fetching SSH public key: {e}")
                    raise
            
            nic_name = f"{vm_name}-nic"
            
            # Get existing virtual network and subnet
            logger.info(f"Getting existing virtual network: {self.vnet_name} in RG {self.vnet_resource_group}")
            vnet = self.network_client.virtual_networks.get(self.vnet_resource_group, self.vnet_name)
            
            # Find the subnet
            subnet = None
            for subnet_info in vnet.subnets:
                if subnet_info.name == self.subnet_name:
                    subnet = subnet_info
                    break
            
            if not subnet:
                raise ValueError(f"Subnet {self.subnet_name} not found in virtual network {self.vnet_name}")
            
            # Create network interface (without public IP)
            nic_params = {
                'location': self.location,
                'ip_configurations': [{
                    'name': f"{vm_name}-ip-config",
                    'subnet': {'id': subnet.id},
                    'private_ip_allocation_method': 'Dynamic'
                }]
            }
            
            logger.info(f"Creating network interface: {nic_name}")
            nic_result = self.network_client.network_interfaces.begin_create_or_update(
                self.resource_group, nic_name, nic_params
            ).result()
            
            # Create spot VM
            vm_params = {
                'location': self.location,
                'hardware_profile': {'vm_size': vm_size},
                'storage_profile': {
                    'image_reference': {
                        'publisher': 'Canonical',
                        'offer': '0001-com-ubuntu-server-focal',
                        'sku': '20_04-lts-gen2',
                        'version': 'latest'
                    },
                    'os_disk': {
                        'create_option': 'FromImage',
                        'managed_disk': {'storage_account_type': 'Premium_LRS'}
                    }
                },
                'os_profile': {
                    'computer_name': vm_name,
                    'admin_username': admin_username,
                    'disable_password_authentication': True,
                    'linux_configuration': {
                        'ssh': {
                            'public_keys': [{
                                'path': f'/home/{admin_username}/.ssh/authorized_keys',
                                'key_data': ssh_public_key
                            }]
                        }
                    } if ssh_public_key else None
                },
                'network_profile': {
                    'network_interfaces': [{'id': nic_result.id}]
                },
                'priority': 'Spot',
                'eviction_policy': 'Deallocate',
                'billing_profile': {
                    'max_price': -1  # -1 means pay up to on-demand price
                }
            }
            
            logger.info(f"Creating spot VM: {vm_name}")
            vm_result = self.compute_client.virtual_machines.begin_create_or_update(
                self.resource_group, vm_name, vm_params
            ).result()
            
            # Wait for VM to be running and get IP
            self._wait_for_vm_running(vm_name)
            
            # Get the private IP address
            nic_info = self.network_client.network_interfaces.get(
                self.resource_group, nic_name
            )
            private_ip = nic_info.ip_configurations[0].private_ip_address
            
            vm_config = {
                'vm_name': vm_name,
                'vm_id': vm_result.id,
                'resource_group': self.resource_group,
                'location': self.location,
                'vm_size': vm_size,
                'private_ip': private_ip,
                'nic_id': nic_result.id,
                'vnet_name': self.vnet_name,
                'subnet_name': self.subnet_name,
                'status': 'running',
                'created_at': time.time()
            }
            
            logger.info(f"Spot VM created successfully: {vm_name} with private IP: {private_ip}")
            return vm_config
            
        except Exception as e:
            logger.error(f"Error creating spot VM {vm_name}: {str(e)}")
            raise
    
    def vm_exists(self, vm_name: str) -> bool:
        """Check if a VM exists"""
        try:
            self.compute_client.virtual_machines.get(self.resource_group, vm_name)
            return True
        except ResourceNotFoundError:
            return False
        except Exception as e:
            logger.error(f"Error checking if VM {vm_name} exists: {str(e)}")
            return False
    
    def get_vm_status(self, vm_name: str) -> Optional[str]:
        """Get the current status of a VM"""
        try:
            vm_instance_view = self.compute_client.virtual_machines.instance_view(
                self.resource_group, vm_name
            )
            
            # Find the power state
            for status in vm_instance_view.statuses:
                if status.code.startswith('PowerState/'):
                    return status.code.split('/')[-1]
            
            return None
        except ResourceNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Error getting VM status for {vm_name}: {str(e)}")
            return None
    
    def get_vm_details(self, vm_name: str) -> Optional[Dict]:
        """Get detailed information about a VM"""
        try:
            vm = self.compute_client.virtual_machines.get(self.resource_group, vm_name)
            status = self.get_vm_status(vm_name)
            
            # Get network interface details
            nic_id = vm.network_profile.network_interfaces[0].id
            nic_name = nic_id.split('/')[-1]
            nic_info = self.network_client.network_interfaces.get(self.resource_group, nic_name)
            private_ip = nic_info.ip_configurations[0].private_ip_address
            
            return {
                'vm_name': vm_name,
                'vm_id': vm.id,
                'resource_group': self.resource_group,
                'location': vm.location,
                'vm_size': vm.hardware_profile.vm_size,
                'private_ip': private_ip,
                'nic_id': nic_id,
                'vnet_name': self.vnet_name,
                'subnet_name': self.subnet_name,
                'status': status,
                'priority': vm.priority,
                'created_at': time.time()  # This would ideally come from tags or database
            }
        except ResourceNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Error getting VM details for {vm_name}: {str(e)}")
            return None
    
    def start_vm(self, vm_name: str) -> bool:
        """Start a deallocated VM"""
        try:
            logger.info(f"Starting VM: {vm_name}")
            self.compute_client.virtual_machines.begin_start(
                self.resource_group, vm_name
            ).result()
            
            # Wait for VM to be running
            self._wait_for_vm_running(vm_name)
            logger.info(f"VM {vm_name} started successfully")
            return True
        except Exception as e:
            logger.error(f"Error starting VM {vm_name}: {str(e)}")
            return False
    
    def stop_vm(self, vm_name: str) -> bool:
        """Stop (deallocate) a VM"""
        try:
            logger.info(f"Stopping VM: {vm_name}")
            self.compute_client.virtual_machines.begin_deallocate(
                self.resource_group, vm_name
            ).result()
            logger.info(f"VM {vm_name} stopped successfully")
            return True
        except Exception as e:
            logger.error(f"Error stopping VM {vm_name}: {str(e)}")
            return False

    def _wait_for_vm_running(self, vm_name: str, timeout: int = 300):
        """Wait for VM to be in running state"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self.get_vm_status(vm_name)
            if status == 'running':
                logger.info(f"VM {vm_name} is now running")
                return
            
            logger.info(f"Waiting for VM {vm_name} to start... Current status: {status}")
            time.sleep(10)
        
        raise TimeoutError(f"VM {vm_name} did not start within {timeout} seconds")
    
    def get_vm_ip(self, vm_name: str) -> Optional[str]:
        """Get the private IP address of an existing VM"""
        try:
            nic_name = f"{vm_name}-nic"
            nic_info = self.network_client.network_interfaces.get(
                self.resource_group, nic_name
            )
            return nic_info.ip_configurations[0].private_ip_address
        except Exception as e:
            logger.error(f"Error getting IP for VM {vm_name}: {str(e)}")
            return None
    
    def list_user_vms(self, user_prefix: str = None) -> List[Dict]:
        """List all VMs, optionally filtered by user prefix"""
        try:
            vms = []
            for vm in self.compute_client.virtual_machines.list(self.resource_group):
                if user_prefix and not vm.name.startswith(user_prefix):
                    continue
                
                vm_details = self.get_vm_details(vm.name)
                if vm_details:
                    vms.append(vm_details)
            
            return vms
        except Exception as e:
            logger.error(f"Error listing VMs: {str(e)}")
            return []

    def update_workspace_table(self, workspace_id: str, vm_config: Dict):
        """
        Update workspace table with VM configuration
        This method should be implemented based on your database/storage solution
        """
        # TODO: Implement based on your workspace storage (SQL, CosmosDB, etc.)
        logger.info(f"Updating workspace {workspace_id} with VM config: {vm_config}")
        
        # Example implementation for a database update:
        # from your_database_module import WorkspaceRepository
        # workspace_repo = WorkspaceRepository()
        # workspace_repo.update_vm_config(workspace_id, vm_config)
        
        pass
    
    def delete_spot_vm(self, vm_name: str):
        """Delete spot VM and associated resources"""
        try:
            logger.info(f"Deleting VM: {vm_name}")
            
            # Get VM details before deletion to find the OS disk
            vm = self.compute_client.virtual_machines.get(self.resource_group, vm_name)
            os_disk_name = vm.storage_profile.os_disk.name
            
            # Delete the VM
            self.compute_client.virtual_machines.begin_delete(
                self.resource_group, vm_name
            ).wait()
            
            # Delete the OS disk
            try:
                logger.info(f"Deleting OS disk: {os_disk_name}")
                self.compute_client.disks.begin_delete(
                    self.resource_group, os_disk_name
                ).wait()
                logger.info(f"Deleted OS disk: {os_disk_name}")
            except Exception as e:
                logger.warning(f"Failed to delete OS disk {os_disk_name}: {str(e)}")
            
            # Delete network interface (but keep the existing VNet)
            nic_name = f"{vm_name}-nic"
            try:
                self.network_client.network_interfaces.begin_delete(
                    self.resource_group, nic_name
                ).wait()
                logger.info(f"Deleted network interface: {nic_name}")
            except Exception as e:
                logger.warning(f"Failed to delete {nic_name}: {str(e)}")
        except Exception as e:
            logger.error(f"Error deleting VM {vm_name}: {str(e)}")
            raise
