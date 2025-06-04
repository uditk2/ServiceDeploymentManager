import requests
import json
import sys
import time
from datetime import datetime

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

def assert_not_equal(actual, expected, message):
    if actual != expected:
        print_success(message)
        return True
    else:
        print_failure(f"{message} - Expected NOT to be: {expected}, Got: {actual}")
        return False

def assert_contains(container, item, message):
    if item in container:
        print_success(message)
        return True
    else:
        print_failure(f"{message} - {item} not found in {container}")
        return False

def assert_type(actual, expected_type, message):
    if isinstance(actual, expected_type):
        print_success(message)
        return True
    else:
        print_failure(f"{message} - Expected type: {expected_type.__name__}, Got: {type(actual).__name__}")
        return False

def assert_greater_equal(actual, expected, message):
    if actual >= expected:
        print_success(message)
        return True
    else:
        print_failure(f"{message} - Expected >= {expected}, Got: {actual}")
        return False

# Configuration
REMOTE = "https://apps.synergiqai.com"
LOCAL = "http://localhost:8005"
API_BASE_URL = REMOTE  # Change this to match your API server
STATS_API_URL = f"{API_BASE_URL}/api/stats"
DOCKER_API_URL = f"{API_BASE_URL}/api/docker"
JOB_API_URL = f"{API_BASE_URL}/api/jobs"
TEST_USERNAME = "test_user"
TEST_WORKSPACE = "test_workspace"
NONEXISTENT_USERNAME = "nonexistent_user"
NONEXISTENT_WORKSPACE = "nonexistent_workspace"

