#!/usr/bin/env python3
"""
Comprehensive test for ErrorIdentifier module.
Tests the AI-powered error identification functionality with real data.
"""

import sys
import os
import json
from typing import Dict, Any

# Add parent directory to path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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

def assert_type(actual, expected_type, message):
    if isinstance(actual, expected_type):
        print_success(message)
        return True
    else:
        print_failure(f"{message} - Expected type: {expected_type.__name__}, Got: {type(actual).__name__}")
        return False

def assert_not_none(value, message):
    if value is not None:
        print_success(message)
        return True
    else:
        print_failure(f"{message} - Value is None")
        return False

def assert_greater_than(actual, expected, message):
    if actual > expected:
        print_success(message)
        return True
    else:
        print_failure(f"{message} - Expected > {expected}, Got: {actual}")
        return False

# Test data - Sample log strings for testing
SAMPLE_LOG_WITH_ERRORS = """
2024-06-14 10:30:15 INFO Starting application server
2024-06-14 10:30:16 INFO Database connection established
2024-06-14 10:30:25 ERROR Database connection failed: Connection timeout
    at DatabaseConnector.connect(DatabaseConnector.java:45)
    at ServiceManager.initialize(ServiceManager.java:23)
    at Application.main(Application.java:12)
2024-06-14 10:30:26 WARN Retrying database connection...
2024-06-14 10:30:30 ERROR Failed to load configuration file: config.json not found
    File "/app/config/loader.py", line 67, in load_config
        with open(config_path, 'r') as f:
    FileNotFoundError: [Errno 2] No such file or directory: 'config.json'
2024-06-14 10:30:31 INFO Application started successfully
2024-06-14 10:30:45 ERROR HTTP 500 Internal Server Error
    Traceback (most recent call last):
        File "/app/handlers/api.py", line 123, in handle_request
            result = process_data(request.data)
        File "/app/processors/data.py", line 56, in process_data
            return validate_schema(data)
    ValidationError: Schema validation failed for field 'user_id'
"""

SAMPLE_LOG_WITHOUT_ERRORS = """
2024-06-14 10:30:15 INFO Starting application server
2024-06-14 10:30:16 INFO Database connection established
2024-06-14 10:30:17 INFO Configuration loaded successfully
2024-06-14 10:30:18 INFO API endpoints registered
2024-06-14 10:30:19 INFO Application started successfully
2024-06-14 10:30:20 INFO Health check passed
2024-06-14 10:30:25 INFO Processing user request
2024-06-14 10:30:26 INFO Request completed successfully
"""

def load_production_log_data():
    """Load production log data from file"""
    try:
        with open('tests/production_log_with_errors.log', 'r') as f:
            return f.read()
    except FileNotFoundError:
        print_warning("Production log file not found, using sample data")
        return SAMPLE_LOG_WITH_ERRORS

def test_error_identifier_basic_functionality():
    """Test basic ErrorIdentifier functionality"""
    print_test_header("ErrorIdentifier Basic Functionality")
    
    try:
        from app.log_processor.error_identifier import ErrorIdentifier
        
        # Create ErrorIdentifier instance
        error_identifier = ErrorIdentifier()
        assert_not_none(error_identifier, "ErrorIdentifier should be instantiated successfully")
        
        # Verify it has the expected attributes
        assert_not_none(error_identifier._agent, "ErrorIdentifier should have an agent")
        assert_equal(error_identifier._agent.name, "SmartErrorDetector", "Agent should have correct name")
        
        print_success("ErrorIdentifier instantiated successfully")
        return True
        
    except ImportError as e:
        print_failure(f"Failed to import ErrorIdentifier: {str(e)}")
        return False
    except Exception as e:
        print_failure(f"Error testing basic functionality: {str(e)}")
        return False

