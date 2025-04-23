from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from typing import List, Optional
from app.models.workspace import UserWorkspace
from app.controllers.workspace_controller import WorkspaceController

router = APIRouter(
    prefix="/api/workspaces",
    tags=["workspaces"]
)

@router.post("", response_model=dict)
async def create_workspace(workspace: UserWorkspace):
    """Create a new user workspace"""
    try:
        return await WorkspaceController.create_workspace(workspace)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{username}", response_model=List[UserWorkspace])
async def list_user_workspaces(username: str):
    """List all workspaces for a user"""
    try:
        return await WorkspaceController.list_workspaces(username)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{username}/{workspace_name}", response_model=UserWorkspace)
async def get_workspace(username: str, workspace_name: str):
    """Get details of a specific workspace"""
    try:
        return await WorkspaceController.get_workspace(username, workspace_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{username}/{workspace_name}", response_model=dict)
async def update_workspace(username: str, workspace_name: str, data: dict):
    """Update an existing workspace"""
    try:
        return await WorkspaceController.update_workspace(username, workspace_name, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{username}/{workspace_name}", response_model=dict)
async def delete_workspace(username: str, workspace_name: str):
    """Delete a workspace"""
    try:
        return await WorkspaceController.delete_workspace(username, workspace_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload/{username}/{workspace_name}", response_model=dict)
async def upload_workspace(
    username: str, 
    workspace_name: str, 
    zip_file: UploadFile = File(...),
    docker_image_name: Optional[str] = Form(None)
):
    """
    Upload a workspace as a zip file.
    The zip file will be extracted to the workspace directory.
    If the workspace doesn't exist, it will be created.
    """
    try:
        return await WorkspaceController.upload_workspace(
            username=username,
            workspace_name=workspace_name,
            zip_file=zip_file,
            docker_image_name=docker_image_name
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))