import logging
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient
from typing import Dict, Optional, List
import time
import os
import base64
from azure.core.exceptions import ResourceNotFoundError
from app.models.workspace import VMConfig
from app.repositories.workspace_repository import WorkspaceRepository
from app.models.exceptions.known_exceptions import VMCreationFailedException, VMNotFoundException, VMInfoNotAvailableException
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
    
    def _get_cloud_init_data(self) -> str:
        """
        Get cloud-init data for Docker installation
        """
        try:
            # Get the cloud-init file path from the same directory as this module
            current_dir = os.path.dirname(os.path.abspath(__file__))
            cloud_init_path = os.path.join(current_dir, 'cloud-init-docker.yaml')
            
            if os.path.exists(cloud_init_path):
                with open(cloud_init_path, 'r') as f:
                    cloud_init_content = f.read()
                # Encode as base64 for Azure VM custom data
                return base64.b64encode(cloud_init_content.encode('utf-8')).decode('utf-8')
            else:
                logger.warning(f"Cloud-init file not found at {cloud_init_path}, VM will be created without Docker pre-installation")
                raise ValueError(f"Failed to read cloud-init file: {e}")
        except Exception as e:
            logger.error(f"Error reading cloud-init file: {e}")
            raise ValueError(f"Failed to read cloud-init file: {e}")
    
    def create_spot_vm(self, vm_name: str, vm_size: str = "Standard_B2ats_v2", 
                       admin_username: str = "azureuser", ssh_public_key: str = None) -> Optional[VMConfig]:
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
                    raise VMCreationFailedException("SSH public key resource 'spot_vm_key' not found in resource group {self.resource_group}")
                except Exception as e:
                    logger.error(f"Error fetching SSH public key: {e}")
                    raise VMCreationFailedException(f"Failed to create VM {vm_name}") from e
            
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
                raise VMCreationFailedException(f"Subnet {self.subnet_name} not found in virtual network {self.vnet_name}")
            
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
            
            # Get cloud-init data for Docker installation
            cloud_init_data = self._get_cloud_init_data()
            
            # Create spot VM
            vm_params = {
                'location': self.location,
                'hardware_profile': {'vm_size': vm_size},
                'storage_profile': {
                        'image_reference': {
                        'publisher': 'Canonical',
                        'offer': 'ubuntu-24_04-lts',
                        'sku': 'server', ## We can check if there is a gen 2 image available              
                        'version': 'latest'
                    },
                    'os_disk': {
                        'create_option': 'FromImage',
                        'managed_disk': {'storage_account_type': 'Premium_LRS'},
                        'delete_option': 'Delete' 
                    }
                },
                'os_profile': {
                    'computer_name': vm_name,
                    'admin_username': admin_username,
                    'disable_password_authentication': True,
                    'custom_data': cloud_init_data,  # Add cloud-init data for Docker installation
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
                    'network_interfaces': [{
                        'id': nic_result.id,
                        'properties': {                   
                            'delete_option': 'Delete'
                        }
                    }],
                },
                ##  Uncomment the following lines if you want to use spot VMs.
                ## We do not have quota for spot VMs in our subscription.
                #'priority': 'Spot',
                # 'eviction_policy': 'Deallocate',
                # 'billing_profile': {
                #     'max_price': -1  # -1 means pay up to on-demand price
                # }
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
            
            vm_config = VMConfig(
                vm_name=vm_name,
                vm_id=vm_result.id,
                resource_group=self.resource_group,
                location=self.location,
                vm_size=vm_size,
                private_ip=private_ip,
                nic_id=nic_result.id,
                vnet_name=self.vnet_name,
                subnet_name=self.subnet_name,
                status='running',
                created_at=time.time(),  # This would ideally come from tags or database
            )

            logger.info(f"Spot VM created successfully: {vm_name} with private IP: {private_ip}")
            return vm_config
            
        except Exception as e:
            logger.error(f"Error creating VM {vm_name}: {str(e)}")
            raise VMCreationFailedException(f"Failed to create VM {vm_name}: {str(e)}") from e
    
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
            raise VMNotFoundException(f"VM {vm_name} not found in resource group {self.resource_group}")
        except Exception as e:
            raise VMInfoNotAvailableException(f"Failed to get VM status for {vm_name}: {str(e)}") from e

    def get_vm_details(self, vm_name: str) -> Optional[VMConfig]:
        """Get detailed information about a VM"""
        try:
            vm = self.compute_client.virtual_machines.get(self.resource_group, vm_name)
            status = self.get_vm_status(vm_name)
            
            # Get network interface details
            nic_id = vm.network_profile.network_interfaces[0].id
            nic_name = nic_id.split('/')[-1]
            nic_info = self.network_client.network_interfaces.get(self.resource_group, nic_name)
            private_ip = nic_info.ip_configurations[0].private_ip_address
            
            return VMConfig(
                vm_name=vm_name,
                vm_id=vm.id,
                resource_group=self.resource_group,
                location=vm.location,
                vm_size=vm.hardware_profile.vm_size,
                private_ip=private_ip,
                nic_id=nic_id,
                vnet_name=self.vnet_name,
                subnet_name=self.subnet_name,
                status=status if status else 'unknown',
                priority=vm.priority if hasattr(vm, 'priority') else None,  # Handle if priority is not set
                created_at=time.time()
            )
        except ResourceNotFoundError:
            raise VMNotFoundException(f"VM {vm_name} not found in resource group {self.resource_group}")
        except Exception as e:
            logger.error(f"Error getting VM details for {vm_name}: {str(e)}")
            raise VMInfoNotAvailableException(f"Failed to get VM details for {vm_name}: {str(e)}") from e
    
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

    def run_vm_command(self, vm_name: str, command: str) -> Optional[str]:
        """
        Run a command on the VM using Azure Run Command
        """
        try:
            logger.info(f"Running command on VM {vm_name}: {command}")
            run_command_result = self.compute_client.virtual_machines.begin_run_command(
                self.resource_group, vm_name, {
                    'command_id': 'RunShellScript',
                    'script': [command]
                }
            ).result()
            
            if run_command_result.value and run_command_result.value[0].message:
                return run_command_result.value[0].message
            else:
                logger.warning(f"No output from command on VM {vm_name}")
                return None
        except Exception as e:
            logger.error(f"Error running command on VM {vm_name}: {str(e)}")
            return None
        
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

    async def update_workspace_table(self, username: str, workspace_name: str, vm_config: VMConfig):
        """
        Update workspace table with VM configuration including Docker context details
        """
        try:
            
            # Await the async update_vm_config call instead of generic update_workspace
            success = await WorkspaceRepository.update_vm_config_state(
                username=username,
                workspace_name=workspace_name,
                vm_config=vm_config
            )
            if success:
                logger.info(f"Successfully updated workspace {workspace_name} for user {username} with VM configuration")
                logger.info(f"VM private IP: {vm_config.private_ip} - ready for Docker context")
            else:
                logger.warning(f"Failed to update workspace {workspace_name} for user {username}")
            return success
        except Exception as e:
            logger.error(f"Error updating workspace table for {username}/{workspace_name}: {str(e)}")
            return False
        
    
    async def clear_workspace_vm_config(self, username: str, workspace_name: str):
        """
        Clear VM configuration from workspace table when VM is deleted
        """
        try:

            # Use the new clear_vm_config_state to remove the vm_config field
            success = await WorkspaceRepository.clear_vm_config_state(
                username=username,
                workspace_name=workspace_name
            )
            if success:
                logger.info(f"Successfully cleared VM configuration from workspace {workspace_name} for user {username}")
            else:
                logger.warning(f"Failed to clear VM configuration from workspace {workspace_name} for user {username}")
            return success
        except Exception as e:
            logger.error(f"Error clearing VM config for {username}/{workspace_name}: {str(e)}")
            return False

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