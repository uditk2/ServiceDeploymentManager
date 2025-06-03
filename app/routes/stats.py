from fastapi import APIRouter, HTTPException
from typing import Dict, Optional

from app.controllers.workspace_controller import WorkspaceController
from app.docker.docker_stats import DockerStats

router = APIRouter(
    prefix="/api/stats",
    tags=["stats"]
)

@router.get("/{username}/{workspace_name}")
async def get_docker_stats(username: str, workspace_name: str) -> Dict:
    """
    Get statistics for Docker containers in a workspace
    
    Args:
        username: The username of the workspace owner
        workspace_name: The name of the workspace
    
    Returns:
        Dict: Statistics for all Docker containers in the workspace
    """
    try:
        # First, verify the workspace exists and get its details
        workspace = await WorkspaceController.get_workspace(username, workspace_name)
        if not workspace:
            raise HTTPException(status_code=404, 
                               detail=f"Workspace '{workspace_name}' not found for user '{username}'")
        
        # Get the workspace path and retrieve stats
        stats = DockerStats.get_workspace_stack_stats(
            username=username,
            workspace_name=workspace_name,
            workspace_path=workspace.workspace_path
        )
        
        # Check if there was an error getting stats
        if "error" in stats and not "stats" in stats:
            raise HTTPException(status_code=500, 
                               detail=f"Failed to get Docker stats: {stats['error']}")
        
        # Return the stats
        return {
            "username": username,
            "workspace_name": workspace_name,
            "stats": stats
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving Docker stats: {str(e)}")