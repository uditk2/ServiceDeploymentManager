import logging
import os
from typing import Dict, Optional, List
import time
import asyncio
from .spot_vm_creator import SpotVMCreator
from .config import AzureVMConfig
from app.repositories.workspace_repository import WorkspaceRepository
from app.models.results.vm_operation_results import VMInfoResult
from app.models.workspace import VMConfig
from app.models.exceptions.known_exceptions import VMNotFoundException, VMInfoNotAvailableException
logger = logging.getLogger(__name__)

class SpotVMManager:
    """
    Manager class for handling user spot VM allocation, monitoring, and lifecycle management
    """
    
    def __init__(self, config: Optional[AzureVMConfig] = None):
        # Use provided config or create from environment
        self.config = config or AzureVMConfig.from_environment()
        
        # Initialize the spot VM creator with separate VNet resource group
        self.vm_creator = SpotVMCreator(
            subscription_id=self.config.subscription_id,
            resource_group=self.config.resource_group,
            vnet_resource_group=self.config.vnet_resource_group,
            vnet_name=self.config.vnet_name,
            subnet_name=self.config.subnet_name,
            location=self.config.location
        )
        
        # Initialize workspace repository for tracking VM allocations
        self.workspace_repo = WorkspaceRepository()
    
    def get_user_vm_name(self, user_id: str, workspace_id: str = None, use_workspace=False) -> str:
        """Generate a consistent VM name for a user"""
        # Clean user ID for VM naming (remove special characters)
        clean_user_id = ''.join(c for c in user_id if c.isalnum() or c == '-').lower()
        if workspace_id and use_workspace:
            clean_workspace_id = ''.join(c for c in workspace_id if c.isalnum() or c == '-').lower()
            return f"vm-{clean_user_id}-{clean_workspace_id}"[:64]  # Azure VM name limit
        return f"vm-{clean_user_id}"[:64]
    
    def check_user_vm_allocation(self, user_id: str, workspace_id: str = None) -> Optional[VMConfig]:
        """
        Check if a user has a spot VM allocated
        Returns VM details if allocated, None otherwise
        """
        try:
            vm_name = self.get_user_vm_name(user_id, workspace_id)
            
            # Check if VM exists in Azure
            vm_details = self.vm_creator.get_vm_details(vm_name)
            
            if vm_details:
                logger.info(f"Found allocated VM for user {user_id}: {vm_name}")
                return vm_details
            else:
                logger.info(f"No VM allocation found for user {user_id}")
                return None
        except VMNotFoundException:
            logger.info(f"VM {vm_name} not found for user {user_id}")
            return None
        except Exception as e:
            logger.error(f"Error checking VM allocation for user {user_id}: {str(e)}")
            return None
    
    def is_vm_running(self, vm_name: str) -> bool:
        """Check if a VM is currently running"""
        try:
            status = self.vm_creator.get_vm_status(vm_name)
            return status == 'running'
        except VMNotFoundException as e:
            raise e
        except Exception as e:
            logger.error(f"Error checking if VM {vm_name} is running: {str(e)}")
            return False
    
    async def allocate_or_reuse_vm(self, user_id, workspace_id=None, vm_name=None, vm_size=None, force_recreate=False):
        # Generate vm_name if not provided
        if not vm_name:
            vm_name = self.get_user_vm_name(user_id, workspace_id)
            
        # Set default vm_size if not provided
        if not vm_size:
            vm_size = "Standard_B2ats_v2"
            
        # Check if VM already exists
        existing_vm = self.check_user_vm_allocation(user_id, workspace_id)
        if existing_vm and not force_recreate:
            logger.info(f"VM {vm_name} already exists for user {user_id}")
            # Check if VM is running
            if self.is_vm_running(vm_name):
                logger.info(f"VM {vm_name} is already running")
                # Update workspace with current VM details
                if workspace_id:
                    await self.vm_creator.update_workspace_table(user_id, workspace_id, existing_vm)
                return VMInfoResult(
                    ip=existing_vm.private_ip,
                    vm_status=existing_vm.status,
                    vm_name=existing_vm.vm_name
                )
            else:
                logger.info(f"VM {vm_name} exists but is not running. Starting...")
                # Try to start the existing VM
                if self.vm_creator.start_vm(vm_name):
                    updated_vm = self.vm_creator.get_vm_details(vm_name)
                    # Update workspace with restarted VM details
                    if workspace_id:
                        await self.vm_creator.update_workspace_table(user_id, workspace_id, updated_vm)
                    return  VMInfoResult(
                        ip=updated_vm.private_ip,
                        vm_name=updated_vm.vm_name,
                        vm_status=updated_vm.status
                    )
                else:
                    logger.warning(f"Failed to start existing VM {vm_name}. Will create new one.")
                    self.vm_creator.delete_spot_vm(vm_name)
                    time.sleep(30)  # Wait for deletion to complete
        elif force_recreate and existing_vm:
            logger.info(f"Force recreating VM {vm_name} for user {user_id}")
            self.vm_creator.delete_spot_vm(vm_name)
            time.sleep(30)  # Wait for deletion to complete
        # Create a new VM
        logger.info(f"Creating new spot VM {vm_name} for user {user_id}")
        # Validate configuration before creating VM
        self.config.validate()
        vm_config = self.vm_creator.create_spot_vm(
            vm_name=vm_name,
            vm_size=vm_size,
            admin_username=self.config.admin_username
        )
        # Update workspace with VM configuration if workspace_id provided
        if workspace_id:
            await self.vm_creator.update_workspace_table(user_id, workspace_id, vm_config)
        return VMInfoResult(
            ip=vm_config.private_ip,
            vm_name=vm_config.vm_name,
            vm_status=vm_config.status
        )
    
    def deallocate_user_vm(self, user_id: str, workspace_id: str = None) -> bool:
        """
        Deallocate (stop) a user's spot VM to save costs
        """
        try:
            vm_name = self.get_user_vm_name(user_id, workspace_id)
            
            # Check if VM exists
            if not self.vm_creator.vm_exists(vm_name):
                logger.info(f"VM {vm_name} does not exist for user {user_id}")
                return True
            
            # Stop the VM
            success = self.vm_creator.stop_vm(vm_name)
            
            if success:
                logger.info(f"Successfully deallocated VM {vm_name} for user {user_id}")
            else:
                logger.error(f"Failed to deallocate VM {vm_name} for user {user_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error deallocating VM for user {user_id}: {str(e)}")
            return False
    
    def delete_user_vm_sync(self, user_id: str, workspace_id: str = None) -> bool:
        """
        Synchronous wrapper for delete_user_vm for compatibility with existing code
        """
        import asyncio
        return asyncio.run(self.delete_user_vm(user_id, workspace_id))

    async def delete_user_vm(self, user_id: str, workspace_id: str = None) -> bool:
        """
        Completely delete a user's spot VM and associated resources
        """
        try:
            vm_name = self.get_user_vm_name(user_id, workspace_id)
            
            # Check if VM exists
            if not self.vm_creator.vm_exists(vm_name):
                logger.info(f"VM {vm_name} does not exist for user {user_id}")
                return True
            
            # Delete the VM
            self.vm_creator.delete_spot_vm(vm_name)
            
            # Clear VM configuration from workspace if workspace_id provided
            if workspace_id:
                await self.vm_creator.clear_workspace_vm_config(user_id, workspace_id)
            
            logger.info(f"Successfully deleted VM {vm_name} for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting VM for user {user_id}: {str(e)}")
            return False
    
    def get_user_vm_info(self, user_id: str, workspace_id: str = None) -> Dict:
        """
        Get comprehensive information about a user's VM
        """
        try:
            vm_name = self.get_user_vm_name(user_id, workspace_id)
            vm_details = self.vm_creator.get_vm_details(vm_name)
            
            if not vm_details:
                return {
                    'allocated': False,
                    'vm_name': vm_name,
                    'status': 'not_found'
                }
            
            is_running = self.is_vm_running(vm_name)
            
            return {
                'allocated': True,
                'vm_name': vm_name,
                'vm_details': vm_details,
                'is_running': is_running,
                'status': vm_details.get('status', 'unknown'),
                'private_ip': vm_details.get('private_ip'),
                'vm_size': vm_details.get('vm_size'),
                'location': vm_details.get('location')
            }
            
        except Exception as e:
            logger.error(f"Error getting VM info for user {user_id}: {str(e)}")
            return {
                'allocated': False,
                'error': str(e),
                'status': 'error'
            }
    
    def list_all_user_vms(self) -> List[Dict]:
        """
        List all user VMs managed by this system
        """
        try:
            # Get all VMs with the naming pattern
            all_vms = self.vm_creator.list_user_vms(user_prefix="vm-")
            
            user_vms = []
            for vm in all_vms:
                # Extract user ID from VM name
                vm_name = vm.get('vm_name', '')
                if vm_name.startswith('vm-'):
                    parts = vm_name[3:].split('-')
                    if len(parts) >= 1:
                        user_id = parts[0]
                        workspace_id = parts[1] if len(parts) > 1 else None
                        
                        vm_info = {
                            'user_id': user_id,
                            'workspace_id': workspace_id,
                            'vm_details': vm,
                            'is_running': vm.get('status') == 'running'
                        }
                        user_vms.append(vm_info)
            
            return user_vms
            
        except Exception as e:
            logger.error(f"Error listing all user VMs: {str(e)}")
            return []
    
    def monitor_spot_vm_health(self, user_id: str, workspace_id: str = None) -> Dict:
        """
        Monitor the health of a user's spot VM and handle evictions
        """
        try:
            vm_info = self.get_user_vm_info(user_id, workspace_id)
            
            if not vm_info.get('allocated'):
                return {
                    'status': 'not_allocated',
                    'action_required': 'none'
                }
            
            vm_name = vm_info['vm_name']
            current_status = vm_info.get('status')
            
            # Check for spot VM eviction or unexpected shutdown
            if current_status in ['deallocated', 'stopped']:
                logger.warning(f"Spot VM {vm_name} appears to be evicted or stopped")
                
                # Try to restart the VM
                if self.vm_creator.start_vm(vm_name):
                    return {
                        'status': 'recovered',
                        'action_taken': 'restarted',
                        'vm_info': self.get_user_vm_info(user_id, workspace_id)
                    }
                else:
                    # If restart fails, the VM might need to be recreated
                    logger.warning(f"Failed to restart VM {vm_name}. May need recreation.")
                    return {
                        'status': 'restart_failed',
                        'action_required': 'recreate',
                        'vm_info': vm_info
                    }
            
            elif current_status == 'running':
                return {
                    'status': 'healthy',
                    'action_required': 'none',
                    'vm_info': vm_info
                }
            
            else:
                return {
                    'status': 'unknown',
                    'current_status': current_status,
                    'action_required': 'investigate',
                    'vm_info': vm_info
                }
                
        except Exception as e:
            logger.error(f"Error monitoring VM health for user {user_id}: {str(e)}")
            return {
                'status': 'error',
                'error': str(e),
                'action_required': 'investigate'
            }
    
    def ensure_user_vm(self, user_id: str, workspace_id: str = None, vm_size: str = None, force_recreate: bool = False):
        """
        Synchronous wrapper for allocate_or_reuse_vm for compatibility with existing code
        """
        import asyncio
        return asyncio.run(self.allocate_or_reuse_vm(
            user_id=user_id,
            workspace_id=workspace_id,
            vm_size=vm_size,
            force_recreate=force_recreate
        ))
