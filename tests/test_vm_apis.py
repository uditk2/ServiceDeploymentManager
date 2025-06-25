#!/usr/bin/env python3
"""
Integration test for VM API
Ensure spot VM ensure job and workspace update
"""
import requests
import sys
import time
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Reuse Colors from test_docker_apis
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# Configuration
LOCAL = "http://localhost:8005"
API_BASE_URL = os.getenv('API_BASE_URL', LOCAL)
VM_API_URL = f"{API_BASE_URL}/api/vm/ensure"
JOB_API_URL = f"{API_BASE_URL}/api/jobs"
WORKSPACE_API_URL = f"{API_BASE_URL}/api/workspaces"

# Test parameters
test_user = 'uditk2@gmail.com'
test_workspace = 'BasePythonWebApp'
AUTH_TOKEN = os.getenv('AUTH_TOKEN')
HEADERS = {'Accept': 'application/json', 'Authorization': AUTH_TOKEN} if AUTH_TOKEN else {'Accept': 'application/json'}


def print_header(msg):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{msg}{Colors.ENDC}")

def print_success(msg):
    print(f"{Colors.OKGREEN}✓ {msg}{Colors.ENDC}")

def print_failure(msg):
    print(f"{Colors.FAIL}✗ {msg}{Colors.ENDC}")


def assert_equal(a, b, msg):
    if a == b:
        print_success(msg)
        return True
    else:
        print_failure(f"{msg} - Expected: {b}, Got: {a}")
        return False


def wait_for_job(job_id):
    print_header(f"Polling job status: {job_id}")
    url = f"{JOB_API_URL}/{job_id}"
    while True:
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code != 200:
            print_failure(f"Failed to get job: {resp.status_code} - {resp.text}")
            return None
        data = resp.json()
        status = data.get('status')
        print(f"Job status: {status}")
        if status in ['completed', 'failed']:
            return data
        time.sleep(5)


def test_vm_api():
    print_header("Testing VM ensure job API")
    print(f"Using URL: {VM_API_URL}/{test_user}/{test_workspace}")
    print(f"Headers: {HEADERS}")
    # Trigger ensure VM job
    url = f"{VM_API_URL}/{test_user}/{test_workspace}"
    resp = requests.post(url, headers=HEADERS)
    if resp.status_code != 200:
        print_failure(f"Failed to trigger VM job: {resp.status_code} - {resp.text}")
        return False
    job_id = resp.json().get('job_id')
    print_success(f"Job created: {job_id}")

    # Wait for completion
    job_data = wait_for_job(job_id)
    if not job_data or job_data.get('status') != 'completed':
        print_failure("Job did not complete successfully")
        return False
    print_success("Job completed successfully")

    vm_result = job_data.get('metadata', {}).get('vm_result')
    if not vm_result:
        print_failure("VM result missing in job metadata")
        return False
    # Check keys
    required_keys = ['status', 'vm_config', 'action_taken']
    for key in required_keys:
        if key not in vm_result:
            print_failure(f"Key '{key}' missing in vm_result")
            return False
    print_success("vm_result contains required keys")

    # Check status
    if not assert_equal(vm_result.get('status'), 'running', "VM status should be 'running'"):
        return False

    # Verify workspace updated
    print_header("Verifying workspace VM configuration")
    url2 = f"{WORKSPACE_API_URL}/{test_user}/{test_workspace}"
    resp2 = requests.get(url2, headers=HEADERS)
    if resp2.status_code != 200:
        print_failure(f"Failed to get workspace: {resp2.status_code} - {resp2.text}")
        return False
    ws = resp2.json()
    vm_conf = ws.get('vm_config')
    if not vm_conf:
        print_failure("vm_config missing in workspace data")
        return False
    # Compare vm_name
    if not assert_equal(vm_conf.get('vm_name'), vm_result.get('vm_config', {}).get('vm_name'), "Workspace vm_name matches result"):
        return False
    print_success("Workspace vm_config updated correctly")
    return True


def run_all():
    result = test_vm_api()
    print_header("Test VM API Completed")
    if result:
        print_success("All VM API tests passed!")
        sys.exit(0)
    else:
        print_failure("Some VM API tests failed")
        sys.exit(1)

if __name__ == '__main__':
    run_all()
