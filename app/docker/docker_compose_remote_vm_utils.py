import os
from .helper_functions import generate_unique_name, extract_username_and_workspace_from_path
from app.custom_logging import logger
from .utils import DockerUtils
from .docker_log_handler import DockerCommandWithLogHandler, CommandResult, DockerComposeLogHandler
import traceback
import yaml
from typing import Dict, Any, Optional
import json
from app.docker.docker_context_manager import DockerContextManager
from .services_ports_identifier import ServicesPortsIdentifier
from app.vm_manager.traefik_toml_generator import TraefikTomlGenerator
class DockerComposeRemoteVMUtils:
    """
    Utilities for deploying and managing Docker Compose projects on a remote VM using Docker contexts.
    """

    @staticmethod
    async def set_docker_context(username: str, workspace_name: str, user: str = 'azureuser'):
        """
        Set the Docker context for the user's workspace on the remote VM (async).
        """
        return await DockerContextManager.set_context_for_user_workspace(username, workspace_name, user)

    @staticmethod
    async def run_docker_compose_down(project_path, username, workspace_name) -> CommandResult:
        try:
            context_name, _ = await DockerComposeRemoteVMUtils.set_docker_context(username, workspace_name)
            os.chdir(project_path)
            container_name = generate_unique_name(project_base_path=project_path, username=username)
            cmd = f'docker --context {context_name} compose -p {container_name} down'
            return DockerCommandWithLogHandler(project_path).run_docker_commands_with_logging(cmd, container_name=container_name)
        except Exception as e:
            error_msg = f"Error in docker compose down: {traceback.format_exc()}"
            logger.error(error_msg)
            return CommandResult(success=False, error=error_msg)

    @staticmethod
    async def run_docker_compose_build(project_path, username, workspace_name) -> CommandResult:
        context_name, _ = await DockerComposeRemoteVMUtils.set_docker_context(username, workspace_name)
        os.chdir(project_path)
        container_name = generate_unique_name(project_base_path=project_path, username=username)
        try:
            compose_file = DockerComposeRemoteVMUtils.get_compose_file_path(project_path=project_path)
            cmd = DockerComposeRemoteVMUtils.generate_build_command(
                compose_file=compose_file,
                project_name=container_name,
                context_name=context_name
            )
            cmd_handler = DockerCommandWithLogHandler(project_path)
            return cmd_handler.run_docker_commands_with_logging(cmd, container_name=container_name)
        except Exception as e:
            error_msg = f"Error building container: {traceback.format_exc()}"
            logger.error(error_msg)
            return CommandResult(success=False, error=error_msg)

    @staticmethod
    def get_compose_file_path(project_path: str) -> str:
        """
        Get the path to the docker-compose.yml file in the project directory.
        
        Args:
            project_path: Path to the project directory
        Returns:
            The path to the docker-compose.yml file
        """
        compose_file_name = DockerUtils.get_service_paths(project_path=project_path, only_compose=True)[0]
        compose_file_path = os.path.join(project_path, compose_file_name)
        if not os.path.exists(compose_file_path):
            raise FileNotFoundError(f"Docker Compose file not found at {compose_file_path}")
        return compose_file_path
    
    @staticmethod
    def read_compose_file(compose_file_path: str) -> Dict[str, Any]:
        """
        Read the docker-compose.yml file and return its contents as a dictionary.
        
        Args:
            project_path: Path to the project directory
        """
        with open(compose_file_path, 'r') as file:
            return yaml.safe_load(file)
        raise FileNotFoundError(f"Docker Compose file not found at {compose_file_path}")

    @staticmethod
    def _retrieve_external_service_ports(project_path: str) -> Optional[Dict[str, Any]]:
        """
        Extract external service ports from the docker-compose file in the project directory.
        Args:
            project_path: Path to the project directory
        Returns:
            A dictionary mapping external service names to their ports, or None if no ports are found
        """

        services_ports_identifier = ServicesPortsIdentifier()
        compose_content = DockerComposeRemoteVMUtils.read_compose_file(
            compose_file_path=DockerComposeRemoteVMUtils.get_compose_file_path(project_path=project_path)
        )
        services_ports = services_ports_identifier.identify_external_servicesports(docker_compose=compose_content)
        if not services_ports:
            raise ValueError("No external services ports found in the docker-compose file.")
        return services_ports

    @staticmethod
    async def run_docker_compose_deploy(project_path, username, workspace_name, env_file_path=None):
        context_name, private_ip = await DockerComposeRemoteVMUtils.set_docker_context(username, workspace_name)
        container_name = generate_unique_name(project_base_path=project_path, username=username)
        env_file_arg = f"--env-file {env_file_path}" if env_file_path else ""
        try:
            logger.info("Performing optional pre-deployment cleanup...")
            cleanup_result = await DockerComposeRemoteVMUtils.run_docker_compose_cleanup(project_path, username=username, workspace_name=workspace_name)
            if cleanup_result.success:
                logger.info("Pre-deployment cleanup completed successfully")
            else:
                logger.info(f"Pre-deployment cleanup completed with warnings: {cleanup_result.error}")
        except Exception as cleanup_error:
            logger.info(f"Pre-deployment cleanup skipped due to error: {str(cleanup_error)}")
        try:
            logger.info("Performing optional system cleanup...")
            system_cleanup_result = DockerComposeRemoteVMUtils.run_system_cleanup()
            if system_cleanup_result.success:
                logger.info("System cleanup completed successfully")
            else:
                logger.info(f"System cleanup completed with warnings: {system_cleanup_result.error}")
        except Exception as system_cleanup_error:
            logger.info(f"System cleanup skipped due to error: {str(system_cleanup_error)}")
        try:
            services_ports = DockerComposeRemoteVMUtils._retrieve_external_service_ports(project_path=project_path)
            # Enable Fluentd logging in the compose file before deployment
            compose_file_path = DockerComposeRemoteVMUtils.get_compose_file_path(project_path=project_path)
            DockerComposeRemoteVMUtils.enable_fluentd_logging(compose_file_path, username, workspace_name)
            # Deploy
            deploy_command = DockerComposeRemoteVMUtils.generate_deploy_command(
                compose_file=compose_file_path,
                project_name=container_name,
                env_file_arg=env_file_arg,
                context_name=context_name
            )
            logger.info("Run command: " + deploy_command)
            run_result = DockerCommandWithLogHandler(project_path).run_docker_commands_with_logging(deploy_command, container_name=container_name)
            if run_result.success:
                docker_compose_logger = DockerComposeLogHandler(project_path)
                docker_compose_logger.follow_compose_logs(
                    compose_file=compose_file_path,
                    project_name=container_name
                )
                # Generate Traefik TOML for each service after deployment
                traefik_gen = TraefikTomlGenerator()
                service_name = generate_unique_name(project_base_path=project_path, username=username)
                toml, final_urls = traefik_gen.generate_toml(
                    service_name=service_name,
                    private_ip=private_ip,
                    service_ports=services_ports
                )
                logger.info(f"Generated Traefik TOML for {service_name}: {toml}")
                run_result.set_deploy_info(json.dumps({"container_name": container_name, "urls": final_urls}))
                return run_result
            return run_result
        except Exception as e:
            logger.error(f"Error in deploying to remote VM {traceback.format_exc()}")
            return CommandResult(success=False, error=str(e), deploy_info=json.dumps({"error": traceback.format_exc()}))

    @staticmethod
    def generate_deploy_command(compose_file, project_name, env_file_arg=None, context_name=None) -> str:
        """
        Generate the Docker Compose command for deployment.
        
        Returns:
            The full Docker Compose command as a string
        """
        command_parts = ["docker"]
        if context_name:
            command_parts.extend(["--context", context_name])
        command_parts.append("compose")
        
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
    
    @staticmethod
    def generate_build_command(compose_file, project_name, env_file_arg=None, context_name=None) -> str:
        """
        Generate the Docker Compose build command.
        
        Returns:
            The full Docker Compose build command as a string
        """
        command_parts = ["docker"]
        if context_name:
            command_parts.extend(["--context", context_name])
        command_parts.append("compose")
        
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
    async def run_docker_compose_cleanup(project_path, username=None, workspace_name=None) -> CommandResult:
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
        container_name = generate_unique_name(project_base_path=project_path, username=username)
        context_name = None
        if username and workspace_name:
            context_name, _ = await DockerComposeRemoteVMUtils.set_docker_context(username, workspace_name)
        try:
            cleanup_commands = [
                f'docker --context {context_name} compose -p {container_name} down --volumes --remove-orphans' if context_name else f'docker compose -p {container_name} down --volumes --remove-orphans',
                f'docker --context {context_name} images -q --filter "label=com.docker.compose.project={container_name}" | xargs -r docker --context {context_name} rmi -f 2>/dev/null || true' if context_name else f'docker images -q --filter "label=com.docker.compose.project={container_name}" | xargs -r docker rmi -f 2>/dev/null || true',
                f'docker --context {context_name} image prune -f' if context_name else 'docker image prune -f'
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
            if results and results[0].success:
                return CommandResult(
                    success=True, 
                    output="Selective cleanup completed successfully",
                    deploy_info="Project-specific cleanup completed"
                )
            else:
                return CommandResult(
                    success=True,
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