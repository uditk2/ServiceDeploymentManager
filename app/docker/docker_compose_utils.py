import os
from .helper_functions import generate_unique_name
from app.custom_logging import logger
from .utils import DockerUtils
from .docker_log_handler import DockerCommandWithLogHandler, ContainerLogHandler, CommandResult
import traceback
import yaml
from typing import Dict, Any, Optional
from .traefik_labeler import TraefikLabeler
import json

class DockerComposeUtils():

    @staticmethod
    def run_docker_compose_down(project_path, user_id)->CommandResult:
        os.chdir(project_path)
        container_name = generate_unique_name(project_base_path=project_path, user_id=user_id)
        try:
            cmd =  f'docker compose -p {container_name} down'
            return DockerCommandWithLogHandler(project_path).run_docker_commands_with_logging(cmd, container_name=container_name)
        except Exception as e:
            logger.error(f"Error stopping container: {traceback.format_exc()}")
            return None
    
    @staticmethod
    def run_docker_compose_build(project_path, user_id)->CommandResult:
        os.chdir(project_path)
        container_name = generate_unique_name(project_base_path=project_path, user_id=user_id)
        try:
            cmd =  'docker compose build'
            cmd_handler = DockerCommandWithLogHandler(project_path)
            return cmd_handler.run_docker_commands_with_logging(cmd, container_name=container_name)
        except Exception as e:
            logger.error(f"Error removing container: {traceback.format_exc()}")
            return None

    @staticmethod
    def _get_exposed_port_docker_compose(project_path):
        """Get the deployment port from the docker-compose file"""
        try:
            compose_file = os.path.join(project_path, 'docker-compose.yml')
            if not os.path.exists(compose_file):
                return None
                
            with open(compose_file, 'r') as f:
                compose_config = yaml.safe_load(f)
                
            # Look for port mapping in the first service
            services = compose_config.get('services', {})
            if not services:
                return None
                
            first_service = next(iter(services.values()))
            ports = first_service.get('ports', [])

            # Extract the expose port from the first port mapping
            if ports and isinstance(ports[0], str):
                return ports[0].split(':')[1]
            elif ports and isinstance(ports[0], dict):
                return ports[0].get('target')
        except Exception as e:
            logger.error(f"Error reading docker-compose.yml: {traceback.format_exc()}")
            return None

    def _get_host_port_docker_compose(project_path):
        """Get the deployment port from the docker-compose file"""
        try:
            compose_file = os.path.join(project_path, 'docker-compose.yml')
            if not os.path.exists(compose_file):
                return None
                
            with open(compose_file, 'r') as f:
                compose_config = yaml.safe_load(f)
                
            # Look for port mapping in the first service
            services = compose_config.get('services', {})
            if not services:
                return None
                
            first_service = next(iter(services.values()))
            ports = first_service.get('ports', [])
            
            # Extract the host port from the first port mapping
            if ports and isinstance(ports[0], str):
                return ports[0].split(':')[0]
            elif ports and isinstance(ports[0], dict):
                return ports[0].get('published')
            return None
        except Exception as e:
            logger.error(f"Error reading docker-compose.yml: {traceback.format_exc()}")
            return None

    def _dev_env_deploy(project_path, container_name, host_port, env_file_arg):

        cmd = f'docker compose {env_file_arg} -p {container_name} up -d --build'
        logger.info("Run command: " + cmd)
        url = f"http://localhost:{host_port}"
        try :
            run_result = DockerCommandWithLogHandler(project_path).run_docker_commands_with_logging(cmd, container_name=container_name)
            url = f"http://localhost:{host_port}"
            if run_result.success:
              return run_result.set_deploy_info(json.dumps({"urls": [url], "container_name": container_name}))
            return run_result
        except Exception as e:
            logger.error(f"Error in deploying in dev env {traceback.format_exc()}")
            return CommandResult(success=False, error=str(e), deploy_info=json.dumps({"urls": [], "error": {traceback.format_exc()}}))
        
    def _prod_env_deploy(container_name, exposed_port, env_file_arg, project_path, user_id):
        try:
            traefik_labeler = TraefikLabeler()
            compose_file_name = DockerUtils.get_service_paths(project_path=project_path, only_compose=True)[0]
            network_compose_file =traefik_labeler.add_traefik_labels(compose_file=os.path.join(project_path, compose_file_name), project_name=container_name)
            generate_deploy_command = DockerComposeUtils.generate_deploy_command(compose_file=network_compose_file, project_name=container_name, env_file_arg=env_file_arg)
            logger.info("Run command: " + generate_deploy_command)
            urls = DockerComposeUtils.get_service_urls(compose_file=network_compose_file, container_name=container_name)
            run_result = DockerCommandWithLogHandler(project_path).run_docker_commands_with_logging(generate_deploy_command, container_name=container_name)
            # Check if the network compose file exists and remove it if it does
            if os.path.exists(network_compose_file):
                logger.info(f"Removing temporary compose file: {network_compose_file}")
                try:
                    os.remove(network_compose_file)
                except Exception as e:
                    logger.warning(f"Could not remove temporary compose file: {str(e)}")
            if run_result.success:
               run_result.set_deploy_info(json.dumps({"urls": urls, "container_name": container_name}))
               return run_result
            return run_result
        except Exception as e:
            logger.error(f"Error in deploying in prod env {traceback.format_exc()}")
            return CommandResult(success=False, error=str(e), deploy_info=json.dumps({"urls": [], "error": {traceback.format_exc()}}))
        
    @staticmethod
    def run_docker_compose_deploy(project_path, user_id, env_file_path=None):
        container_name = generate_unique_name(project_base_path=project_path, user_id=user_id)
        env_file_arg = ""
        if env_file_path is not None:
            env_file_arg = f"--env-file {env_file_path}"
        exposed_port = DockerComposeUtils._get_exposed_port_docker_compose(project_path=project_path)
        host_port = DockerComposeUtils._get_host_port_docker_compose(project_path=project_path)

        if os.getenv('FLASK_ENV') == 'development':
            return DockerComposeUtils._dev_env_deploy(project_path=project_path, container_name=container_name, 
                                                      host_port=host_port, env_file_arg=env_file_arg)
        else:
            return DockerComposeUtils._prod_env_deploy(container_name=container_name, 
                                                       exposed_port=exposed_port, env_file_arg=env_file_arg, 
                                                       project_path=project_path, user_id=user_id)
    
                

    @staticmethod
    def generate_deploy_command(compose_file, project_name, env_file_arg=None)-> str:
        """
        Generate the Docker Compose command for deployment.
        
        Returns:
            The full Docker Compose command as a string
        """
        command_parts = ["docker", "compose"]
        
        # Add compose file
        command_parts.extend(["-f", compose_file])
        
        # Add project name
        command_parts.extend(["-p", project_name])
        
        # Add env file if specified
        if env_file_arg:
            command_parts.extend([env_file_arg])
        
        # Add up command
        command_parts.append("up")
        # Add detached mode
        command_parts.append("-d")
          # Add build flag 
        command_parts.append("--build")    
        
        # Join all parts with spaces
        return " ".join(command_parts)
    

    @staticmethod
    def get_service_urls(compose_file, container_name, domain_base: str="apps.synergiqai.com") -> Dict[str, str]:
        """
        Generate a dictionary of service URLs based on the compose file and domain base.
        
        Args:
            domain_base: Base domain for services (e.g., apps.synergiqai.com)
            
        Returns:
            Dictionary mapping service names to their URLs
        """
        import yaml
        
        # Read the compose file
        with open(compose_file, 'r') as f:
            compose_data = yaml.safe_load(f)
        
        urls = {}
        services = compose_data.get('services', {})
        
        for service_name in services:
            url = f"https://{service_name}-{container_name}.{domain_base}"
            urls[service_name] = url
        
        return urls