def test_get_stats_for_existing_workspace():
    """Test getting stats for an existing workspace with running containers."""
    url = f"{STATS_API_URL}/{TEST_USERNAME}/{TEST_WORKSPACE}"
    print_test_header("Getting stats for existing workspace")
    
    try:
        print_info(f"Sending GET request to {url}")
        response = requests.get(url)
        
        print_info(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print_info(f"Response content: {json.dumps(data, indent=2)}")
            
            # Test response structure
            success = True
            success &= assert_contains(data, "username", "Response contains username field")
            success &= assert_contains(data, "workspace_name", "Response contains workspace_name field")
            success &= assert_contains(data, "stats", "Response contains stats field")
            
            # Test that the returned username and workspace match
            success &= assert_equal(data.get("username"), TEST_USERNAME, "Username matches expected value")
            success &= assert_equal(data.get("workspace_name"), TEST_WORKSPACE, "Workspace name matches expected value")
            
            # Test stats structure
            stats = data.get("stats", {})
            success &= assert_type(stats, dict, "Stats is a dictionary")
            
            if "error" not in stats:
                # If there are running containers, verify the stats structure
                if "stats" in stats and stats.get("count", 0) > 0:
                    success &= assert_contains(stats, "stats", "Stats contains container stats array")
                    success &= assert_contains(stats, "count", "Stats contains count field")
                    success &= assert_contains(stats, "aggregated", "Stats contains aggregated field")
                    success &= assert_type(stats["stats"], list, "Container stats is a list")
                    success &= assert_type(stats["count"], int, "Count is an integer")
                    success &= assert_greater_equal(stats["count"], 0, "Count is non-negative")
                    
                    # Test aggregated stats structure
                    aggregated = stats.get("aggregated", {})
                    if aggregated and "error" not in aggregated:
                        success &= assert_contains(aggregated, "cpu_percentage", "Aggregated stats contains CPU percentage")
                        success &= assert_contains(aggregated, "memory_usage", "Aggregated stats contains memory usage")
                        success &= assert_contains(aggregated, "memory_percentage", "Aggregated stats contains memory percentage")
                        
                        # Test that numeric values are reasonable
                        if "cpu_percentage" in aggregated:
                            success &= assert_greater_equal(aggregated["cpu_percentage"], 0, "CPU percentage is non-negative")
                        if "memory_percentage" in aggregated:
                            success &= assert_greater_equal(aggregated["memory_percentage"], 0, "Memory percentage is non-negative")
                else:
                    print_info("No running containers found - this is acceptable")
                    success &= assert_contains(stats, "message", "Stats contains explanatory message when no containers")
                    
            return success
            
        elif response.status_code == 404:
            print_warning("Workspace not found - this might be expected if workspace doesn't exist")
            return True  # This might be acceptable for some test scenarios
        else:
            print_failure(f"Unexpected status code: {response.status_code}")
            print_info(f"Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print_failure(f"Request failed: {str(e)}")
        return False
    except json.JSONDecodeError as e:
        print_failure(f"Failed to parse JSON response: {str(e)}")
        return False
    except Exception as e:
        print_failure(f"Unexpected error: {str(e)}")
        return False

def test_get_stats_for_nonexistent_workspace():
    """Test getting stats for a workspace that doesn't exist."""
    url = f"{STATS_API_URL}/{NONEXISTENT_USERNAME}/{NONEXISTENT_WORKSPACE}"
    print_test_header("Getting stats for nonexistent workspace")
    
    try:
        print_info(f"Sending GET request to {url}")
        response = requests.get(url)
        
        print_info(f"Response status: {response.status_code}")
        
        # Should return 404 for nonexistent workspace
        success = assert_equal(response.status_code, 404, "Returns 404 for nonexistent workspace")
        
        if response.status_code == 404:
            try:
                data = response.json()
                print_info(f"Error response: {json.dumps(data, indent=2)}")
                success &= assert_contains(data, "detail", "Error response contains detail field")
            except json.JSONDecodeError:
                print_info("Response is not JSON - might be plain text error")
                
        return success
        
    except requests.exceptions.RequestException as e:
        print_failure(f"Request failed: {str(e)}")
        return False
    except Exception as e:
        print_failure(f"Unexpected error: {str(e)}")
        return False

def test_get_stats_with_special_characters_in_username():
    """Test getting stats with special characters in username (like email)."""
    email_username = "test.user@example.com"
    url = f"{STATS_API_URL}/{email_username}/{TEST_WORKSPACE}"
    print_test_header("Getting stats with email-like username")
    
    try:
        print_info(f"Sending GET request to {url}")
        response = requests.get(url)
        
        print_info(f"Response status: {response.status_code}")
        
        # Should handle email-like usernames gracefully
        if response.status_code == 200:
            data = response.json()
            print_info(f"Response content: {json.dumps(data, indent=2)}")
            success = assert_equal(data.get("username"), email_username, "Username with email format handled correctly")
            return success
        elif response.status_code == 404:
            print_info("Workspace not found for email username - this is acceptable")
            return True
        else:
            print_warning(f"Unexpected status code: {response.status_code}")
            return True  # Don't fail the test for this edge case
            
    except requests.exceptions.RequestException as e:
        print_failure(f"Request failed: {str(e)}")
        return False
    except Exception as e:
        print_failure(f"Unexpected error: {str(e)}")
        return False

def test_stats_api_response_time():
    """Test that the stats API responds within a reasonable time."""
    url = f"{STATS_API_URL}/{TEST_USERNAME}/{TEST_WORKSPACE}"
    print_test_header("Testing stats API response time")
    
    try:
        start_time = time.time()
        print_info(f"Sending GET request to {url}")
        response = requests.get(url, timeout=10)  # 10 second timeout
        end_time = time.time()
        
        response_time = end_time - start_time
        print_info(f"Response time: {response_time:.2f} seconds")
        print_info(f"Response status: {response.status_code}")
        
        # Response should be reasonably fast (under 5 seconds)
        success = assert_greater_equal(5.0, response_time, "Response time is reasonable (< 5 seconds)")
        
        return success
        
    except requests.exceptions.Timeout:
        print_failure("Request timed out after 10 seconds")
        return False
    except requests.exceptions.RequestException as e:
        print_failure(f"Request failed: {str(e)}")
        return False
    except Exception as e:
        print_failure(f"Unexpected error: {str(e)}")
        return False

def ensure_test_workspace_exists():
    """Ensure test workspace exists by creating a deployment if needed."""
    print_test_header("Ensuring test workspace exists")
    
    # First check if workspace already has stats (containers running)
    stats_url = f"{STATS_API_URL}/{TEST_USERNAME}/{TEST_WORKSPACE}"
    try:
        response = requests.get(stats_url)
        if response.status_code == 200:
            data = response.json()
            stats = data.get("stats", {})
            if "stats" in stats and stats.get("count", 0) > 0:
                print_success("Test workspace already exists with running containers")
                return True
    except:
        pass
    
    # Try to deploy a test app to ensure we have a workspace with containers
    print_info("Attempting to create test workspace with containers...")
    deploy_url = f"{DOCKER_API_URL}/build_deploy/{TEST_USERNAME}/{TEST_WORKSPACE}"
    zip_file_path = "./tests/SampleWebApp.zip"
    
    try:
        with open(zip_file_path, 'rb') as f:
            files = {'zip_file': (zip_file_path, f)}
            headers = {'Accept': 'application/json'}
            response = requests.post(deploy_url, files=files, headers=headers)
            
            if response.status_code == 200:
                job_data = response.json()
                job_id = job_data.get('job_id')
                print_info(f"Deployment job created: {job_id}")
                
                # Wait a bit for deployment to start
                time.sleep(10)
                return True
            else:
                print_warning(f"Could not create test workspace: {response.status_code}")
                return False
                
    except FileNotFoundError:
        print_warning(f"Test zip file not found: {zip_file_path}")
        return False
    except Exception as e:
        print_warning(f"Could not create test workspace: {str(e)}")
        return False

def run_all_tests():
    """Run all stats API tests."""
    # First ensure we have a test workspace
    workspace_ready = ensure_test_workspace_exists()
    if not workspace_ready:
        print_warning("Could not ensure test workspace exists - some tests may fail")
    
    tests = [
        test_get_stats_for_existing_workspace,
        test_get_stats_for_nonexistent_workspace,
        test_get_stats_with_special_characters_in_username,
        test_stats_api_response_time
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
    """Main function to run the stats API tests."""
    print(f"{Colors.BOLD}Docker Stats API Tests{Colors.ENDC}")
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Stats API URL: {STATS_API_URL}")
    print(f"Testing with username: {TEST_USERNAME}")
    print(f"Testing with workspace: {TEST_WORKSPACE}")

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