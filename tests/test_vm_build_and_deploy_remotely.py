import requests
import json
import sys
import time
from datetime import datetime
import os
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()
def print_test_header(test_name):
    print(f"\n{Colors.HEADER}{Colors.BOLD}Running test: {test_name}{Colors.ENDC}")


def print_success(message):
    print(f"{Colors.OKGREEN}✓ {message}{Colors.ENDC}")


def print_failure(message):
    print(f"{Colors.FAIL}✗ {message}{Colors.ENDC}")


def print_info(message):
    print(f"{Colors.OKBLUE}ℹ {message}{Colors.ENDC}")


def print_warning(message):
    print(f"{Colors.WARNING}⚠ {message}{Colors.ENDC}")


def assert_equal(actual, expected, message):
    if actual == expected:
        print_success(message)
        return True
    else:
        print_failure(f"{message} - Expected: {expected}, Got: {actual}")
        return False


def assert_contains(container, item, message):
    if item in container:
        print_success(message)
        return True
    else:
        print_failure(f"{message} - {item} not found in {container}")
        return False


#IP = "localhost"  # Change this to the IP address of your API server
REMOTE = "https://apps.synergiqai.com"
LOCAL = "http://localhost:8005"
# Configuration
API_BASE_URL = REMOTE # Change this to match your API server
DOCKER_API_URL = f"{API_BASE_URL}/api/docker"
JOB_API_URL = f"{API_BASE_URL}/api/jobs"
TEST_USERNAME = "uditk2@gmail.com"
TEST_WORKSPACE = "AdventureousChemist"

def test_build_deploy_docker_image():
    """Build a Docker image for the project."""
    url = f"{DOCKER_API_URL}/build_deploy/{TEST_USERNAME}/{TEST_WORKSPACE}"
    print_test_header("Building and deploying Docker image")
    zip_file_path = "tests/AdventureousChemist.zip"

    try:
        with open(zip_file_path, 'rb') as f:
            files = {'zip_file': (zip_file_path, f)}
            auth_token = os.getenv("AUTH_TOKEN")
            headers = {'Accept': 'application/json', 'Authorization': f"{auth_token}"}
            print_info(f"Sending build request to {url}")
            response = requests.post(url, files=files, headers=headers)
            
            if response.status_code != 200:
                print_warning(f"Response: {response.status_code} - {response.text}")
            else:
                print_info(f"Response: {response.status_code}")
                print_info(f"Response content: {response.content.decode('utf-8')}")
            return wait_for_job_completion(response.json().get('job_id'))
    except FileNotFoundError:
        print_failure(f"Test zip file not found: {zip_file_path}")
        return False

def test_build_docker_image():
    """Test the /build route for Docker image build only (no deploy)."""
    url = f"{DOCKER_API_URL}/build/{TEST_USERNAME}/{TEST_WORKSPACE}"
    print_test_header("Building Docker image (build only)")
    zip_file_path = "tests/AdventureousChemist.zip"
    
    try:
        with open(zip_file_path, 'rb') as f:
            files = {'zip_file': (zip_file_path, f)}
            auth_token = os.getenv("AUTH_TOKEN")
            headers = {'Accept': 'application/json', 'Authorization': f"{auth_token}"}
            print_info(f"Sending build request to {url}")
            response = requests.post(url, files=files, headers=headers)
            
            if response.status_code != 200:
                print_warning(f"Response: {response.status_code} - {response.text}")
            else:
                print_info(f"Response: {response.status_code}")
                print_info(f"Response content: {response.content.decode('utf-8')}")
            return wait_for_job_completion(response.json().get('job_id'))
    except FileNotFoundError:
        print_failure(f"Test zip file not found: {zip_file_path}")
        return False

