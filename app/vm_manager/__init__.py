"""
VM Manager Module

This module provides functionality for managing Azure Spot VMs for user workspaces.
"""

from .spot_vm_creator import SpotVMCreator
from .spot_vm_manager import SpotVMManager
from .config import AzureVMConfig

__all__ = ['SpotVMCreator', 'SpotVMManager', 'AzureVMConfig']
