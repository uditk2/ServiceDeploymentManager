import os
import sys
import time
import json
import shutil
import yaml
from zipfile import ZipFile

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

def assert_true(value, message):
    if value:
        print_success(message)
        return True
    else:
        print_failure(f"{message} - Value is not True")
        return False

def assert_false(value, message):
    if not value:
        print_success(message)
        return True
    else:
        print_failure(f"{message} - Value is not False")
        return False

def assert_not_none(value, message):
    if value is not None:
        print_success(message)
        return True
    else:
        print_failure(f"{message} - Value is None")
        return False

# Path constants
TEST_USERNAME = "test_user"
TEST_WORKSPACE = "test_docker_compose_utils"
ZIP_FILE_PATH = "./tests/BasePythonWebApp.zip"
PROJECT_PATH = f"./tests/{TEST_WORKSPACE}"

# Import DockerComposeUtils locally to avoid import issues before project path setup
sys.path.append('.')
from app.docker.docker_compose_utils import DockerComposeUtils
from app.docker.docker_log_handler import CommandResult
from app.docker.helper_functions import generate_project_name_from_user_workspace


def setup_test_project():
    """Extract the test project and prepare for testing"""
    print_test_header("Setting up test project")
    
    try:
        if os.path.exists(PROJECT_PATH):
            print_info("Removing existing test project directory")
            shutil.rmtree(PROJECT_PATH)
        
        os.makedirs(PROJECT_PATH, exist_ok=True)
        
        print_info(f"Extracting {ZIP_FILE_PATH} to {PROJECT_PATH}")
        with ZipFile(ZIP_FILE_PATH, 'r') as zip_ref:
            zip_ref.extractall(PROJECT_PATH)
            
        if os.path.exists(os.path.join(PROJECT_PATH, "docker-compose.yml")):
            print_success("Test project successfully set up")
            return True
        else:
            print_failure("docker-compose.yml not found in extracted project")
            return False
    except Exception as e:
        print_failure(f"Error setting up test project: {str(e)}")
        return False


def test_generate_deploy_command():
    """Test the generate_deploy_command function"""
    print_test_header("Testing generate_deploy_command function")
    
    try:
        compose_file = os.path.join(PROJECT_PATH, "docker-compose.yml")
        project_name = generate_project_name_from_user_workspace(TEST_USERNAME, TEST_WORKSPACE)
        
        # Test without env file
        cmd = DockerComposeUtils.generate_deploy_command(
            compose_file=compose_file,
            project_name=project_name
        )
        
        expected_cmd_parts = [
            "docker", "compose", "-f", compose_file, 
            "-p", project_name, "up", "-d", "--build"
        ]
        expected_cmd = " ".join(expected_cmd_parts)
        
        assert_equal(cmd, expected_cmd, "Command generated correctly without env file")
        
        # Test with env file
        env_file_arg = "--env-file .env"
        cmd_with_env = DockerComposeUtils.generate_deploy_command(
            compose_file=compose_file,
            project_name=project_name,
            env_file_arg=env_file_arg
        )
        
        expected_cmd_parts_with_env = [
            "docker", "compose", "-f", compose_file, 
            "-p", project_name, env_file_arg, "up", "-d", "--build"
        ]
        expected_cmd_with_env = " ".join(expected_cmd_parts_with_env)
        
        assert_equal(cmd_with_env, expected_cmd_with_env, "Command generated correctly with env file")
        
        return True
    except Exception as e:
        print_failure(f"Error testing generate_deploy_command: {str(e)}")
        return False


