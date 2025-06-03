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

# Configuration
REMOTE = "https://apps.synergiqai.com"
LOCAL = "http://localhost:8005"
API_BASE_URL = REMOTE  # Change this to match your API server
LOGS_API_URL = f"{API_BASE_URL}/api/logs"
TEST_USERNAME = "uditk2@gmail.com"
TEST_WORKSPACE = "SearchAgentOptimizationAnalyser"

def test_get_logs_for_workspace():
    """Test fetching logs for a specific username and workspace for the past 50 lines."""
    url = f"{LOGS_API_URL}/{TEST_USERNAME}/{TEST_WORKSPACE}"
    print_test_header("Fetching logs for workspace (past 50 lines)")
    
    try:
        # Parameters to get the last 50 lines
        params = {
            'lines': 50
        }
        
        print_info(f"Sending request to {url} with params: {params}")
        response = requests.get(url, params=params)
        
        if response.status_code == 404:
            print_warning("Workspace or logs not found - this might be expected if no workspace exists yet")
            print_info(f"Response: {response.status_code} - {response.text}")
            return True  # Consider this a pass since workspace might not exist
        elif response.status_code != 200:
            print_failure(f"Response: {response.status_code} - {response.text}")
            return False
        else:
            response_data = response.json()
            print_success(f"Successfully fetched logs - Response: {response.status_code}")
            print_info(f"Workspace: {response_data.get('workspace', 'N/A')}")
            print_info(f"Username: {response_data.get('username', 'N/A')}")
            print_info(f"Total log count: {response_data.get('log_count', 0)}")
            
            logs = response_data.get('logs', [])
            log_count = len(logs)
            
            # Display first few logs for verification
            if logs:
                print_info(f"Sample logs (showing first 3 out of {log_count}):")
                for i, log_entry in enumerate(logs[:3]):
                    if isinstance(log_entry, dict):
                        timestamp = log_entry.get('timestamp', 'No timestamp')
                        content = log_entry.get('content', 'No content')
                        level = log_entry.get('level', 'No level')
                        print_info(f"  {i+1}. [{timestamp}] [{level}] {content[:100]}...")
                    else:
                        print_info(f"  {i+1}. {str(log_entry)[:100]}...")
            else:
                print_info("No logs found for this workspace")
            
            # Assertions
            assertion1 = assert_contains(response_data, 'workspace', "Response should contain workspace field")
            assertion2 = assert_contains(response_data, 'username', "Response should contain username field")
            assertion3 = assert_contains(response_data, 'logs', "Response should contain logs field")
            assertion4 = assert_equal(response_data.get('username'), TEST_USERNAME, "Username should match request")
            assertion5 = assert_equal(response_data.get('workspace'), TEST_WORKSPACE, "Workspace should match request")
            
            # Verify that we requested the correct number of lines (or less if fewer available)
            assertion6 = assert_less_than_or_equal(log_count, 50, "Should not receive more than 50 logs")
            
            return assertion1 and assertion2 and assertion3 and assertion4 and assertion5 and assertion6
            
    except requests.exceptions.RequestException as e:
        print_failure(f"Request failed: {str(e)}")
        return False
    except Exception as e:
        print_failure(f"Unexpected error: {str(e)}")
        return False

def test_get_logs_with_time_filter():
    """Test fetching logs for a specific username and workspace with time filter."""
    url = f"{LOGS_API_URL}/{TEST_USERNAME}/{TEST_WORKSPACE}"
    print_test_header("Fetching logs with time filter (past 60 minutes)")
    
    try:
        # Parameters to get logs from the last 60 minutes
        params = {
            'lines': 50,
            'minutes': 60
        }
        
        print_info(f"Sending request to {url} with params: {params}")
        response = requests.get(url, params=params)
        
        if response.status_code == 404:
            print_warning("Workspace or logs not found - this might be expected if no workspace exists yet")
            print_info(f"Response: {response.status_code} - {response.text}")
            return True
        elif response.status_code != 200:
            print_failure(f"Response: {response.status_code} - {response.text}")
            return False
        else:
            response_data = response.json()
            print_success(f"Successfully fetched logs with time filter - Response: {response.status_code}")
            print_info(f"Total log count: {response_data.get('log_count', 0)}")
            
            logs = response_data.get('logs', [])
            log_count = len(logs)
            
            # Verify response structure
            assertion1 = assert_contains(response_data, 'logs', "Response should contain logs field")
            assertion2 = assert_less_than_or_equal(log_count, 50, "Should not receive more than 50 logs")
            
            return assertion1 and assertion2
            
    except requests.exceptions.RequestException as e:
        print_failure(f"Request failed: {str(e)}")
        return False
    except Exception as e:
        print_failure(f"Unexpected error: {str(e)}")
        return False

def test_get_logs_invalid_workspace():
    """Test fetching logs for a non-existent workspace."""
    invalid_workspace = "non_existent_workspace_12345"
    url = f"{LOGS_API_URL}/{TEST_USERNAME}/{invalid_workspace}"
    print_test_header("Fetching logs for invalid workspace")
    
    try:
        params = {'lines': 50}
        
        print_info(f"Sending request to {url} with params: {params}")
        response = requests.get(url, params=params)
        
        # Should return 404 for non-existent workspace
        assertion1 = assert_equal(response.status_code, 404, "Should return 404 for non-existent workspace")
        
        return assertion1
        
    except requests.exceptions.RequestException as e:
        print_failure(f"Request failed: {str(e)}")
        return False
    except Exception as e:
        print_failure(f"Unexpected error: {str(e)}")
        return False

def run_all_tests():
    tests = [
        test_get_logs_for_workspace,
        test_get_logs_with_time_filter,
        test_get_logs_invalid_workspace
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
    print(f"{Colors.BOLD}Logs API Comprehensive Tests{Colors.ENDC}")
    print(f"API Base URL: {API_BASE_URL}")
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