from typing import List, Dict, Optional
from app.models.workspace import UserWorkspace
from app.repositories.workspace_repository import WorkspaceRepository
from app.docker.zip_utils import ZipUtils
from app.docker.dockerfile_utils import DockerFileUtils
from app.docker.docker_compose_utils import DockerComposeUtils
import os
import tempfile
import shutil
from app.custom_logging import logger

class WorkspaceController:
    @staticmethod
    async def create_workspace(workspace: UserWorkspace) -> Dict:
        """Create a new user workspace"""
        try:
            workspace_id = await WorkspaceRepository.create_workspace(workspace)
            return {
                "status": "success", 
                "message": "Workspace created successfully", 
                "workspace_id": workspace_id
            }
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise Exception(f"Failed to create workspace: {str(e)}")

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
    async def update_workspace(username: str, workspace_name: str, data: dict) -> Dict:
        """Update an existing workspace"""
        try:
            updated = await WorkspaceRepository.update_workspace(username, workspace_name, data)
            if not updated:
                raise ValueError(f"Workspace {workspace_name} not found for user {username}")
            return {"status": "success", "message": "Workspace updated successfully"}
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise Exception(f"Failed to update workspace: {str(e)}")

    @staticmethod
    async def delete_workspace(username: str, workspace_name: str) -> Dict:
        """Delete a workspace and its resources"""
        try:
            # Get workspace details first
            workspace = await WorkspaceRepository.get_workspace(username, workspace_name)
            if not workspace:
                raise ValueError(f"Workspace {workspace_name} not found for user {username}")

            # Stop and remove any running containers
            try:
                # Try docker-compose down first
                result = DockerComposeUtils.run_docker_compose_down(
                    project_path=workspace.workspace_path,
                    user_id=username
                )
                if not result or not result.success:
                    # Fallback to regular docker stop/remove
                    DockerFileUtils.run_docker_stop(
                        project_path=workspace.workspace_path,
                        user_id=username
                    )
                    DockerFileUtils.run_docker_remove(
                        project_path=workspace.workspace_path,
                        user_id=username
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
    async def upload_workspace(
        username: str,
        workspace_name: str,
        zip_file,
        docker_image_name: Optional[str] = None
    ) -> Dict:
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
            result = ZipUtils.extract_zip_file(temp_path, username, workspace_name)
            
            # Clean up the temporary file
            os.unlink(temp_path)
            
            if not result["success"]:
                raise ValueError(result["message"])
            
            # If workspace doesn't exist, create it
            if not workspace:
                new_workspace = UserWorkspace(
                    username=username,
                    workspace_name=workspace_name,
                    workspace_path=result["project_path"]
                )
                await WorkspaceRepository.create_workspace(new_workspace)
                logger.info(f"Created new workspace: {username}/{workspace_name}")
            
            return {
                "status": "success",
                "message": "Workspace uploaded and extracted successfully",
                "workspace_path": result["project_path"]
            }
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            raise Exception(f"Failed to upload workspace: {str(e)}")