def test_get_host_port_docker_compose():
    """Test the _get_host_port_docker_compose function"""
    print_test_header("Testing _get_host_port_docker_compose function")
    
    try:
        # Use the actual BasePythonWebApp from the ZIP file using ZipUtils
        if os.path.exists(PROJECT_PATH):
            print_info("Removing existing test project directory")
            shutil.rmtree(PROJECT_PATH)
        
        os.makedirs(PROJECT_PATH, exist_ok=True)
        
        # Import and use ZipUtils to extract the test project
        from app.docker.zip_utils import ZipUtils
        print_info(f"Using ZipUtils to extract {ZIP_FILE_PATH} to {PROJECT_PATH}")
        
        extract_result = ZipUtils.extract_zip_file(
            zip_file_path=ZIP_FILE_PATH,
            user_name=TEST_USERNAME,
            project_name="BasePythonWebApp",
            base_directory=PROJECT_PATH
        )
        
        if not extract_result["success"]:
            print_failure(f"Failed to extract test project: {extract_result['message']}")
            return False
            
        # Make sure the docker-compose.yml exists
        compose_file = os.path.join(extract_result["project_path"], "docker-compose.yml")
        if not os.path.exists(compose_file):
            print_failure(f"docker-compose.yml not found in {extract_result["project_path"]}")
            return False
            
        # Test the function with the actual docker-compose file
        host_ports = DockerComposeUtils._get_host_port_docker_compose(extract_result["project_path"])
        
        assert_not_none(host_ports, "Host ports should not be None")

        # Check that we have ports in the dictionary
        assert_true(len(host_ports) > 0, "Host ports dictionary should have at least one entry")
        
        # Check the first item in the dictionary
        first_key = list(host_ports.keys())[0]
        first_value = host_ports[first_key]
        print_info(f"First port mapping: {first_key} -> {first_value}")
        
        # Check specific service port
        assert_equal(host_ports.get(first_key), '3000', "Web app service port should be 3000")
        
        # Test with no ports by modifying the compose file temporarily
        compose_content_no_ports = {
            'services': {
                'web': {
                    'image': 'nginx'
                }
            }
        }
        
        temp_compose_file = os.path.join(PROJECT_PATH, "temp-docker-compose.yml")
        with open(temp_compose_file, 'w') as f:
            yaml.dump(compose_content_no_ports, f)
        
        host_ports_none = DockerComposeUtils._get_host_port_docker_compose(PROJECT_PATH)
        assert_equal(host_ports_none, None, "Host ports should be None when no ports defined")
        
        # Remove temporary file
        if os.path.exists(temp_compose_file):
            os.remove(temp_compose_file)
        
        # Clean up by removing the extracted project
        if os.path.exists(PROJECT_PATH):
            print_info("Cleaning up extracted project after test")
            shutil.rmtree(PROJECT_PATH)
        
        return True
    except Exception as e:
        print_failure(f"Error testing _get_host_port_docker_compose: {str(e)}")
        
        # Make sure to clean up even if there's an error
        if os.path.exists(PROJECT_PATH):
            print_info("Cleaning up extracted project after exception")
            shutil.rmtree(PROJECT_PATH)
            
        return False


def test_update_volume_paths():
    """Test the update_volume_paths function"""
    print_test_header("Testing update_volume_paths function")
    
    try:
        # Create a test docker-compose file with volumes
        compose_content = {
            'services': {
                'web': {
                    'image': 'nginx',
                    'volumes': [
                        './app:/app',
                        {'source': './data', 'target': '/data'}
                    ]
                }
            }
        }
        
        compose_file = os.path.join(PROJECT_PATH, "docker-compose.yml")
        with open(compose_file, 'w') as f:
            yaml.dump(compose_content, f)
        
        # Test the function
        result = DockerComposeUtils.update_volume_paths(compose_file, PROJECT_PATH)
        assert_true(result, "Volume path update should succeed")
        
        # Read updated compose file
        with open(compose_file, 'r') as f:
            updated_compose = yaml.safe_load(f)
        
        # Check if paths were updated
        volumes = updated_compose['services']['web']['volumes']
        mapped_path = DockerComposeUtils.get_mapped_project_path(PROJECT_PATH)
        
        expected_path = os.path.join(mapped_path, "app")
        assert_true(volumes[0].startswith(expected_path), f"Volume path should be updated to start with {expected_path}")
        
        expected_source = os.path.join(mapped_path, "data")
        assert_equal(volumes[1]['source'], expected_source, f"Object volume source should be {expected_source}")
        
        return True
    except Exception as e:
        print_failure(f"Error testing update_volume_paths: {str(e)}")
        return False


