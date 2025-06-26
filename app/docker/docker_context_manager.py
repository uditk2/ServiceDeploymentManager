import subprocess
import asyncio
import os
from typing import Optional
from app.repositories.workspace_repository import WorkspaceRepository
from app.custom_logging import logger
from app.docker.helper_functions import generate_context_name_from_user_workspace
from app.models.exceptions.known_exceptions import (
    VMNotFoundException,
    DockerContextSetException
)
from app.models.results.vm_operation_results import VMInfoResult
from app.models.results.docker_operation_results import DockerContextResult
class DockerContextManager:
    """
    Manages Docker contexts for user workspaces by fetching VM info and setting the Docker context.
    """

    @staticmethod
    async def get_vm_info_for_user_workspace(username: str, workspace_name: str) -> Optional[VMInfoResult]:
        """
        Fetch VM info for a user workspace from the database.
        Returns a dict with at least 'ip' or 'hostname' if available, else None.
        """
        workspace = await WorkspaceRepository.get_workspace(username, workspace_name)
        if workspace and workspace.vm_config and workspace.vm_config.private_ip:
            return VMInfoResult(
                ip=workspace.vm_config.private_ip,
                vm_name=workspace.vm_config.vm_name,
                vm_status=workspace.vm_config.status
            )
        raise VMNotFoundException(f"VM not found for workspace {workspace_name} of user {username}")

    @staticmethod
    def _remove_known_host(host: str):
        """
        Remove the host entry from ~/.ssh/known_hosts to avoid SSH key verification issues.
        """
        known_hosts = os.path.expanduser('~/.ssh/known_hosts')
        if os.path.exists(known_hosts):
            subprocess.run(["ssh-keygen", "-R", host], check=False)

    @staticmethod
    async def set_context_for_user_workspace(username: str, workspace_name: str, user: str = 'azureuser')-> DockerContextResult:
        """
        Asynchronously fetches VM info for the user workspace and sets the Docker context.
        SSH configuration is already set up in the Dockerfile.
        Returns a tuple: (context_name, private_ip)
        """
        logger.info(f"Setting Docker context for workspace {username}/{workspace_name}")
        vm_info = await DockerContextManager.get_vm_info_for_user_workspace(username, workspace_name)
        host = vm_info.ip
        context_name = generate_context_name_from_user_workspace(username, workspace_name)
        
        # Create SSH connection string
        docker_host = f"ssh://{user}@{host}"
        
        logger.info(f"Context details - name: {context_name}, host: {docker_host}")
        
        # Remove known host entry to avoid SSH key verification issues
        DockerContextManager._remove_known_host(host)
        
        # Check if context already exists
        result = subprocess.run(
            ["docker", "context", "inspect", context_name], 
            capture_output=True, 
            check=False
        )
        if result.returncode == 0:
            # Context already exists, no need to create it again
            logger.debug(f"Docker context '{context_name}' already exists.")
            return DockerContextResult(
                context_name=context_name,
                ip=vm_info.ip
            )

        # Create Docker context (SSH config is already set up in Dockerfile)
        logger.info(f"Creating Docker context '{context_name}' with host '{docker_host}'")
        
        create_result = subprocess.run([
            "docker", "context", "create", context_name,
            "--docker", f"host={docker_host}",
            "--description", f"Workspace {username}/{workspace_name} context"
        ], capture_output=True, check=False)
        
        if create_result.returncode != 0:
            error_output = create_result.stderr.decode().strip()
            error_msg = f"Failed to create Docker context '{context_name}': {error_output}"
            logger.error(error_msg)
            raise DockerContextSetException(error_msg)
        
        logger.info(f"Docker context '{context_name}' created successfully")
        return DockerContextResult(
            context_name=context_name,
            ip=vm_info.ip
        )

    @staticmethod
    def remove_context_for_user_workspace(username: str, workspace_name: str):
        """
        Removes the Docker context for the user workspace.
        """
        context_name = generate_context_name_from_user_workspace(username, workspace_name)
        result = subprocess.run(
            ["docker", "context", "rm", context_name],
            capture_output=True,
            check=False
        )
        if result.returncode == 0:
            logger.info(f"Docker context '{context_name}' removed successfully.")
            return True
        else:
            logger.error(f"Failed to remove Docker context '{context_name}': {result.stderr.decode().strip()}")
            return False