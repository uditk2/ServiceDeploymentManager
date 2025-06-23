import os
from .helper_functions import generate_unique_name, extract_username_and_workspace_from_path
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
            compose_file, _ = DockerComposeUtils.generate_docker_compose_file(project_path=project_path, container_name=container_name)
            cmd =  DockerComposeUtils.generate_build_command(
                compose_file=compose_file,
                project_name=container_name
            )
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
            username, workspace = extract_username_and_workspace_from_path(project_path=project_path)
            DockerComposeUtils.enable_fluentd_logging(
                compose_file_path=compose_file_path,
                username=username,
                workspace=workspace
            )
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
    
    def generate_network_compose_file(compose_file: str) -> str:
        # Generate output filename
        base_filename, ext = os.path.splitext(compose_file)
        output_file = f"{base_filename}.traefik{ext}"
        return output_file
    
    def generate_docker_compose_file(project_path: str, container_name) -> str:
        try:
            compose_file_name = DockerUtils.get_service_paths(project_path=project_path, only_compose=True)[0]
            compose_file_path = os.path.join(project_path, compose_file_name)
            network_compose_file = DockerComposeUtils.generate_network_compose_file(compose_file=compose_file_path)
            traefik_labeler = TraefikLabeler()
            service_urls = traefik_labeler.add_traefik_labels(compose_file=compose_file_path, project_name=container_name, output_file=network_compose_file)
              # Update volume paths in the compose file
            DockerComposeUtils.update_volume_paths(compose_file_path=network_compose_file, project_path=project_path)
            return network_compose_file, service_urls
        except Exception as e:
            logger.error(f"Error generating docker-compose file: {traceback.format_exc()}")
            raise e
    def _prod_env_deploy(container_name, env_file_arg, project_path):
        try:
            network_compose_file, service_urls = DockerComposeUtils.generate_docker_compose_file(project_path=project_path, container_name=container_name)
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

        # Perform optional pre-deployment cleanup to free up space
        # These operations are non-critical and should never fail the deployment
        try:
            logger.info("Performing optional pre-deployment cleanup...")
            cleanup_result = DockerComposeUtils.run_docker_compose_cleanup(project_path, user_id)
            if cleanup_result.success:
                logger.info("Pre-deployment cleanup completed successfully")
            else:
                logger.info(f"Pre-deployment cleanup completed with warnings: {cleanup_result.error}")
        except Exception as cleanup_error:
            logger.info(f"Pre-deployment cleanup skipped due to error: {str(cleanup_error)}")

        # Perform optional system cleanup to free more space
        # This is also non-critical and should never fail the deployment
        try:
            logger.info("Performing optional system cleanup...")
            system_cleanup_result = DockerComposeUtils.run_system_cleanup()
            if system_cleanup_result.success:
                logger.info("System cleanup completed successfully")
            else:
                logger.info(f"System cleanup completed with warnings: {system_cleanup_result.error}")
        except Exception as system_cleanup_error:
            logger.info(f"System cleanup skipped due to error: {str(system_cleanup_error)}")

        # Proceed with the actual deployment
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
          # Add build flag. Since we are building it earlier. we can skip this.
        command_parts.append("--build")    
        
        # Join all parts with spaces
        return " ".join(command_parts)
    
    def generate_build_command(compose_file, project_name, env_file_arg=None) -> str:
        """
        Generate the Docker Compose build command.
        
        Returns:
            The full Docker Compose build command as a string
        """
        command_parts = ["docker", "compose"]
        
        # Add compose file
        command_parts.extend(["-f", compose_file])
        
        # Add project name
        command_parts.extend(["-p", project_name])
        
        # Add env file if specified
        if env_file_arg:
            command_parts.extend([env_file_arg])
        
        # Add build command
        command_parts.append("build")
        
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

    def enable_fluentd_logging(compose_file_path: str, username: str, workspace: str) -> str:
        """
        Add Fluentd logging configuration to the docker-compose file.
        
        Args:
            compose_file_path: Path to the docker-compose.yml file
            username: Username for the log tag
            workspace: Workspace name for the log tag
            
        Returns:
            Path to the modified compose file with Fluentd logging enabled
        """
        from app.docker.fluentd_enabler import FluentdEnabler
        
        fluentd_enabler = FluentdEnabler()
        updated = fluentd_enabler.add_fluentd_to_compose(
            compose_file_path=compose_file_path,
            username=username,
            workspace=workspace
        )
        if not updated:
            logger.error(f"Failed to enable Fluentd logging in {compose_file_path}")
            raise RuntimeError("Failed to enable Fluentd logging")
        
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

    @staticmethod
    def run_docker_compose_cleanup(project_path, user_id) -> CommandResult:
        """
        Perform selective cleanup for a specific project without disturbing other running containers.
        Only cleans up resources related to this project.
        
        Args:
            project_path: Path to the project directory
            user_id: User identifier
            
        Returns:
            CommandResult indicating success/failure of cleanup operations
        """
        os.chdir(project_path)
        container_name = generate_unique_name(project_base_path=project_path, user_id=user_id)
        
        try:
            # Only clean up resources specific to this project
            cleanup_commands = [
                # Stop and remove only THIS project's containers
                f'docker compose -p {container_name} down --volumes --remove-orphans',
                # Remove only images specific to this project (if they exist)
                f'docker images -q --filter "label=com.docker.compose.project={container_name}" | xargs -r docker rmi -f 2>/dev/null || true',
                # Only remove dangling images (not affecting running containers)
                'docker image prune -f'
            ]
            
            results = []
            for cmd in cleanup_commands:
                logger.info(f"Running selective cleanup command: {cmd}")
                try:
                    result = DockerCommandWithLogHandler(project_path).run_docker_commands_with_logging(cmd, container_name=container_name)
                    if result:
                        results.append(result)
                        if not result.success:
                            logger.warning(f"Cleanup command failed (non-critical): {cmd} - {result.error}")
                    else:
                        logger.warning(f"Cleanup command returned None: {cmd}")
                except Exception as cmd_error:
                    logger.warning(f"Error running cleanup command '{cmd}': {str(cmd_error)}")
                    # Continue with other cleanup commands even if one fails
                    
            # Return success if at least the main down command succeeded
            if results and results[0].success:
                return CommandResult(
                    success=True, 
                    output="Selective cleanup completed successfully",
                    deploy_info="Project-specific cleanup completed"
                )
            else:
                return CommandResult(
                    success=True,  # Mark as success since project-specific cleanup not existing is OK
                    output="No existing containers found for this project",
                    deploy_info="No cleanup needed"
                )
                
        except Exception as e:
            error_msg = f"Error during selective cleanup: {traceback.format_exc()}"
            logger.error(error_msg)
            return CommandResult(success=False, error=error_msg)

    @staticmethod
    def run_system_cleanup() -> CommandResult:
        """
        Perform safe system-wide Docker cleanup that won't affect running containers.
        Only removes truly unused resources.
        
        Returns:
            CommandResult indicating success/failure of system cleanup
        """
        try:
            # Only run safe cleanup commands that won't affect running containers
            safe_cleanup_commands = [
                # Remove only dangling images (not used by any container)
                'docker image prune -f',
                # Remove only unused build cache
                'docker builder prune -f',
                # Remove only unused volumes (not mounted by running containers)
                'docker volume prune -f'
            ]
            
            results = []
            for cmd in safe_cleanup_commands:
                logger.info(f"Running safe system cleanup command: {cmd}")
                try:
                    # Use a simple command execution for system cleanup
                    import subprocess
                    result = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=60)
                    if result.returncode == 0:
                        logger.info(f"Safe cleanup command succeeded: {cmd}")
                        results.append(True)
                    else:
                        logger.warning(f"Safe cleanup command failed: {cmd} - {result.stderr}")
                        results.append(False)
                except Exception as cmd_error:
                    logger.warning(f"Error running safe cleanup command '{cmd}': {str(cmd_error)}")
                    results.append(False)
                    
            success_count = sum(results)
            total_count = len(results)
            
            return CommandResult(
                success=True,  # Always return success since this is optional optimization
                output=f"Safe system cleanup completed: {success_count}/{total_count} commands succeeded",
                deploy_info=f"Safe cleanup: {success_count}/{total_count} operations completed"
            )
                
        except Exception as e:
            error_msg = f"Error during safe system cleanup: {traceback.format_exc()}"
            logger.error(error_msg)
            return CommandResult(success=True, error=error_msg)  # Don't fail deployment for cleanup issues