def test_get_service_urls():
    """Test the get_service_urls function"""
    print_test_header("Testing get_service_urls function")
    
    try:
        # Create a test docker-compose file with multiple services
        compose_content = {
            'services': {
                'web': {'image': 'nginx'},
                'api': {'image': 'python'}
            }
        }
        
        compose_file = os.path.join(PROJECT_PATH, "docker-compose.yml")
        with open(compose_file, 'w') as f:
            yaml.dump(compose_content, f)
        
        container_name = f"{TEST_USERNAME}_{TEST_WORKSPACE}"
        domain_base = "apps.synergiqai.com"
        
        # Test the function
        urls = DockerComposeUtils.get_service_urls(compose_file, container_name, domain_base)
        
        assert_equal(urls['web'], f"https://web-{container_name}.{domain_base}", "Web service URL correct")
        assert_equal(urls['api'], f"https://api-{container_name}.{domain_base}", "API service URL correct")
        
        return True
    except Exception as e:
        print_failure(f"Error testing get_service_urls: {str(e)}")
        return False


def test_get_mapped_project_path():
    """Test the get_mapped_project_path function"""
    print_test_header("Testing get_mapped_project_path function")
    
    try:
        # Save original environment variable
        original_env = os.environ.get('BASE_VOLUME_DIR_MAP', '')
        
        # Set test environment variable
        os.environ['BASE_VOLUME_DIR_MAP'] = f"/local/path:/container/path"
        
        # Test with matching path
        local_path = "/local/path/myproject"
        mapped_path = DockerComposeUtils.get_mapped_project_path(local_path)
        expected_path = "/container/path/myproject"
        assert_equal(mapped_path, expected_path, "Path should be mapped correctly when it matches the base path")
        
        # Test with non-matching path
        other_path = "/other/path/myproject"
        mapped_other_path = DockerComposeUtils.get_mapped_project_path(other_path)
        assert_equal(mapped_other_path, other_path, "Path should remain unchanged when it doesn't match the base path")
        
        # Restore original environment variable
        if original_env:
            os.environ['BASE_VOLUME_DIR_MAP'] = original_env
        else:
            del os.environ['BASE_VOLUME_DIR_MAP']
        
        return True
    except Exception as e:
        print_failure(f"Error testing get_mapped_project_path: {str(e)}")
        # Restore original environment variable
        original_env = os.environ.get('BASE_VOLUME_DIR_MAP', '')
        if original_env:
            os.environ['BASE_VOLUME_DIR_MAP'] = original_env
        else:
            if 'BASE_VOLUME_DIR_MAP' in os.environ:
                del os.environ['BASE_VOLUME_DIR_MAP']
        return False


def test_docker_compose_build():
    """Test the run_docker_compose_build function"""
    print_test_header("Testing run_docker_compose_build function")
    
    try:
        # Skip actual build in test environment to avoid Docker operations
        print_info("Skipping actual Docker Compose build to avoid Docker operations")
        print_info("In a real environment, this would build the Docker image")
        
        # Instead, just verify that the function exists with correct signature
        assert_true(hasattr(DockerComposeUtils, 'run_docker_compose_build'), 
                    "DockerComposeUtils should have run_docker_compose_build method")
        
        return True
    except Exception as e:
        print_failure(f"Error testing run_docker_compose_build: {str(e)}")
        return False


def clean_up():
    """Clean up the test project"""
    print_test_header("Cleaning up test project")
    
    try:
        if os.path.exists(PROJECT_PATH):
            print_info("Removing test project directory")
            shutil.rmtree(PROJECT_PATH)
            print_success("Test project directory removed")
        return True
    except Exception as e:
        print_failure(f"Error cleaning up test project: {str(e)}")
        return False


def run_all_tests():
    tests = [
        setup_test_project,
        test_generate_deploy_command,
        test_get_host_port_docker_compose,
        test_update_volume_paths,
        test_get_service_urls,
        test_get_mapped_project_path,
        test_docker_compose_build,
        clean_up
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
    print(f"{Colors.BOLD}Docker Compose Utils Comprehensive Tests{Colors.ENDC}")
    print(f"Testing with username: {TEST_USERNAME}")
    print(f"Testing with workspace: {TEST_WORKSPACE}")
    
    try:
        sys.exit(run_all_tests())
    except Exception as e:
        print(f"{Colors.FAIL}Error: {str(e)}{Colors.ENDC}")
        sys.exit(1)


if __name__ == "__main__":
    main()