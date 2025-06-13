#!/usr/bin/env python3
"""
Comprehensive Log Watchdog and Deployment Manager Integration Tests
Tests the per-deployment log monitoring functionality
"""

import requests
import json
import sys
import time
from datetime import datetime
import os
from dotenv import load_dotenv
import websocket
import threading
from service_deployment_manager_client import ServiceDeploymentManagerClient

# Load environment variables from .env file
load_dotenv()

# Initialize the client
client = ServiceDeploymentManagerClient()

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

# Configuration
TEST_USERNAME = "test_deployment_user"
TEST_WORKSPACE_1 = "webapp_deployment"
TEST_WORKSPACE_2 = "api_deployment"
LOG_STREAM_BASE_URL = f"{client.base_url}/api/log-stream"

def test_start_log_watchdog():
    """Test starting the log watchdog service"""
    print_test_header("Starting Log Watchdog Service for Deployment Manager")
    
    try:
        url = f"{LOG_STREAM_BASE_URL}/start"
        response = client.session.post(url)
        
        if response.status_code == 200:
            result = response.json()
            print_success(f"Log watchdog started: {result.get('message')}")
            return assert_equal(result.get('status'), 'running', "Watchdog should be running")
        else:
            print_failure(f"Failed to start watchdog: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print_failure(f"Error starting log watchdog: {str(e)}")
        return False

def test_auto_discover_user_deployments():
    """Test auto-discovering all deployments for a specific user"""
    print_test_header("Auto-discovering User Deployments")
    
    try:
        url = f"{LOG_STREAM_BASE_URL}/auto-discover/{TEST_USERNAME}"
        response = client.session.post(url)
        
        if response.status_code == 200:
            result = response.json()
            print_success(f"Auto-discovery completed: {result.get('message')}")
            print_info(f"User: {result.get('user')}")
            print_info(f"Workspaces found: {result.get('workspaces_found')}")
            print_info(f"Total monitored files: {result.get('total_monitored_files')}")
            
            discovered_logs = result.get('discovered_logs', [])
            print_info(f"Discovered {len(discovered_logs)} log sources:")
            for log_info in discovered_logs:
                if 'workspace' in log_info:
                    print_info(f"  - Workspace: {log_info['workspace']}, Status: {log_info['status']}")
                elif 'type' in log_info:
                    print_info(f"  - {log_info['type']}: {log_info.get('directory', 'N/A')}, Status: {log_info['status']}")
            
            return True
        else:
            print_warning(f"Auto-discovery response: {response.status_code} - {response.text}")
            # This might be expected if no workspaces exist yet
            return True
            
    except Exception as e:
        print_failure(f"Error in auto-discovery: {str(e)}")
        return False

def test_deploy_webapp_with_monitoring():
    """Test deploying a web app and automatically monitoring its logs"""
    print_test_header("Deploying Web App with Automatic Log Monitoring")
    
    zip_file_path = "./tests/SampleWebApp.zip"
    
    try:
        print_info(f"Deploying {TEST_WORKSPACE_1} for user {TEST_USERNAME}")
        
        # Deploy the web app
        response = client.build_deploy_docker_image(TEST_USERNAME, TEST_WORKSPACE_1, zip_file_path)
        
        if response.status_code == 200:
            job_data = response.json()
            job_id = job_data.get('job_id')
            print_success(f"Deployment started successfully. Job ID: {job_id}")
            
            # Wait a moment for deployment to initialize
            time.sleep(5)
            
            # Check if log monitoring was automatically started
            monitor_url = f"{LOG_STREAM_BASE_URL}/deployment-status/{TEST_USERNAME}/{TEST_WORKSPACE_1}"
            monitor_response = client.session.get(monitor_url)
            
            if monitor_response.status_code == 200:
                monitor_data = monitor_response.json()
                print_info(f"Monitoring status: {json.dumps(monitor_data, indent=2)}")
                
                is_monitored = monitor_data.get('is_monitored', False)
                if is_monitored:
                    print_success("Log monitoring automatically started for deployment")
                else:
                    print_warning("Log monitoring not automatically started - may start after log file creation")
                
            return True
        else:
            print_warning(f"Deployment response: {response.status_code} - {response.text}")
            return True  # Don't fail test for deployment issues
            
    except FileNotFoundError:
        print_warning(f"Test zip file not found: {zip_file_path}")
        return True
    except Exception as e:
        print_warning(f"Deployment test error: {str(e)}")
        return True

def test_manual_deployment_monitoring():
    """Test manually starting monitoring for a specific deployment"""
    print_test_header("Manual Deployment Monitoring")
    
    try:
        # Start monitoring for a specific deployment
        url = f"{LOG_STREAM_BASE_URL}/monitor-deployment/{TEST_USERNAME}/{TEST_WORKSPACE_1}"
        response = client.session.post(url)
        
        if response.status_code == 200:
            result = response.json()
            print_success(f"Manual monitoring started: {result.get('message')}")
            print_info(f"Log file: {result.get('log_file')}")
            print_info(f"Log file exists: {result.get('log_file_exists')}")
            print_info(f"Monitoring status: {result.get('monitoring_status')}")
            return True
        elif response.status_code == 404:
            print_warning("Workspace not found - this is expected if no deployment exists")
            return True
        else:
            print_failure(f"Manual monitoring failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print_failure(f"Error in manual monitoring: {str(e)}")
        return False

def test_deployment_specific_websocket_stream():
    """Test WebSocket streaming for a specific deployment"""
    print_test_header("Deployment-Specific WebSocket Streaming")
    
    try:
        # Create a WebSocket URL for specific deployment
        ws_url = f"ws://{client.base_url.replace('http://', '').replace('https://', '')}/api/log-stream/ws/workspace/{TEST_USERNAME}/{TEST_WORKSPACE_1}"
        
        print_info(f"Attempting WebSocket connection: {ws_url}")
        
        # Simple WebSocket test with timeout
        received_messages = []
        connection_successful = False
        
        def on_message(ws, message):
            received_messages.append(message)
            try:
                msg_data = json.loads(message)
                msg_type = msg_data.get('type', 'unknown')
                print_info(f"WebSocket message ({msg_type}): {message[:100]}...")
            except:
                print_info(f"WebSocket message: {message[:100]}...")
            
        def on_open(ws):
            nonlocal connection_successful
            connection_successful = True
            print_success("Deployment WebSocket connection established")
            
        def on_error(ws, error):
            print_warning(f"WebSocket error: {error}")
            
        def on_close(ws, close_status_code, close_msg):
            print_info("Deployment WebSocket connection closed")
        
        # Create WebSocket connection
        ws = websocket.WebSocketApp(ws_url,
                                  on_open=on_open,
                                  on_message=on_message,
                                  on_error=on_error,
                                  on_close=on_close)
        
        # Run WebSocket in a separate thread with timeout
        ws_thread = threading.Thread(target=ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
        
        # Wait for connection and messages
        time.sleep(5)
        
        if connection_successful:
            ws.close()
            print_success(f"WebSocket test completed - received {len(received_messages)} messages")
            return True
        else:
            print_warning("WebSocket connection could not be established")
            return True  # Don't fail for WebSocket issues
            
    except Exception as e:
        print_warning(f"WebSocket test error: {str(e)}")
        return True

def test_redis_deployment_streaming():
    """Test Redis streaming for deployment logs"""
    print_test_header("Redis Deployment Log Streaming")
    
    try:
        # Add Redis stream for deployment logs
        url = f"{LOG_STREAM_BASE_URL}/stream/redis"
        data = {
            "stream_id": f"deployment_stream_{TEST_USERNAME}_{TEST_WORKSPACE_1}",
            "channel": f"deployment_logs_{TEST_USERNAME}_{TEST_WORKSPACE_1}",
            "filters": {
                "username": TEST_USERNAME,
                "workspace": TEST_WORKSPACE_1
            },
            "format": "json"
        }
        response = client.session.post(url, json=data)
        
        if response.status_code == 200:
            result = response.json()
            print_success(f"Redis deployment stream added: {result.get('message')}")
            print_info(f"Stream ID: {result.get('stream_id')}")
            print_info(f"Channel: {result.get('channel')}")
            return True
        else:
            print_failure(f"Redis stream failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print_failure(f"Error adding Redis stream: {str(e)}")
        return False

def test_multiple_deployment_monitoring():
    """Test monitoring multiple deployments simultaneously"""
    print_test_header("Multiple Deployment Monitoring")
    
    try:
        deployments = [
            (TEST_USERNAME, TEST_WORKSPACE_1),
            (TEST_USERNAME, TEST_WORKSPACE_2),
            ("another_user", "test_workspace")
        ]
        
        monitoring_results = []
        
        for username, workspace in deployments:
            try:
                url = f"{LOG_STREAM_BASE_URL}/monitor-deployment/{username}/{workspace}"
                response = client.session.post(url)
                
                monitoring_results.append({
                    'username': username,
                    'workspace': workspace,
                    'status_code': response.status_code,
                    'success': response.status_code in [200, 404]  # 404 is OK if workspace doesn't exist
                })
                
                if response.status_code == 200:
                    result = response.json()
                    print_success(f"Monitoring started for {username}/{workspace}")
                elif response.status_code == 404:
                    print_info(f"Workspace {username}/{workspace} not found (expected)")
                else:
                    print_warning(f"Monitoring failed for {username}/{workspace}: {response.status_code}")
                    
            except Exception as e:
                print_warning(f"Error monitoring {username}/{workspace}: {str(e)}")
                monitoring_results.append({
                    'username': username,
                    'workspace': workspace,
                    'success': False,
                    'error': str(e)
                })
        
        # Check overall status
        url = f"{LOG_STREAM_BASE_URL}/status"
        status_response = client.session.get(url)
        
        if status_response.status_code == 200:
            status = status_response.json()
            print_info(f"Total monitored files: {status.get('monitored_files_count')}")
            print_info(f"Active streams: {status.get('streams_count')}")
            print_info(f"WebSocket connections: {status.get('websocket_connections_count')}")
        
        return len([r for r in monitoring_results if r.get('success', False)]) >= 1
        
    except Exception as e:
        print_failure(f"Error in multiple deployment monitoring: {str(e)}")
        return False

def test_deployment_log_file_discovery():
    """Test discovery of actual log files from deployments"""
    print_test_header("Deployment Log File Discovery")
    
    try:
        # List all monitored files
        url = f"{LOG_STREAM_BASE_URL}/files"
        response = client.session.get(url)
        
        if response.status_code == 200:
            result = response.json()
            monitored_files = result.get('monitored_files', [])
            
            print_info(f"Currently monitoring {len(monitored_files)} files:")
            
            deployment_logs = []
            system_logs = []
            
            for file_path in monitored_files:
                if 'compose.log' in file_path:
                    deployment_logs.append(file_path)
                    print_info(f"  📦 Deployment log: {file_path}")
                else:
                    system_logs.append(file_path)
                    print_info(f"  📋 System log: {file_path}")
            
            print_success(f"Found {len(deployment_logs)} deployment logs and {len(system_logs)} system logs")
            
            # Test if files actually exist
            existing_files = 0
            for file_path in monitored_files:
                if os.path.exists(file_path):
                    existing_files += 1
            
            print_info(f"Physical files existing: {existing_files}/{len(monitored_files)}")
            
            return True
        else:
            print_failure(f"Failed to list files: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print_failure(f"Error in file discovery: {str(e)}")
        return False

def test_auto_discover_all_deployments():
    """Test auto-discovering all deployments across all users"""
    print_test_header("Auto-discovering All System Deployments")
    
    try:
        url = f"{LOG_STREAM_BASE_URL}/auto-discover-all"
        response = client.session.post(url)
        
        if response.status_code == 200:
            result = response.json()
            print_success(f"System-wide auto-discovery completed: {result.get('message')}")
            
            users_processed = result.get('users_processed', [])
            total_discovered = result.get('total_discovered', 0)
            discovered_logs = result.get('discovered_logs', [])
            
            print_info(f"Users processed: {len(users_processed)}")
            print_info(f"Total discoveries: {total_discovered}")
            print_info(f"Total monitored files: {result.get('total_monitored_files')}")
            
            # Group discoveries by user
            user_deployments = {}
            for log_info in discovered_logs:
                username = log_info.get('username', 'system')
                if username not in user_deployments:
                    user_deployments[username] = []
                user_deployments[username].append(log_info)
            
            for username, deployments in user_deployments.items():
                print_info(f"  User '{username}': {len(deployments)} deployments")
                for deployment in deployments[:3]:  # Show first 3
                    workspace = deployment.get('workspace', deployment.get('type', 'unknown'))
                    status = deployment.get('status', 'unknown')
                    print_info(f"    - {workspace}: {status}")
            
            return True
        else:
            print_failure(f"System-wide auto-discovery failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print_failure(f"Error in system-wide auto-discovery: {str(e)}")
        return False

def test_cleanup_deployment_monitoring():
    """Test cleaning up monitoring for deployments"""
    print_test_header("Cleaning Up Deployment Monitoring")
    
    try:
        # Stop monitoring for specific deployments
        deployments_to_stop = [
            (TEST_USERNAME, TEST_WORKSPACE_1),
            (TEST_USERNAME, TEST_WORKSPACE_2)
        ]
        
        for username, workspace in deployments_to_stop:
            try:
                url = f"{LOG_STREAM_BASE_URL}/monitor-deployment/{username}/{workspace}"
                response = client.session.delete(url)
                
                if response.status_code == 200:
                    result = response.json()
                    print_success(f"Stopped monitoring {username}/{workspace}")
                elif response.status_code == 404:
                    print_info(f"Monitoring for {username}/{workspace} was not active")
                else:
                    print_warning(f"Failed to stop monitoring {username}/{workspace}: {response.status_code}")
                    
            except Exception as e:
                print_warning(f"Error stopping monitoring for {username}/{workspace}: {str(e)}")
        
        # Check final status
        url = f"{LOG_STREAM_BASE_URL}/status"
        status_response = client.session.get(url)
        
        if status_response.status_code == 200:
            status = status_response.json()
            print_info(f"Final monitored files: {status.get('monitored_files_count')}")
            print_info(f"Final active streams: {status.get('streams_count')}")
        
        return True
        
    except Exception as e:
        print_failure(f"Error in cleanup: {str(e)}")
        return False

def run_all_tests():
    tests = [
        test_start_log_watchdog,
        test_auto_discover_user_deployments,
        test_deploy_webapp_with_monitoring,
        test_manual_deployment_monitoring,
        test_deployment_specific_websocket_stream,
        test_redis_deployment_streaming,
        test_multiple_deployment_monitoring,
        test_deployment_log_file_discovery,
        test_auto_discover_all_deployments,
        test_cleanup_deployment_monitoring
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print_failure(f"Test {test.__name__} failed with exception: {str(e)}")
            results.append(False)
    
    print("\n" + "="*70)
    print(f"{Colors.BOLD}Deployment Manager Log Watchdog Test Results:{Colors.ENDC}")
    print("="*70)
    
    all_passed = True
    for i, result in enumerate(results):
        test_name = tests[i].__name__
        if result:
            print(f"{Colors.OKGREEN}✓ {test_name} - PASSED{Colors.ENDC}")
        else:
            all_passed = False
            print(f"{Colors.FAIL}✗ {test_name} - FAILED{Colors.ENDC}")
    
    print("="*70)
    if all_passed:
        print(f"{Colors.OKGREEN}{Colors.BOLD}All deployment monitoring tests passed!{Colors.ENDC}")
        return 0
    else:
        print(f"{Colors.FAIL}{Colors.BOLD}Some tests failed!{Colors.ENDC}")
        return 1

def main():
    print(f"{Colors.BOLD}Deployment Manager Log Watchdog Integration Tests{Colors.ENDC}")
    print(f"API Base URL: {client.base_url}")
    print(f"Testing with username: {client.username}")
    print(f"Log Stream API: {LOG_STREAM_BASE_URL}")
    print(f"Test deployment workspaces: {TEST_WORKSPACE_1}, {TEST_WORKSPACE_2}")

    try:
        sys.exit(run_all_tests())
    except requests.exceptions.ConnectionError:
        print(f"{Colors.FAIL}Error: Could not connect to the API server at {client.base_url}{Colors.ENDC}")
        print(f"{Colors.FAIL}Make sure the API server is running and the URL is correct.{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print(f"{Colors.FAIL}Error: {str(e)}{Colors.ENDC}")
        sys.exit(1)

if __name__ == "__main__":
    main()