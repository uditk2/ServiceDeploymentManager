from typing import List, Dict, Optional
from app.models.workspace import UserWorkspace
from app.repositories.workspace_repository import WorkspaceRepository
from app.docker.zip_utils import ZipUtils
from app.docker.docker_compose_utils import DockerComposeUtils
from app.docker.docker_compose_remote_vm_utils import DockerComposeRemoteVMUtils
import os
import tempfile
import shutil
from app.custom_logging import logger
from app.workspace_monitoring.log_watcher_manager import log_watcher_manager
from app.docker.helper_functions import generate_project_name_from_user_workspace
from app.models.exceptions.known_exceptions import (
    WorkspaceUploadFailedException, 
    WorkspaceCreationFailedException,
    WorkspaceUpdateFailedException,
    WorkspaceNotFoundException
)
from app.models.results.workspace_controller_results import (
    CreateWorkspaceResult, 
    UpdateWorkspaceResult,
    UploadWorkspaceResult
)

class WorkspaceController:
    @staticmethod
    async def create_workspace(workspace: UserWorkspace) -> CreateWorkspaceResult:
        """Create a new user workspace"""
        try:
            workspace_id = await WorkspaceRepository.create_workspace(workspace)
            return  CreateWorkspaceResult(
                status="success",
                message="Workspace created successfully",
                workspace_id=workspace_id,
                workspace_name=workspace.workspace_name,
                username=workspace.username,
                workspace_path=workspace.workspace_path
            )
        except ValueError as e:
            raise WorkspaceCreationFailedException(str(e))
        except Exception as e:
            raise WorkspaceCreationFailedException(f"Failed to create workspace: {str(e)}")

    @staticmethod
    async def list_workspaces(username: str) -> List[UserWorkspace]:
        """List all workspaces for a user"""
        try:
            return await WorkspaceRepository.list_workspaces(username)
        except Exception as e:
            raise Exception(f"Failed to list workspaces: {str(e)}")

    @staticmethod
    async def get_workspace(username: str, workspace_name: str, raise_exception=True) -> UserWorkspace:
        """Get details of a specific workspace"""
        workspace = await WorkspaceRepository.get_workspace(username, workspace_name)
        if not workspace and raise_exception:
            raise ValueError(f"Workspace {workspace_name} not found for user {username}")
        return workspace

    @staticmethod
    async def update_workspace(username: str, workspace_name: str, data: dict) -> UpdateWorkspaceResult:
        """Update an existing workspace"""
        try:
            updated = await WorkspaceRepository.update_workspace(username, workspace_name, data)
            if not updated:
                raise ValueError(f"Workspace {workspace_name} not found for user {username}")

            return UpdateWorkspaceResult(
                status="success",
                message="Workspace updated successfully",
                data=data,
                username=username,
                workspace_name=workspace_name
            )
        except ValueError as e:
            raise WorkspaceUpdateFailedException(str(e))
        except Exception as e:
            raise WorkspaceUpdateFailedException(f"Failed to update workspace: {str(e)}")

    @staticmethod
    async def delete_workspace(username: str, workspace_name: str) -> Dict:
        """Delete a workspace and its resources"""
        try:
            logger.info(f"Starting workspace deletion for: {username}/{workspace_name}")
            # Get workspace details first
            workspace = await WorkspaceRepository.get_workspace(username, workspace_name)
            if not workspace:
                raise WorkspaceNotFoundException(f"Workspace {workspace_name} not found for user {username}")

            logger.info(f"Found workspace with VM config: {workspace.vm_config is not None}")
            if workspace.vm_config:
                logger.info(f"VM config details - IP: {workspace.vm_config.private_ip}, Status: {workspace.vm_config.status}")

            # Stop any active log watchers for this workspace
            try:
                project_name = generate_project_name_from_user_workspace(username, workspace_name)
                
                # Stop log watcher if the manager is initialized
                if log_watcher_manager._initialized and log_watcher_manager._log_handler:
                    if project_name in log_watcher_manager._log_handler.log_watchers:
                        logger.info(f"Stopping log watcher for workspace deletion: {username}/{workspace_name}")
                        log_watcher_manager._log_handler._cleanup_process(project_name)
                        
            except Exception as e:
                logger.warning(f"Error stopping log watcher during workspace deletion: {str(e)}")
                # Don't fail the deletion if log watcher cleanup fails

            # Stop and remove any running containers
            try:
                # Use remote VM utils for workspaces with VM configuration
                logger.info(f"Using remote VM Docker compose down for workspace: {username}/{workspace_name}")
                await DockerComposeRemoteVMUtils.run_docker_compose_down(
                    project_path=workspace.workspace_path,
                    username=username,
                    workspace_name=workspace_name
                )
            except Exception as e:
                logger.error(f"Error cleaning up containers: {str(e)}")

            # Remove workspace files
            if os.path.exists(workspace.workspace_path):
                try:
                    shutil.rmtree(workspace.workspace_path)
                except Exception as e:
                    raise Exception(f"Failed to remove workspace files: {str(e)}")

            # Finally delete from database
            deleted = await WorkspaceRepository.delete_workspace(username, workspace_name)
            if not deleted:
                raise Exception("Failed to delete workspace from database")

            return {"status": "success", "message": "Workspace deleted successfully"}
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise Exception(f"Failed to delete workspace: {str(e)}")

    @staticmethod
    async def upload_workspace(username: str, workspace_name: str, zip_file, docker_image_name: Optional[str] = None) -> UploadWorkspaceResult:
        """Upload and extract a workspace from a zip file"""
        try:
            # Check if workspace exists
            workspace = await WorkspaceRepository.get_workspace(username, workspace_name)
            
            # Create a temporary file to store the uploaded zip
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
                temp_path = temp_file.name
            
            # Save the uploaded file to the temporary file
            with open(temp_path, 'wb') as f:
                shutil.copyfileobj(zip_file.file, f)
            
            # Extract the zip file
            destination_path = ZipUtils.extract_zip_file(temp_path, username, workspace_name)
            # Clean up the temporary file
            os.unlink(temp_path)

            # If workspace doesn't exist, create it
            if not workspace:
                new_workspace = UserWorkspace(username=username, workspace_name=workspace_name, workspace_path=destination_path)
                await WorkspaceRepository.create_workspace(new_workspace)
                logger.info(f"Created new workspace: {username}/{workspace_name}")
            else:
                # Update existing workspace path
                await WorkspaceRepository.update_workspace(
                    username=username,
                    workspace_name=workspace_name,
                    update_data={"workspace_path": destination_path}
                )
                logger.info(f"Updated existing workspace: {username}/{workspace_name}")
            return UploadWorkspaceResult(
                status="success",
                message="Workspace uploaded and extracted successfully",
                workspace_path=destination_path
            )
        except WorkspaceCreationFailedException as e:
            raise WorkspaceUploadFailedException(f"Failed to create workspace: {str(e)}") from e
        except Exception as e:
            raise WorkspaceUploadFailedException(f"Failed to upload workspace: {str(e)}") from e