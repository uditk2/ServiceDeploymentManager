import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.docker.docker_compose_utils import DockerComposeUtils
from app.custom_logging import logger

def test_run_docker_compose_down():
    # Mock the project path and user ID
    project_path = "/Users/uditkhandelwal/Documents/testing/test_user/test_workspace"
    user_id = "test_user"

    # Call the method
    result = DockerComposeUtils.run_docker_compose_down(project_path, user_id)
    logger.info("Result of Docker Compose down command: " + str(result))
    # Check the result
    assert result is not None

def test_run_docker_compose_build():
    # Mock the project path and user ID
    project_path = "/Users/uditkhandelwal/Documents/testing/test_user/test_workspace"
    user_id = "test_user"

    # Call the method
    result = DockerComposeUtils.run_docker_compose_build(project_path, user_id)
    logger.info("Result of Docker Compose build command: " + str(result))
    # Check the result
    assert result is not None

def test_run_docker_compose_deploy():
    # Mock the project path and user ID
    project_path = "/Users/uditkhandelwal/Documents/testing/test_user/test_workspace"
    user_id = "test_user"

    # Call the method
    result = DockerComposeUtils.run_docker_compose_deploy(project_path, user_id)
    logger.info("Result of Docker Compose deploy command: " + str(result))
    job_id = result["job_id"]

    # Check the result
    assert result is not None 

if __name__ == "__main__":
    test_run_docker_compose_down()
    test_run_docker_compose_build()
    test_run_docker_compose_deploy()
    print("Test passed!")