def test_ensure_vm_then_build_deploy():
    """
    Ensures the VM is up for the user/workspace, then builds and deploys the Docker image.
    """

    AUTH_TOKEN = os.getenv("AUTH_TOKEN")
    headers = {'Accept': 'application/json', 'Authorization': f"{AUTH_TOKEN}"}
    
    def wait_for_job(job_id):
        url = f"{API_BASE_URL}/api/jobs/{job_id}"
        while True:
            resp = requests.get(url, headers=headers)
            if resp.status_code != 200:
                print_failure(f"Job status failed: {resp.status_code} {resp.text}")
                return False
            status = resp.json().get('status')
            if status not in ['pending', 'running']:
                print_info(f"Job completed with status: {status}")
                print_info(f"Job result: {resp.json().get('metadata', {})}")
                return status == 'completed'
            time.sleep(5)
    
    # 1. Ensure VM
    url = f"{API_BASE_URL}/api/vm/ensure/{TEST_USERNAME}/{TEST_WORKSPACE}"
    body = {"create": False}

    print_test_header("Ensuring VM for user/workspace (create=False)")
    print_info(f"Request body: {body}")
    resp = requests.post(url, headers=headers, json=body)
    if resp.status_code != 200:
        print_failure(f"Failed to ensure VM: {resp.text}")
        return False
    job_id = resp.json().get('job_id')
    if not job_id:
        print_failure("No job_id returned from ensure_vm")
        return False
    print_info(f"Ensuring VM, job_id: {job_id}")
    if not wait_for_job(job_id):
        print_failure("VM ensure job did not complete successfully")
        return False
    
    # 2. Build and Deploy
    url = f"{API_BASE_URL}/api/docker/build_deploy/{TEST_USERNAME}/{TEST_WORKSPACE}"
    zip_file_path = "tests/BasePythonWebApp.zip"
    try:
        with open(zip_file_path, 'rb') as f:
            files = {'zip_file': (zip_file_path, f)}
            resp = requests.post(url, files=files, headers=headers)
        if resp.status_code != 200:
            print_failure(f"Build/Deploy failed: {resp.text}")
            return False
        job_id = resp.json().get('job_id')
        if not job_id:
            print_failure("No job_id returned from build_deploy")
            return False
        print_info(f"Build/Deploy job_id: {job_id}")
        if not wait_for_job(job_id):
            print_failure("Build/Deploy job did not complete successfully")
            return False
        print_success("ensure_vm_then_build_deploy passed!")
        return True
    except FileNotFoundError:
        print_failure(f"Test zip file not found: {zip_file_path}")
        return False

def wait_for_job_completion(job_id):
    """Create a job for the Docker image build."""
    url = f"{JOB_API_URL}/{job_id}"
    print_test_header("Waiting for job completion")
    
    try:
        while True:
            print_info(f"Get job status for job id {job_id}")
            response = requests.get(url, headers={'Accept': 'application/json', 'Authorization': f"{os.getenv('AUTH_TOKEN')}"})
            
            if response.status_code != 200:
                print_warning(f"Response: {response.status_code} - {response.text}")
                break
            else:
                print_info(f"Response: {response.status_code}")
                print_info(f"Response content: {response.content.decode('utf-8')}")
                job_status = response.json().get('status')
                if job_status != 'pending' and job_status != 'running':
                    print_info(f"Job completed with status: {job_status}")
                    print_info(f"Job result: {response.json().get('metadata', {})}")
                    assertion = assert_equal(job_status, 'completed', "Job status should be completed")
                    job_result = response.json().get("metadata", {})
                    assertion = assertion and assert_equal(job_result, True, "Job result should be successful")
                    return assertion
                else:
                    print_info(f"Job is still {job_status}. Waiting...")
            time.sleep(5)  # Wait for 5 seconds before checking again
    except requests.exceptions.RequestException as e:
        print_failure(f"Request failed: {str(e)}")
        return False
        
def run_all_tests():
    tests = [
        test_ensure_vm_then_build_deploy
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print_failure(f"Test {test.__name__} failed with exception: {str(e)}")
            results.append(False)
    
    print("\n" + "="*50)
    print(f"{Colors.BOLD}Test Results Summary:{Colors.ENDC}")
    print("="*50)
    
    all_passed = True
    for i, result in enumerate(results):
        test_name = tests[i].__name__
        if result:
            print(f"{Colors.OKGREEN}✓ {test_name} - PASSED{Colors.ENDC}")
        else:
            all_passed = False
            print(f"{Colors.FAIL}✗ {test_name} - FAILED{Colors.ENDC}")
    
    print("="*50)
    if all_passed:
        print(f"{Colors.OKGREEN}{Colors.BOLD}All tests passed!{Colors.ENDC}")
        return 0
    else:
        print(f"{Colors.FAIL}{Colors.BOLD}Some tests failed!{Colors.ENDC}")
        return 1

def main():
    print(f"{Colors.BOLD}Docker API Comprehensive Tests{Colors.ENDC}")
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Testing with username: {TEST_USERNAME}")

    try:
        sys.exit(run_all_tests())
    except requests.exceptions.ConnectionError:
        print(f"{Colors.FAIL}Error: Could not connect to the API server at {API_BASE_URL}{Colors.ENDC}")
        print(f"{Colors.FAIL}Make sure the API server is running and the URL is correct.{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print(f"{Colors.FAIL}Error: {str(e)}{Colors.ENDC}")
        sys.exit(1)

if __name__ == "__main__":
    main()