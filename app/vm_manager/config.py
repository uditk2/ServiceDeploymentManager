"""
Configuration management for Azure VM services
"""

import os
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class AzureVMConfig:
    """Configuration for Azure VM management"""
    subscription_id: str
    resource_group: str
    vnet_resource_group: str  # Resource group where the VNet resides
    vnet_name: str
    subnet_name: str
    location: str = "East US"
    admin_username: str = "azureuser"
    ssh_public_key: Optional[str] = None
    default_vm_size: str = "Standard_B2s"
    
    @classmethod
    def from_environment(cls) -> 'AzureVMConfig':
        """Create configuration from environment variables"""
        subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
        resource_group = os.getenv('AZURE_RESOURCE_GROUP')
        # Read separate VNet resource group or use the main resource group
        vnet_resource_group = os.getenv('AZURE_VNET_RESOURCE_GROUP', resource_group)
        vnet_name = os.getenv('AZURE_VNET_NAME')
        subnet_name = os.getenv('AZURE_SUBNET_NAME')
        
        if not all([subscription_id, resource_group, vnet_name, subnet_name]):
            missing = []
            if not subscription_id:
                missing.append('AZURE_SUBSCRIPTION_ID')
            if not resource_group:
                missing.append('AZURE_RESOURCE_GROUP')
            if not vnet_name:
                missing.append('AZURE_VNET_NAME')
            if not subnet_name:
                missing.append('AZURE_SUBNET_NAME')
                
            raise ValueError(f"Missing required Azure configuration: {', '.join(missing)}")
        
        return cls(
            subscription_id=subscription_id,
            resource_group=resource_group,
            vnet_resource_group=vnet_resource_group,
            vnet_name=vnet_name,
            subnet_name=subnet_name,
            location=os.getenv('AZURE_LOCATION', 'East US'),
            admin_username=os.getenv('AZURE_VM_ADMIN_USERNAME', 'azureuser'),
            ssh_public_key=os.getenv('AZURE_SSH_PUBLIC_KEY'),
            default_vm_size=os.getenv('AZURE_DEFAULT_VM_SIZE', 'Standard_B2s')
        )
    
    def validate(self) -> bool:
        """Validate the configuration"""
        if not self.ssh_public_key:
            raise ValueError("SSH public key is required for VM creation")
        
        return True
