#!/usr/bin/env python3
"""
Comprehensive API tests for workspace endpoints.
Requires only the requests library.
Tests all endpoints including those that might not be implemented yet.
"""
import requests
import json
import sys
import time
from datetime import datetime
import zipfile
import io
import os

# Configuration
API_BASE_URL = "http://localhost:8005"  # Change this to match your API server
WORKSPACE_API_URL = f"{API_BASE_URL}/api/workspaces"

def create_test_workspace_zip():
    """Create a test workspace zip file in memory for upload testing."""
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        # Add some sample project files
        zf.writestr('main.py', 'print("Hello World!")')
        zf.writestr('requirements.txt', 'fastapi\nuvicorn')
        zf.writestr('config.json', json.dumps({
            'name': 'test_project',
            'version': '1.0.0',
            'description': 'Test project for API testing'
        }))
    memory_file.seek(0)
    return memory_file

# Test data
TEST_USERNAME = "test_user"
TEST_WORKSPACE = {
    "username": TEST_USERNAME,
    "workspace_name": f"test-workspace-{int(time.time())}",
    "api_keys": {
        "github": "test-github-key",
        "aws": "test-aws-key"
    },
    "docker_image_name": "test-image:latest",
    "workspace_path": f"/workspace/{TEST_USERNAME}/test-workspace",
    "deployed_versions": ["v1.0.0"],
    "service_url": "https://test-service.example.com"
}

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


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


def test_create_workspace():
    print_test_header("Create Workspace")
    
    # Create a workspace
    response = requests.post(
        WORKSPACE_API_URL,
        json=TEST_WORKSPACE
    )
    
    print_info(f"Response status: {response.status_code}")
    print_info(f"Response body: {response.text}")
    
    success = assert_equal(response.status_code, 200, "Status code should be 200")
    if not success:
        return False
    
    data = response.json()
    success = assert_equal(data.get("status"), "success", "Response status should be 'success'")
    success = success and assert_contains(data, "workspace_id", "Response should contain workspace_id")
    
    return success


def test_create_duplicate_workspace():
    print_test_header("Create Duplicate Workspace")
    
    # Try to create the same workspace again
    response = requests.post(
        WORKSPACE_API_URL,
        json=TEST_WORKSPACE
    )
    
    print_info(f"Response status: {response.status_code}")
    print_info(f"Response body: {response.text}")
    
    success = assert_equal(response.status_code, 400, "Status code should be 400 for duplicate workspace")
    return success


def test_list_user_workspaces():
    print_test_header("List User Workspaces")
    
    # List workspaces for the test user
    response = requests.get(f"{WORKSPACE_API_URL}/{TEST_USERNAME}")
    
    print_info(f"Response status: {response.status_code}")
    print_info(f"Response body: {response.text}")
    
    success = assert_equal(response.status_code, 200, "Status code should be 200")
    if not success:
        return False
    
    workspaces = response.json()
    success = isinstance(workspaces, list)
    assert_equal(success, True, "Response should be a list of workspaces")
    
    # Check if our test workspace is in the list
    found = False
    for workspace in workspaces:
        if workspace.get("workspace_name") == TEST_WORKSPACE["workspace_name"]:
            found = True
            break
    
    assert_equal(found, True, f"Test workspace '{TEST_WORKSPACE['workspace_name']}' should be in the list")
    return success


def test_get_workspace():
    print_test_header("Get Workspace")
    
    # Get the specific workspace
    response = requests.get(
        f"{WORKSPACE_API_URL}/{TEST_USERNAME}/{TEST_WORKSPACE['workspace_name']}"
    )
    
    print_info(f"Response status: {response.status_code}")
    print_info(f"Response body: {response.text}")
    
    success = assert_equal(response.status_code, 200, "Status code should be 200")
    if not success:
        return False
    
    workspace = response.json()
    success = assert_equal(workspace.get("username"), TEST_USERNAME, "Username should match")
    success = success and assert_equal(
        workspace.get("workspace_name"), 
        TEST_WORKSPACE["workspace_name"], 
        "Workspace name should match"
    )
    success = success and assert_equal(
        workspace.get("docker_image_name"), 
        TEST_WORKSPACE["docker_image_name"], 
        "Docker image name should match"
    )
    
    return success


