#!/usr/bin/env python3
"""
Test script for Spot VM Manager functionality

This script demonstrates how to use the SpotVMManager to manage Azure Spot VMs.
Make sure to set the required environment variables before running.
"""

import os
import sys
import time
import logging
from typing import Dict
from dotenv import load_dotenv
load_dotenv()
# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.vm_manager import SpotVMManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_environment():
    """Check if required environment variables are set"""
    required_vars = [
        'AZURE_SUBSCRIPTION_ID',
        'AZURE_RESOURCE_GROUP', 
        'AZURE_VNET_NAME',
        'AZURE_SUBNET_NAME',
        'AZURE_SSH_PUBLIC_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        logger.error("Please set these variables in your .env file or environment")
        return False
    
    return True

def test_vm_manager():
    """Test the VM manager functionality"""
    try:
        logger.info("Initializing SpotVMManager...")
        vm_manager = SpotVMManager()
        
        # Test user
        test_user = "uditk2@gmail.com"
        test_workspace = "BasePythonWebApp"
        
        logger.info(f"Testing VM management for user: {test_user}")
        
        # Step 1: Check current VM allocation
        logger.info("Step 1: Checking current VM allocation...")
        vm_info = vm_manager.get_user_vm_info(test_user, test_workspace)
        logger.info(f"Current VM info: {vm_info}")
        
        # Step 2: Ensure VM is available
        logger.info("Step 2: Ensuring VM is available...")
        result = vm_manager.allocate_or_reuse_vm(
            user_id=test_user,
            workspace_id=test_workspace,
            vm_size=os.getenv('VM_SIZE', 'Standard_B2ats_v2')
        )
        logger.info(f"Ensure VM result: {result}")
        
        # Step 3: Check VM info again
        logger.info("Step 3: Checking VM info after ensure...")
        vm_info = vm_manager.get_user_vm_info(test_user, test_workspace)
        logger.info(f"Updated VM info: {vm_info}")
        
        # Step 4: Monitor VM health
        logger.info("Step 4: Monitoring VM health...")
        health_status = vm_manager.monitor_spot_vm_health(test_user, test_workspace)
        logger.info(f"VM health status: {health_status}")
        
        # Step 5: List all user VMs
        logger.info("Step 5: Listing all user VMs...")
        all_vms = vm_manager.list_all_user_vms()
        logger.info(f"All user VMs: {len(all_vms)} VMs found")
        for vm in all_vms:
            logger.info(f"  - User: {vm.get('user_id')}, VM: {vm.get('vm_details', {}).get('vm_name')}, Status: {vm.get('vm_details', {}).get('status')}")
        
        # Wait a bit then test stop/start
        logger.info("Waiting 30 seconds before testing stop/start...")
        time.sleep(30)
        
        # Step 6: Test stop VM
        logger.info("Step 6: Testing VM stop...")
        stop_result = vm_manager.deallocate_user_vm(test_user, test_workspace)
        logger.info(f"Stop result: {stop_result}")
        
        # Wait for stop to complete
        time.sleep(30)
        
        # Step 7: Check status after stop
        logger.info("Step 7: Checking status after stop...")
        vm_info = vm_manager.get_user_vm_info(test_user, test_workspace)
        logger.info(f"VM info after stop: {vm_info}")
        
        # Step 8: Test start VM
        logger.info("Step 8: Testing VM start...")
        result = vm_manager.ensure_user_vm(test_user, test_workspace)
        logger.info(f"Start result: {result}")
        
        logger.info("VM Manager test completed successfully!")
        
        return True
        
    except Exception as e:
        logger.error(f"Error during VM manager test: {str(e)}")
        return False

def cleanup_test_vm():
    """Clean up the test VM"""
    try:
        logger.info("Cleaning up test VM...")
        vm_manager = SpotVMManager()
        
        test_user = "uditk2@gmail.com"
        test_workspace = "BasePythonWebApp"
        
        result = vm_manager.delete_user_vm_sync(test_user, test_workspace)
        logger.info(f"Cleanup result: {result}")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")

def main():
    """Main function"""
    logger.info("Starting Spot VM Manager Test")
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Run test
    success = test_vm_manager()
    
    if success:
        logger.info("Test completed successfully!")
        
        # Ask if user wants to cleanup
        cleanup = input("Do you want to delete the test VM? (y/N): ")
        if cleanup.lower() == 'y':
            cleanup_test_vm()
    else:
        logger.error("Test failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