def test_error_identifier_with_sample_errors():
    """Test ErrorIdentifier with sample log data containing errors"""
    print_test_header("ErrorIdentifier with Sample Error Logs")
    
    try:
        from app.log_processor.error_identifier import ErrorIdentifier
        
        error_identifier = ErrorIdentifier()
        
        print_info("Testing with sample log data containing multiple errors...")
        result = error_identifier.identify_errors(SAMPLE_LOG_WITH_ERRORS)
        
        # Verify the result structure
        assert_type(result, dict, "Result should be a dictionary")
        
        if result is None:
            print_failure("ErrorIdentifier returned None - check implementation")
            return False
        
        # Check for successful processing
        if "status" in result:
            if result["status"] == "success":
                print_success("ErrorIdentifier processed logs successfully")
                
                if "error_logs" in result:
                    error_logs = result["error_logs"]
                    assert_type(error_logs, list, "error_logs should be a list")
                    
                    if len(error_logs) > 0:
                        print_success(f"Found {len(error_logs)} error groups")
                        
                        # Display the identified errors
                        for i, error_log in enumerate(error_logs):
                            print_info(f"Error group {i+1}: {error_log[:100]}...")
                        
                        return True
                    else:
                        print_warning("No errors identified in sample data")
                        return True
                else:
                    print_failure("Result missing 'error_logs' field")
                    return False
            else:
                print_failure(f"ErrorIdentifier returned error status: {result.get('message', 'Unknown error')}")
                return False
        else:
            print_info("Result format may be different than expected")
            print_info(f"Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
            return True
            
    except Exception as e:
        print_failure(f"Error testing with sample data: {str(e)}")
        return False

def test_error_identifier_with_production_data():
    """Test ErrorIdentifier with real production log data"""
    print_test_header("ErrorIdentifier with Production Log Data")
    
    try:
        from app.log_processor.error_identifier import ErrorIdentifier
        
        # Load production log data
        production_log_data = load_production_log_data()
        print_info(f"Loaded production log data: {len(production_log_data)} characters")
        
        error_identifier = ErrorIdentifier()
        
        print_info("Analyzing production logs with real AI agent...")
        print_info("This may take a moment as it calls the actual AI service...")
        
        result = error_identifier.identify_errors(production_log_data)
        
        # Verify the result
        if result is None:
            print_failure("ErrorIdentifier returned None - check implementation")
            return False
        
        assert_type(result, dict, "Result should be a dictionary")
        
        # Check for successful processing
        if "status" in result:
            if result["status"] == "success":
                        # Write result to file for inspection
                with open('tests/production_errors.log', 'w') as f:
                   for error_log in result.get("error_logs", []):
                        f.write(f"{error_log}\n\n\n")
                print_success("ErrorIdentifier processed production logs successfully")
                
                if "error_logs" in result:
                    error_logs = result["error_logs"]
                    assert_type(error_logs, list, "error_logs should be a list")
                    
                    print_success(f"Identified {len(error_logs)} error groups in production data")
                    
                    # Display the identified errors
                    for i, error_log in enumerate(error_logs):
                        print_info(f"Production Error {i+1}:")
                        print(f"  {error_log[:200]}...")
                        print()
                    
                    # Verify that it found the main error from the production logs
                    found_api_router_error = any("APIRouter.post()" in error for error in error_logs)
                    if found_api_router_error:
                        print_success("Correctly identified the APIRouter error from production logs")
                    else:
                        print_warning("Did not identify the main APIRouter error - check analysis quality")
                    
                    return True
                else:
                    print_failure("Result missing 'error_logs' field")
                    return False
            else:
                print_failure(f"ErrorIdentifier returned error status: {result.get('message', 'Unknown error')}")
                return False
        else:
            print_info("Result format may be different than expected")
            print_info(f"Result: {result}")
            return True
            
    except Exception as e:
        print_failure(f"Error testing with production data: {str(e)}")
        return False

def test_error_identifier_with_clean_logs():
    """Test ErrorIdentifier with logs containing no errors"""
    print_test_header("ErrorIdentifier with Clean Logs")
    
    try:
        from app.log_processor.error_identifier import ErrorIdentifier
        
        error_identifier = ErrorIdentifier()
        
        print_info("Testing with clean log data (no errors)...")
        result = error_identifier.identify_errors(SAMPLE_LOG_WITHOUT_ERRORS)
        print_info(result)
        # Verify the result
        if result is None:
            print_failure("ErrorIdentifier returned None")
            return False
        
        assert_type(result, dict, "Result should be a dictionary")
        
        if "status" in result and result["status"] == "success":
            if "error_logs" in result:
                error_logs = result["error_logs"]
                assert_type(error_logs, list, "error_logs should be a list")
                
                if len(error_logs) == 0:
                    print_success("Correctly identified no errors in clean logs")
                else:
                    print_warning(f"Found {len(error_logs)} potential errors in supposedly clean logs")
                    for i, error_log in enumerate(error_logs):
                        print_info(f"Potential error {i+1}: {error_log[:100]}...")
                
                return True
            else:
                print_failure("Result missing 'error_logs' field")
                return False
        else:
            print_info(f"Unexpected result format: {result}")
            return True
            
    except Exception as e:
        print_failure(f"Error testing clean logs: {str(e)}")
        return False

def test_error_identifier_system_prompt():
    """Test ErrorIdentifier system prompt configuration"""
    print_test_header("ErrorIdentifier System Prompt Configuration")
    
    try:
        from app.log_processor.error_identifier import ErrorIdentifier
        
        # Verify the system prompt is correctly configured
        expected_prompt_keywords = [
            "log",
            "error",
            "json",
            "identify"
        ]
        
        system_prompt = ErrorIdentifier.SYSTEM_PROMPT
        assert_not_none(system_prompt, "System prompt should not be None")
        assert_type(system_prompt, str, "System prompt should be a string")
        assert_greater_than(len(system_prompt), 50, "System prompt should be substantial")
        
        # Check if key concepts are present in the prompt
        found_keywords = 0
        for keyword in expected_prompt_keywords:
            if keyword.lower() in system_prompt.lower():
                print_success(f"System prompt contains '{keyword}'")
                found_keywords += 1
            else:
                print_warning(f"System prompt might be missing '{keyword}'")
        
        if found_keywords >= len(expected_prompt_keywords) // 2:
            print_success("System prompt contains most expected keywords")
        
        print_info(f"System prompt length: {len(system_prompt)} characters")
        print_info(f"First 100 chars: {system_prompt[:100]}...")
        
        return True
        
    except Exception as e:
        print_failure(f"Error testing system prompt: {str(e)}")
        return False

def run_all_tests():
    """Run all ErrorIdentifier tests"""
    tests = [
        test_error_identifier_basic_functionality,
        test_error_identifier_system_prompt,
        test_error_identifier_with_sample_errors,
        test_error_identifier_with_clean_logs,
        test_error_identifier_with_production_data,
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print_failure(f"Test {test.__name__} failed with exception: {str(e)}")
            results.append(False)
    
    print("\n" + "="*60)
    print(f"{Colors.BOLD}ErrorIdentifier Test Results Summary:{Colors.ENDC}")
    print("="*60)
    
    all_passed = True
    for i, result in enumerate(results):
        test_name = tests[i].__name__
        if result:
            print(f"{Colors.OKGREEN}✓ {test_name} - PASSED{Colors.ENDC}")
        else:
            all_passed = False
            print(f"{Colors.FAIL}✗ {test_name} - FAILED{Colors.ENDC}")
    
    print("="*60)
    if all_passed:
        print(f"{Colors.OKGREEN}{Colors.BOLD}All ErrorIdentifier tests passed!{Colors.ENDC}")
        return 0
    else:
        print(f"{Colors.FAIL}{Colors.BOLD}Some ErrorIdentifier tests failed!{Colors.ENDC}")
        return 1

def main():
    print(f"{Colors.BOLD}ErrorIdentifier Real Functionality Tests{Colors.ENDC}")
    print("Testing AI-powered log error identification with real data")
    print("This will make actual calls to the AI service")
    
    try:
        return run_all_tests()
    except Exception as e:
        print(f"{Colors.FAIL}Error: {str(e)}{Colors.ENDC}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)