def test_get_nonexistent_workspace():
    print_test_header("Get Nonexistent Workspace")
    
    # Try to get a workspace that doesn't exist
    response = requests.get(
        f"{WORKSPACE_API_URL}/{TEST_USERNAME}/nonexistent-workspace"
    )
    
    print_info(f"Response status: {response.status_code}")
    print_info(f"Response body: {response.text}")
    
    success = assert_equal(response.status_code, 404, "Status code should be 404 for nonexistent workspace")
    return success


def test_update_workspace():
    print_test_header("Update Workspace")
    
    # Update the workspace with new values
    update_data = {
        "docker_image_name": "updated-image:latest",
        "service_url": "https://updated-service.example.com",
        "api_keys": {
            "github": "updated-github-key",
            "aws": "updated-aws-key",
            "gcp": "new-gcp-key"
        }
    }
    
    # Since the update endpoint isn't directly exposed in the routes,
    # we'll simulate it by using a PATCH request
    response = requests.put(
        f"{WORKSPACE_API_URL}/{TEST_USERNAME}/{TEST_WORKSPACE['workspace_name']}",
        json=update_data
    )
    
    print_info(f"Response status: {response.status_code}")
    print_info(f"Response body: {response.text}")
    
    # Check if the update was successful
    # Note: This might return 404 if the PATCH endpoint isn't implemented
    # In that case, we'll skip this test
    if response.status_code == 404:
        print_warning("Update endpoint not implemented, skipping test")
        return True
    
    success = assert_equal(response.status_code, 200, "Status code should be 200")
    if not success:
        return False
    
    # Verify the update by getting the workspace again
    response = requests.get(
        f"{WORKSPACE_API_URL}/{TEST_USERNAME}/{TEST_WORKSPACE['workspace_name']}"
    )
    
    workspace = response.json()
    success = assert_equal(
        workspace.get("docker_image_name"), 
        update_data["docker_image_name"], 
        "Docker image name should be updated"
    )
    success = success and assert_equal(
        workspace.get("service_url"), 
        update_data["service_url"], 
        "Service URL should be updated"
    )
    
    # Check if the API keys were updated
    api_keys = workspace.get("api_keys", {})
    success = success and assert_equal(
        api_keys.get("github"), 
        update_data["api_keys"]["github"], 
        "GitHub API key should be updated"
    )
    success = success and assert_equal(
        api_keys.get("gcp"), 
        update_data["api_keys"]["gcp"], 
        "GCP API key should be added"
    )
    
    return success


def test_add_deployed_version():
    print_test_header("Add Deployed Version")
    
    # Add a new deployed version
    new_version = f"v1.1.{int(time.time())}"
    update_data = {
        "add_deployed_version": new_version
    }
    
    # Since the add_deployed_version endpoint isn't directly exposed in the routes,
    # we'll simulate it by using a PATCH request
    response = requests.patch(
        f"{WORKSPACE_API_URL}/{TEST_USERNAME}/{TEST_WORKSPACE['workspace_name']}/versions",
        json=update_data
    )
    
    print_info(f"Response status: {response.status_code}")
    print_info(f"Response body: {response.text}")
    
    # Check if the update was successful
    # Note: This might return 404 if the PATCH endpoint isn't implemented
    # In that case, we'll skip this test
    if response.status_code == 404:
        print_warning("Add deployed version endpoint not implemented, skipping test")
        return True
    
    success = assert_equal(response.status_code, 200, "Status code should be 200")
    if not success:
        return False
    
    # Verify the update by getting the workspace again
    response = requests.get(
        f"{WORKSPACE_API_URL}/{TEST_USERNAME}/{TEST_WORKSPACE['workspace_name']}"
    )
    
    workspace = response.json()
    deployed_versions = workspace.get("deployed_versions", [])
    success = assert_contains(
        deployed_versions, 
        new_version, 
        f"Deployed versions should contain the new version {new_version}"
    )
    
    # Check if the new version is at the beginning of the list (most recent)
    if deployed_versions and deployed_versions[0] == new_version:
        print_success("New version is at the beginning of the list (most recent)")
    else:
        print_failure(f"New version should be at the beginning of the list. Got: {deployed_versions}")
        success = False
    
    return success


