import asyncio
import subprocess
import tempfile
import shutil
import os
from fastapi import APIRouter, HTTPException, File, UploadFile
from typing import Dict, Optional
from pydantic import BaseModel
import traceback
from app.docker.docker_compose_utils import DockerComposeUtils
from app.docker.docker_compose_remote_vm_utils import DockerComposeRemoteVMUtils
from app.docker.helper_functions import generate_unique_name
from app.docker.utils import DockerUtils
from app.docker.zip_utils import ZipUtils
from app.docker.config import DockerConfig
from app.docker.docker_log_handler import CommandResult
from app.models.job import TriggeredJob
from app.repositories.job_repository import JobRepository
from app.controllers.workspace_controller import WorkspaceController
from app.docker.server_error_identifier import ServerErrorIdentifier
from app.models.workspace import UserWorkspace
from app.custom_logging import logger
import uuid
router = APIRouter(
    prefix="/api/docker",
    tags=["docker"]
)

@router.post("/build_deploy/{username}/{workspace_name}", response_model=dict)
async def build_deploy_job(username: str, workspace_name: str, zip_file: UploadFile = File(...)):  
    try:
        user_workspace = await WorkspaceController.get_workspace(username, workspace_name, raise_exception=False)
        if not user_workspace:
            workspace = UserWorkspace(username=username, workspace_name=workspace_name, workspace_path=DockerConfig.get_project_dir(username, workspace_name))
            user_workspace = await WorkspaceController.create_workspace(workspace)
    
        # Save the uploaded file to a temporary file that can be accessed in the background task
        temp_file_path = None
        # Create a temporary file to store the uploaded zip
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
            temp_file_path = temp_file.name
            # Save the uploaded file to the temporary file
            shutil.copyfileobj(zip_file.file, temp_file)
        job = TriggeredJob(job_id= str(uuid.uuid4()), username=username, workspace_name=user_workspace.workspace_name, status="pending", job_type="build_deploy")
        job_id = await JobRepository.create_job(job)  
        # Create background task with the temp file path using actual workspace name
        asyncio.create_task(run_build_deploy_job(username=username, workspace_name=user_workspace.workspace_name, job_id=job_id, temp_file_path=temp_file_path))
        return {"status": "success", "message": "Job created successfully. Check job status for updates.", "job_id": job_id}
    except Exception as e:
        logger.error(f"Error in build_deploy_job: {traceback.format_exc()}")
        # Clean up the temporary file if an error occurs
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        await JobRepository.update_job_status(
            job_id=job_id,
            status="failed",
            metadata={
                "error": "Internal Server Error. Please try again later. We are looking into this issue.",
                "server_error": True
            }
        )


async def run_build_deploy_job(username: str, workspace_name: str, job_id: str, temp_file_path: str):
    try:
        result = None
        # Create a file-like object from the temp file
        with open(temp_file_path, 'rb') as file:
            upload_file = UploadFile(filename=f"{workspace_name}.zip",file=file)
            # Process the upload
            result = await WorkspaceController.upload_workspace(username=username, workspace_name=workspace_name, zip_file=upload_file)
        # Continue with job processing
        await JobRepository.update_job_status(job_id=job_id,status="running",metadata={"update": result.model_dump_json()})
        workspace = await WorkspaceController.get_workspace(username, workspace_name)
        # Build the Docker image
        result = await DockerComposeRemoteVMUtils.run_docker_compose_down(workspace.workspace_path, username, workspace_name=workspace.workspace_name)
        await JobRepository.update_job_status(job_id=job_id,status="running",metadata={"update": result.model_dump_json()})
        result = await DockerComposeRemoteVMUtils.run_docker_compose_build(workspace.workspace_path, username, workspace_name=workspace.workspace_name)
        if result.success is False:
            error_type = ServerErrorIdentifier().identify_error(result.error)
            metadata = {"error": result.model_dump_json()}
            if error_type is not None:
                metadata["server_error"] = True
            await JobRepository.update_job_status(job_id=job_id, status="failed", metadata=metadata)
            return
        await JobRepository.update_job_status(job_id=job_id, status="running", metadata={"update": result.model_dump_json()})
        # Start the Docker container
        result = await DockerComposeRemoteVMUtils.run_docker_compose_deploy(workspace.workspace_path, username, workspace_name=workspace.workspace_name)
        if result.success is False:
            await JobRepository.update_job_status(job_id=job_id, status="failed", metadata={"error": result.model_dump_json()})
            return
        await JobRepository.update_job_status(job_id=job_id, status="completed", metadata={"output": result.metadata})
    except Exception as e:
        # Update job status with error
        ## TODO: Raise an error into your system monitoring tool
        logger.error(f"Error in run_build_deploy_job: {traceback.format_exc()}")
        await JobRepository.update_job_status(
            job_id=job_id,
            status="failed",
            metadata={
                "error": "Internal Server Error. Please try again later. We are looking into this issue.",
                "server_error": True
            }
        )
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

