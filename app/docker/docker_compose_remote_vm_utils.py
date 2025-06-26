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
from app.models.results.docker_operation_results import DockerOperationResult, DockerOperationType
from app.models.exceptions.known_exceptions import (
    DockerComposeFileNotFoundException,
    DockerComposeBuildFailedException,
    DockerComposeDeployFailedException,
    DockerComposeDownFailedException,
    DockerComposeCleanupFailedException,
    DockerComposeSystemCleanupFailedException,
    DockerContextSetException
    )
class DockerComposeRemoteVMUtils:
    """
    Utilities for deploying and managing Docker Compose projects on a remote VM using Docker contexts.
    """
    @staticmethod
    async def run_docker_compose_down(project_path, username, workspace_name) -> DockerOperationResult:
        try:
            docker_context_result = await DockerContextManager.set_context_for_user_workspace(username, workspace_name)
            os.chdir(project_path)
            container_name = generate_unique_name(project_base_path=project_path, username=username)
            cmd = f'docker --context {docker_context_result.context_name} compose -p {container_name} down'
            result = DockerCommandWithLogHandler(project_path).run_docker_commands_with_logging(cmd, container_name=container_name)
            if result.success:
                logger.info(f"Docker Compose project {container_name} brought down successfully.")
                return DockerOperationResult(success=True, message=f"Docker Compose project {container_name} brought down successfully.", operation=DockerOperationType.DOWN)
            else:
                error_msg = f"Failed to bring down Docker Compose project {container_name}: {result.error}"
                logger.error(error_msg)
                return DockerOperationResult(success=False, error=error_msg, operation=DockerOperationType.DOWN)
        except DockerContextSetException as e:
            raise DockerComposeDownFailedException("Failed to bring down the Docker Compose project") from e
        except  Exception as e:
            raise DockerComposeDownFailedException(f"Error bringing down the Docker Compose project: {traceback.format_exc()}") from e
        

    @staticmethod
    async def run_docker_compose_build(project_path, username, workspace_name) -> DockerOperationResult:
        try:
            context = await DockerContextManager.set_context_for_user_workspace(username, workspace_name)
            os.chdir(project_path)
            container_name = generate_unique_name(project_base_path=project_path, username=username)
            compose_file = DockerComposeRemoteVMUtils.get_compose_file_path(project_path=project_path)
            cmd = DockerComposeRemoteVMUtils.generate_build_command(
                compose_file=compose_file,
                project_name=container_name,
                context_name=context.context_name
            )
            cmd_handler = DockerCommandWithLogHandler(project_path)
            result = cmd_handler.run_docker_commands_with_logging(cmd, container_name=container_name)
            return DockerOperationResult(
                success=result.success,
                message=result.output if result.success else None,
                error=result.error,
                operation=DockerOperationType.BUILD
            )
        except DockerContextSetException as e:
            logger.error(f"Failed to set Docker context: {traceback.format_exc()}")
            raise DockerComposeBuildFailedException("Failed to build the project") from e
        except Exception as e:
            logger.error(f"Error during Docker Compose build: {traceback.format_exc()}")
            raise DockerComposeBuildFailedException(f"Error during Docker Compose build: {traceback.format_exc()}") from e

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
    async def run_docker_compose_deploy(project_path, username, workspace_name, env_file_path=None)-> DockerOperationResult:

        try:
            logger.info("Performing optional pre-deployment cleanup...")
            await DockerComposeRemoteVMUtils.run_docker_compose_cleanup(project_path, username=username, workspace_name=workspace_name)
        except DockerContextSetException as e:
            raise DockerComposeDeployFailedException("Failed in cleanup stage for container deployment") from e
        try:
            context_result = await DockerContextManager.set_context_for_user_workspace(username, workspace_name)
            container_name = generate_unique_name(project_base_path=project_path, username=username)
            env_file_arg = f"--env-file {env_file_path}" if env_file_path else ""
            services_ports = DockerComposeRemoteVMUtils._retrieve_external_service_ports(project_path=project_path)
            # Enable Fluentd logging in the compose file before deployment
            compose_file_path = DockerComposeRemoteVMUtils.get_compose_file_path(project_path=project_path)
            DockerComposeRemoteVMUtils.enable_fluentd_logging(compose_file_path, username, workspace_name)
            # Deploy
            deploy_command = DockerComposeRemoteVMUtils.generate_deploy_command(
                compose_file=compose_file_path,
                project_name=container_name,
                env_file_arg=env_file_arg,
                context_name=context_result.context_name
            )
            logger.info("Run command: " + deploy_command)
            run_result = DockerCommandWithLogHandler(project_path).run_docker_commands_with_logging(deploy_command, container_name=container_name)
            if run_result.success is False:
                return DockerOperationResult(
                    success=False,
                    error=run_result.error,
                    output=run_result.output,
                    operation=DockerOperationType.UP
                )
            docker_compose_logger = DockerComposeLogHandler(project_path)
            docker_compose_logger.follow_compose_logs(compose_file=compose_file_path, project_name=container_name)
            traefik_gen = TraefikTomlGenerator()
            service_name = generate_unique_name(project_base_path=project_path, username=username)
            toml, final_urls = traefik_gen.generate_toml(service_name=service_name, private_ip=context_result.ip, service_ports=services_ports)
            return DockerOperationResult(
                success=True,
                message="Your project has been deployed successfully.",
                operation=DockerOperationType.UP,
                output=run_result.output,
                metadata={"container_name": container_name,"urls": final_urls}
            )
        except Exception as e:
            logger.error(f"Error in deploying to remote VM {traceback.format_exc()}")
            raise DockerComposeDeployFailedException(message=f"Error in deploying to remote VM: {traceback.format_exc()}", original_exception=e)

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
            if isinstance(env_file_arg, (tuple, list)):
                command_parts.extend(env_file_arg)
            else:
                command_parts.append(env_file_arg)
        
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
        try:
            os.chdir(project_path)
            container_name = generate_unique_name(project_base_path=project_path, username=username)
            context = await DockerContextManager.set_context_for_user_workspace(username, workspace_name)
            cleanup_commands = [
                f'docker --context {context.context_name} compose -p {container_name} down --volumes --remove-orphans',
                f'docker --context {context.context_name} images -q --filter "label=com.docker.compose.project={container_name}" | xargs docker --context {context.context_name} rmi -f 2>/dev/null || true',
                f'docker --context {context.context_name} image prune -f',
                f'docker --context {context.context_name} builder prune -f',
                f'docker --context {context.context_name} volume prune -f'
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
        except DockerContextSetException as e:
            raise DockerComposeCleanupFailedException(original_exception=e)