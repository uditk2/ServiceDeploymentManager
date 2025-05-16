import os
from .helper_functions import generate_unique_name
from app.custom_logging import logger
from .utils import DockerUtils
from .docker_log_handler import DockerCommandWithLogHandler, CommandResult, DockerComposeLogHandler
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
            error_msg = f"Error stopping container: {traceback.format_exc()}"
            logger.error(error_msg)
            return CommandResult(success=False, error=error_msg)
    
    @staticmethod
    def run_docker_compose_build(project_path, user_id)->CommandResult:
        os.chdir(project_path)
        container_name = generate_unique_name(project_base_path=project_path, user_id=user_id)
        try:
            cmd =  'docker compose build'
            cmd_handler = DockerCommandWithLogHandler(project_path)
            return cmd_handler.run_docker_commands_with_logging(cmd, container_name=container_name)
        except Exception as e:
            error_msg = f"Error building container: {traceback.format_exc()}"
            logger.error(error_msg)
            return CommandResult(success=False, error=error_msg)

    @staticmethod
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
                
            all_ports = {}
            
            # Iterate through all services
            for service_name, service_config in services.items():
                ports = service_config.get('ports', [])
                
                # Extract all host ports
                for port in ports:
                    if isinstance(port, str):
                        all_ports[service_name] = port.split(':')[0]
                    elif isinstance(port, dict):
                        published_port = port.get('published')
                        if published_port:
                            all_ports[service_name] = published_port
            
            return all_ports if all_ports else None
        except Exception as e:
            logger.error(f"Error reading docker-compose.yml: {traceback.format_exc()}")
            return None

    def _dev_env_deploy(project_path, container_name, host_ports, env_file_arg):

        cmd = f'docker compose {env_file_arg} -p {container_name} up -d --build'
        logger.info("Run command: " + cmd)
        service_urls = {}
        for service_name, host_port in host_ports.items():
            service_urls[service_name] = f"http://localhost:{host_port}"     
        try :
            compose_file_name = DockerUtils.get_service_paths(project_path=project_path, only_compose=True)[0]
            compose_file_path = os.path.join(project_path, compose_file_name)
            DockerComposeUtils.update_volume_paths(compose_file_path=compose_file_path, project_path=project_path)
            
            # Run the docker compose command
            run_result = DockerCommandWithLogHandler(project_path).run_docker_commands_with_logging(cmd, container_name=container_name)
            
            if run_result.success:                
                # Set up consolidated logging for all containers in the project
                docker_compose_logger = DockerComposeLogHandler(project_path)
                docker_compose_logger.follow_compose_logs(
                    compose_file=compose_file_path,
                    project_name=container_name
                )
                
                run_result.set_deploy_info(json.dumps({"urls": service_urls, "container_name": container_name}))
                return run_result
            return run_result
        except Exception as e:
            logger.error(f"Error in deploying in dev env {traceback.format_exc()}")
            return CommandResult(success=False, error=str(e), deploy_info=json.dumps({"urls": [], "error": {traceback.format_exc()}}))
        
    def _prod_env_deploy(container_name, env_file_arg, project_path):
        try:
            traefik_labeler = TraefikLabeler()
            compose_file_name = DockerUtils.get_service_paths(project_path=project_path, only_compose=True)[0]
            compose_file_path = os.path.join(project_path, compose_file_name)
            network_compose_file, service_urls = traefik_labeler.add_traefik_labels(compose_file=compose_file_path, project_name=container_name)
            # Update volume paths in the compose file
            DockerComposeUtils.update_volume_paths(compose_file_path=network_compose_file, project_path=project_path)
            generate_deploy_command = DockerComposeUtils.generate_deploy_command(compose_file=network_compose_file, project_name=container_name, env_file_arg=env_file_arg)
            logger.info("Run command: " + generate_deploy_command)
            
            # Run the docker compose command      
            run_result = DockerCommandWithLogHandler(project_path).run_docker_commands_with_logging(generate_deploy_command, container_name=container_name)
            
            if run_result.success:
                # Set up consolidated logging for all containers in the project
                docker_compose_logger = DockerComposeLogHandler(project_path)
                docker_compose_logger.follow_compose_logs(
                    compose_file=network_compose_file,
                    project_name=container_name
                )
                
                run_result.set_deploy_info(json.dumps({"urls": service_urls, "container_name": container_name}))
                return run_result
            return run_result
        except Exception as e:
            logger.error(f"Error in deploying in prod env {traceback.format_exc()}")
            return CommandResult(success=False, error=str(e), deploy_info=json.dumps({"urls": [], "error": traceback.format_exc()}))
        
    @staticmethod
    def run_docker_compose_deploy(project_path, user_id, env_file_path=None):
        container_name = generate_unique_name(project_base_path=project_path, user_id=user_id)
        env_file_arg = ""
        if env_file_path is not None:
            env_file_arg = f"--env-file {env_file_path}"
        host_ports = DockerComposeUtils._get_host_port_docker_compose(project_path=project_path)
        
        # Default to a placeholder port if none is found
        if host_ports is None:
             raise ValueError("No host ports found in the docker-compose file.")

        if os.getenv('FLASK_ENV') == 'development':
            return DockerComposeUtils._dev_env_deploy(project_path=project_path, container_name=container_name, 
                                                      host_ports=host_ports, env_file_arg=env_file_arg)
        else:
            return DockerComposeUtils._prod_env_deploy(container_name=container_name, 
                                                        env_file_arg=env_file_arg, 
                                                       project_path=project_path)
    
                

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
    
    @staticmethod
    def update_volume_paths(compose_file_path: str, project_path: str) -> None:
        """
        Update volume paths in a docker-compose file by prepending mapped project path
        to the left-hand side of volume mappings.
        
        Args:
            compose_file_path: Path to the docker-compose.yml file
            project_path: Base project path to be mapped
        
        Returns:
            None
        """
        try:
            # Read the compose file
            with open(compose_file_path, 'r') as f:
                compose_data = yaml.safe_load(f)
            
            mapped_path = DockerComposeUtils.get_mapped_project_path(project_path)
            
            # Process each service's volumes
            services = compose_data.get('services', {})
            for service_name, service_config in services.items():
                if 'volumes' in service_config:
                    updated_volumes = []
                    for volume in service_config['volumes']:
                        # Handle string format "source:target"
                        if isinstance(volume, str) and ':' in volume:
                            source, target = volume.split(':', 1)
                            # Handle relative paths (including those starting with ./)
                            if not source.startswith('/') and not source.startswith('~'):
                                # Remove leading ./ if present
                                if source.startswith('./'):
                                    source = source[2:]
                                # It's a relative path, prepend with mapped project path
                                source = os.path.join(mapped_path, source)
                            updated_volumes.append(f"{source}:{target}")
                        # Handle object format {source: ..., target: ...}
                        elif isinstance(volume, dict) and 'source' in volume:
                            if not volume['source'].startswith('/') and not volume['source'].startswith('~'):
                                # Remove leading ./ if present and also handle ~
                                if volume['source'].startswith('./') or volume['source'].startswith('~/'):
                                    volume['source'] = volume['source'][2:]
                                volume['source'] = os.path.join(mapped_path, volume['source'])
                            updated_volumes.append(volume)
                        else:
                            updated_volumes.append(volume)
                    
                    service_config['volumes'] = updated_volumes
            
            # Write the updated compose file
            with open(compose_file_path, 'w') as f:
                yaml.dump(compose_data, f, default_flow_style=False)
                
            logger.info(f"Updated volume paths in {compose_file_path}")
            return True
                
        except Exception as e:
            logger.error(f"Error updating volume paths: {traceback.format_exc()}")
            return False

    @staticmethod
    def get_mapped_project_path(project_path: str) -> str:
        """
        Replace the local project path with the appropriate volume path if needed.
        
        Args:
            project_path: Original project path
            
        Returns:
            Mapped project path for use in Docker volumes
        """
        volume_map = dict([os.environ.get('BASE_VOLUME_DIR_MAP', '').split(':', 1)])
            
        for base_path, volume_path in volume_map.items():
            if project_path.startswith(base_path):
                return project_path.replace(base_path, volume_path, 1)
        return project_path