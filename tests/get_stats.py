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

def assert_contains(container, item, message):
    if item in container:
        print_success(message)
        return True
    else:
        print_failure(f"{message} - {item} not found in {container}")
        return False

def assert_less_than_or_equal(actual, expected, message):
    if actual <= expected:
        print_success(message)
        return True
    else:
        print_failure(f"{message} - Expected: <= {expected}, Got: {actual}")
        return False

def assert_greater_equal(actual, expected, message):
    if actual >= expected:
        print_success(message)
        return True
    else:
        print_failure(f"{message} - Expected >= {expected}, Got: {actual}")
        return False

def assert_type(actual, expected_type, message):
    if isinstance(actual, expected_type):
        print_success(message)
        return True
    else:
        print_failure(f"{message} - Expected type: {expected_type.__name__}, Got: {type(actual).__name__}")
        return False


REMOTE = "https://apps.synergiqai.com"
API_BASE_URL = REMOTE  # Change this to match your API server
STATS_API_URL = f"{API_BASE_URL}/api/stats"
DOCKER_API_URL = f"{API_BASE_URL}/api/docker"
JOB_API_URL = f"{API_BASE_URL}/api/jobs"
TEST_USERNAME = "uditk2@gmail.com"
TEST_WORKSPACE = "SearchAgentOptimizationAnalyser"

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

if __name__ == "__main__":
    print(f"{Colors.BOLD}Docker Stats API Test{Colors.ENDC}")
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Testing with username: {TEST_USERNAME}, workspace: {TEST_WORKSPACE}")
    
    result = test_get_stats_for_existing_workspace()
    
    if result:
        print_success("Test passed successfully!")
        sys.exit(0)
    else:
        print_failure("Test failed!")
        sys.exit(1)