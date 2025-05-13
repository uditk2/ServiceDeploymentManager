from .helper_functions import generate_unique_name, extract_user_id
import os
from pathlib import Path
import json
from app.custom_logging import logger
from typing import Dict, Any, Optional
from .docker_log_handler import DockerCommandWithLogHandler
from .config import DockerConfig
import subprocess


class DockerUtils():

    @staticmethod
    def is_container_present(project_path, user_id) -> Optional[bool]:
        container_name = generate_unique_name(project_base_path=project_path, user_id=user_id)
        check_cmd = f'docker ps -a --filter name=^/{container_name}$ --format "{{{{.Names}}}}"'
        check_result = DockerCommandWithLogHandler(project_path).run_docker_commands_with_logging(check_cmd, container_name=container_name)
        if not check_result.success or not check_result.output.strip():
            logger.info(f"Container {container_name} does not exist")
            return False
        return True

    @staticmethod
    def get_host_port(user_id, project_path):
        """Generate a host port using base port and offset"""
        try:
            base_port = DockerConfig.BASE_PORT
            user_id = extract_user_id(user_id)
            project_name = Path(project_path).name
            # Create a hash based on both user_id and project name
            combined_str = user_id + project_name
            offset = sum(ord(c) for c in combined_str) % DockerConfig.MAX_PORT_OFFSET
            return base_port + offset
        except Exception as e:
            logger.error(f"Error generating host port: {str(e)}")
            return None
        
    @staticmethod
    def process_env_variables(env_variables: Dict, base_path: str) -> Optional[str]:
        """Create a .env file from environment variables"""
        if not env_variables:
            return None
            
        env_file_path = os.path.join(base_path, ".env")
        
        try:
            with open(env_file_path, "w") as f:
                for key, value in env_variables.items():
                    f.write(f"{key}={value}\n")
            return env_file_path
        except Exception:
            return None

    @staticmethod
    def get_container_name(user_id: str, project_name: str) -> str:
        """Generate a container name from user ID and project name"""
        sanitized_name = f"{user_id}-{project_name}".lower()
        return "".join(c for c in sanitized_name if c.isalnum() or c in ('-', '_'))

    @staticmethod
    def get_build_result(container_id, success, url, error=None) -> Dict[str, Any]:
        """Build a response based on deployment success"""
        return {
            'container_id': container_id,
            'status': success,
            'url': url,
            'error': error
        }

    @staticmethod
    def generate_network_labels():
        """Generate Docker network labels for Traefik"""
        return {
            'network': DockerConfig.DOCKER_NETWORK
        }

    @staticmethod
    def generate_subdomain(project_path, user_id):
        """Generate a unique subdomain for the project"""
        endpoint_file = os.path.join(project_path, 'endpoint')
        logger.info(f"Endpoint file: {endpoint_file}")
        if os.path.exists(endpoint_file):
            with open(endpoint_file, 'r') as f:
                return f.read().strip
        return generate_unique_name(project_base_path=project_path, user_id=user_id) + f".{DockerConfig.BASE_DOMAIN}"

    @staticmethod
    def get_service_paths(project_path, only_compose=False):
        """Get service paths for a docker-compose project"""
        try:
            docker_compose_paths = []
            dockerfile_paths = []
            
            # Walk through the project directory
            for root, _, files in os.walk(project_path):
                for file in files:
                    file_path = Path(root) / file
                    if file.lower() in ['docker-compose.yml', 'docker-compose.yaml']:
                        docker_compose_paths.append(str(file_path))
                    elif file.lower() == 'dockerfile':
                        dockerfile_paths.append(str(file_path))
            if only_compose:
                return docker_compose_paths
            if len(docker_compose_paths) == 1 and len(dockerfile_paths) == 1:
                docker_compose_base = Path(docker_compose_paths[0]).parent
                dockerfile_base = Path(dockerfile_paths[0]).parent
                if docker_compose_base == dockerfile_base:
                    return docker_compose_paths
            return docker_compose_paths + dockerfile_paths
        except Exception as e:
            logger.error(f"Error getting service paths: {str(e)}")
            return None