@router.post("/cleanup/{username}/{workspace_name}", response_model=dict)
async def cleanup_workspace(username: str, workspace_name: str):
    """
    Perform comprehensive cleanup for a specific workspace including:
    - Stop and remove containers
    - Remove project-specific images
    - Clean up dangling images and volumes
    """
    try:
        workspace = await WorkspaceController.get_workspace(username, workspace_name)
        if not workspace:
            raise HTTPException(status_code=404, detail=f"Workspace {workspace_name} not found for user {username}")
        
        logger.info(f"Starting cleanup for workspace {username}/{workspace_name}")
        cleanup_result = await DockerComposeRemoteVMUtils.run_docker_compose_cleanup(workspace.workspace_path, username=username, workspace_name=workspace_name)

        if cleanup_result.success:
            return {
                "status": "success",
                "message": "Workspace cleanup completed successfully",
                "details": cleanup_result.output
            }
        else:
            return {
                "status": "error", 
                "message": "Cleanup completed with some failures",
                "error": cleanup_result.error
            }
            
    except Exception as e:
        logger.error(f"Error during workspace cleanup: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to cleanup workspace: {str(e)}")  


@router.post("/build/{username}/{workspace_name}", response_model=dict)
async def build_job(
    username: str, 
    workspace_name: str, 
    zip_file: UploadFile = File(...)
): 
    user_workspace = await WorkspaceController.get_workspace(username, workspace_name, raise_exception=False)
    if not user_workspace:
        workspace = UserWorkspace(
            username=username,
            workspace_name=workspace_name,
            workspace_path=DockerConfig.get_project_dir(username, workspace_name)
        )
        user_workspace = await WorkspaceController.create_workspace(workspace)
    
    # Use the actual workspace name from the database for job creation
    actual_workspace_name = user_workspace.workspace_name if user_workspace else workspace_name
    
    job = TriggeredJob(
        job_id= str(uuid.uuid4()),
        username=username,
        workspace_name=actual_workspace_name,
        status="pending",
        job_type="build"
    )
    job_id = await JobRepository.create_job(job)
    
    # Save the uploaded file to a temporary file that can be accessed in the background task
    temp_file_path = None
    try:
        # Create a temporary file to store the uploaded zip
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
            temp_file_path = temp_file.name
            # Save the uploaded file to the temporary file
            shutil.copyfileobj(zip_file.file, temp_file)
            
        # Create background task with the temp file path using actual workspace name
        asyncio.create_task(run_build_job(
            username=username,
            workspace_name=actual_workspace_name,
            job_id=job_id,
            temp_file_path=temp_file_path
        ))
        
        return {
            "status": "success",
            "message": "Build job created successfully. Check job status for updates.",
            "job_id": job_id
        }
    except Exception as e:
        # Clean up the temporary file if an error occurs
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        raise HTTPException(status_code=500, detail=f"Failed to process upload: {str(e)}")


async def run_build_job(username: str, workspace_name: str, job_id: str, temp_file_path: str):
    try:
        # Create a file-like object from the temp file
        with open(temp_file_path, 'rb') as file:
            # Use FastAPI's UploadFile to match the expected interface
            upload_file = UploadFile(
                filename=f"{workspace_name}.zip",
                file=file
            )
            
            # Process the upload
            upload_status = await WorkspaceController.upload_workspace(
                username=username, 
                workspace_name=workspace_name, 
                zip_file=upload_file
            )
            
        # Continue with job processing
        await JobRepository.update_job_status(job_id=job_id,status="running",
            metadata={"update": upload_status.model_dump_json()}
        )
        workspace = await WorkspaceController.get_workspace(username, workspace_name)
        
        # Build the Docker image
        result = await DockerComposeRemoteVMUtils.run_docker_compose_build(workspace.workspace_path, username, workspace_name=workspace_name)

        await JobRepository.update_job_status(job_id=job_id,status="completed",metadata= {"output": result.metadata})
        
    except Exception as e:
        # Update job status with error
        await JobRepository.update_job_status(job_id=job_id,status="failed",
        metadata={
                "error": "Internal Server Error. Please try again later. We are looking into this issue.",
                 "server_error": True
            }
        )
        logger.error(f"Error in run_build_job: {traceback.format_exc()}")
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)