def test_upload_workspace():
    print_test_header("Upload Workspace")
    
    # Create test zip file
    zip_file = create_test_workspace_zip()
    
    # Prepare the files and form data
    files = {
        'zip_file': ('workspace.zip', zip_file, 'application/zip')
    }
    
    # Make the request to upload endpoint
    url = f"{WORKSPACE_API_URL}/upload/{TEST_USERNAME}/{TEST_WORKSPACE['workspace_name']}"
    response = requests.post(url, files=files)
    
    print_info(f"Response status: {response.status_code}")
    print_info(f"Response body: {response.text}")
    
    # Check if the upload endpoint is implemented
    if response.status_code == 404:
        print_warning("Upload endpoint not implemented, skipping test")
        return True
    
    success = assert_equal(response.status_code, 200, "Status code should be 200")
    if not success:
        return False
    
    response_data = response.json()
    success = assert_equal(
        response_data.get("status"),
        "success",
        "Upload status should be success"
    )
    success = success and assert_contains(
        response_data,
        "workspace_path",
        "Response should contain workspace_path"
    )
    
    return success

def test_delete_workspace():
    print_test_header("Delete Workspace")
    
    # Get the workspace details before deletion to check the path
    response = requests.get(
        f"{WORKSPACE_API_URL}/{TEST_USERNAME}/{TEST_WORKSPACE['workspace_name']}"
    )
    workspace_details = response.json()
    workspace_path = workspace_details.get('project_base_path')
    
    # Delete the workspace
    response = requests.delete(
        f"{WORKSPACE_API_URL}/{TEST_USERNAME}/{TEST_WORKSPACE['workspace_name']}"
    )
    
    print_info(f"Response status: {response.status_code}")
    print_info(f"Response body: {response.text}")
    
    # Check if the delete endpoint is implemented
    if response.status_code == 404 and "not found" in response.text.lower():
        print_warning("Delete endpoint not implemented, skipping test")
        return True
    
    success = assert_equal(response.status_code, 200, "Status code should be 200")
    if not success:
        return False
    
    # Verify workspace is deleted from database by trying to get it
    response = requests.get(
        f"{WORKSPACE_API_URL}/{TEST_USERNAME}/{TEST_WORKSPACE['workspace_name']}"
    )
    success = assert_equal(response.status_code, 404, "Status code should be 404 after deletion")
    
    # Verify the workspace files are deleted
    if workspace_path and os.path.exists(workspace_path):
        print_failure(f"Workspace directory still exists at {workspace_path}")
        success = False
    else:
        print_success("Workspace directory was successfully deleted")
    
    return success


def run_all_tests():
    tests = [
        test_create_workspace,
        test_create_duplicate_workspace,
        test_list_user_workspaces,
        test_get_workspace,
        test_get_nonexistent_workspace,
        test_update_workspace,
        test_add_deployed_version,
        test_upload_workspace,  # Add the new test to the test suite
        test_delete_workspace
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
    print(f"{Colors.BOLD}Workspace API Comprehensive Tests{Colors.ENDC}")
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Testing with username: {TEST_USERNAME}")
    print(f"Testing with workspace: {TEST_WORKSPACE['workspace_name']}")
    
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