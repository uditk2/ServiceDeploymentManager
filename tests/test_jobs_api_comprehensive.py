#!/usr/bin/env python3
"""
Comprehensive API tests for jobs endpoints.
Tests all job-related endpoints including create, list, get, update, and delete operations.
"""
import requests
import json
import sys
import time
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8005"  # Change this to match your API server
JOBS_API_URL = f"{API_BASE_URL}/api/jobs"

# Test data
TEST_USERNAME = "test_user"
TEST_JOB = {
    "status": "pending",
    "workspace_id": 1,
    "username": TEST_USERNAME,  # Required field
    "workspace_name": "test-workspace",  # Required field
    "job_type": "deployment",  # Required field
    "config": {
        "target_env": "staging",
        "docker_image": "test-image:latest",
        "replicas": 1
    }
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


def test_create_job():
    print_test_header("Create Job")
    
    # Create a job
    response = requests.post(
        JOBS_API_URL,
        json=TEST_JOB
    )
    
    print_info(f"Response status: {response.status_code}")
    print_info(f"Response body: {response.text}")
    
    success = assert_equal(response.status_code, 200, "Status code should be 200")
    if not success:
        return False
    
    data = response.json()
    success = assert_equal(data.get("status"), "success", "Response status should be 'success'")
    success = success and assert_contains(data, "job_id", "Response should contain job_id")
    TEST_JOB["job_id"]= data["job_id"]  # Store the job ID for later tests
    return success


def test_create_invalid_job():
    print_test_header("Create Invalid Job")
    
    # Try to create an invalid job (missing required fields)
    invalid_jobs = [
        {},  # Empty job
        {"name": "invalid-job-1"},  # Missing all required fields
        {  # Missing workspace_name
            "name": "invalid-job-2",
            "username": TEST_USERNAME,
            "job_type": "deployment"
        },
        {  # Missing job_type
            "name": "invalid-job-3",
            "username": TEST_USERNAME,
            "workspace_name": "test-workspace"
        }
    ]
    
    success = True
    for invalid_job in invalid_jobs:
        response = requests.post(
            JOBS_API_URL,
            json=invalid_job
        )
        
        print_info(f"Response status: {response.status_code}")
        print_info(f"Response body: {response.text}")
        
        if not assert_equal(response.status_code, 422, f"Status code should be 422 for invalid job {invalid_job}"):
            success = False
            
    return success


def test_list_user_jobs():
    print_test_header("List User Jobs")
    
    # List jobs for the test user
    response = requests.get(f"{JOBS_API_URL}/user/{TEST_USERNAME}")
    
    print_info(f"Response status: {response.status_code}")
    print_info(f"Response body: {response.text}")
    
    success = assert_equal(response.status_code, 200, "Status code should be 200")
    if not success:
        return False
    
    jobs = response.json()
    success = isinstance(jobs, list)
    assert_equal(success, True, "Response should be a list of jobs")
    
    # Check if our test job is in the list
    found = False
    for job in jobs:
        if job.get("job_id") == TEST_JOB["job_id"]:
            found = True
            break
    
    assert_equal(found, True, f"Test job '{TEST_JOB['job_id']}' should be in the list")
    return success


def test_get_job():
    print_test_header("Get Job")
    
    # First create a job to get its ID
    create_response = requests.post(JOBS_API_URL, json=TEST_JOB)
    if create_response.status_code != 200:
        print_failure("Failed to create test job")
        return False
        
    job_id = create_response.json().get("job_id")
    if not job_id:
        print_failure("No job ID returned from create operation")
        return False
    
    # Get the specific job
    response = requests.get(f"{JOBS_API_URL}/{job_id}")
    
    print_info(f"Response status: {response.status_code}")
    print_info(f"Response body: {response.text}")
    
    if not assert_equal(response.status_code, 200, "Status code should be 200"):
        return False
    
    job = response.json()
    success = True
    
    # Verify all required fields
    required_fields = ["status", "username", "workspace_name", "job_type", "created_at", "updated_at"]
    for field in required_fields:
        if not assert_contains(job, field, f"Job should contain {field}"):
            success = False
            
    # Verify field values match what we created
    if not assert_equal(job.get("job_type"), TEST_JOB["job_type"], "Job type should match"):
        success = False
    if not assert_equal(job.get("job_id"), TEST_JOB["job_id"], "Job id should match"):
        success = False
    if not assert_equal(job.get("status"), "pending", "Initial job status should be pending"):
        success = False
        
    return success


def test_get_nonexistent_job():
    print_test_header("Get Nonexistent Job")
    
    # Try to get a job that doesn't exist
    response = requests.get(f"{JOBS_API_URL}/99999")
    
    print_info(f"Response status: {response.status_code}")
    print_info(f"Response body: {response.text}")
    
    success = assert_equal(response.status_code, 404, "Status code should be 404 for nonexistent job")
    return success


def test_update_job():
    print_test_header("Update Job")
    TEST_JOB_COPY = TEST_JOB.copy()
    del TEST_JOB_COPY['job_id']
    # First create a job to update
    create_response = requests.post(JOBS_API_URL, json=TEST_JOB_COPY)
    job_id = create_response.json().get("job_id")
    
    # Update the job status
    status = "running"
    response = requests.put(
        f"{JOBS_API_URL}/{job_id}/status",
        params={"status": status, "artifact_location": "artifacts/test"}
    )
    
    print_info(f"Response status: {response.status_code}")
    print_info(f"Response body: {response.text}")
    
    success = assert_equal(response.status_code, 200, "Status code should be 200")
    if not success:
        return False
    
    # Verify the update
    get_response = requests.get(f"{JOBS_API_URL}/{job_id}")
    job = get_response.json()
    
    success = assert_equal(job.get("status"), status, "Job status should be updated")
    
    return success


def test_delete_job():
    print_test_header("Delete Job")
    
    # First create a job to delete
# Create a modified version of TEST_JOB without the job_id field
    TEST_JOB_COPY = TEST_JOB.copy()
    del TEST_JOB_COPY['job_id']
    create_response = requests.post(JOBS_API_URL, json=TEST_JOB_COPY)
    job_id = create_response.json().get("job_id")
    
    # Delete the job
    response = requests.delete(f"{JOBS_API_URL}/{job_id}")
    
    print_info(f"Response status: {response.status_code}")
    print_info(f"Response body: {response.text}")
    
    success = assert_equal(response.status_code, 200, "Status code should be 200")
    if not success:
        return False
    
    # Verify the job is deleted
    get_response = requests.get(f"{JOBS_API_URL}/{job_id}")
    print_info(get_response.text)
    success = assert_equal(get_response.status_code, 404, "Job should not exist after deletion")
    
    return success


def run_all_tests():
    tests = [
        test_create_job,
        test_create_invalid_job,
        test_list_user_jobs,
        test_get_job,
        test_get_nonexistent_job,
        test_update_job,
        test_delete_job
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
    print(f"{Colors.BOLD}Jobs API Comprehensive Tests{Colors.ENDC}")
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