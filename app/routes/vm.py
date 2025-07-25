import asyncio
import uuid
from fastapi import APIRouter, HTTPException
from typing import Dict, Optional
from pydantic import BaseModel

from app.models.job import TriggeredJob
from app.repositories.job_repository import JobRepository
from app.controllers.workspace_controller import WorkspaceController
from app.vm_manager.spot_vm_manager import SpotVMManager
from app.models.workspace import UserWorkspace
from app.docker.config import DockerConfig  # for project dir generation similar approach
from app.custom_logging import logger
import traceback

class EnsureVMRequest(BaseModel):
    create: bool = True
    vm_size: Optional[str] = None  # Optional VM size, can be used to specify size if needed

router = APIRouter(
    prefix="/api/vm",
    tags=["vm"]
)

@router.get("/is_ready/{username}/{workspace_name}", response_model=dict)
async def is_vm_ready(username: str, workspace_name: str):
    """
    Check if VM is ready by verifying docker availability on the remote VM
    """
    try:
        manager = SpotVMManager()
        is_ready = await manager.is_vm_docker_ready(username, workspace_name)
        
        return {
            "status": "success", 
            "vm_ready": is_ready,
            "message": "Docker available" if is_ready else "Docker not available or VM not accessible"
        }
    except Exception as e:
        logger.error(f"Error checking VM readiness: {traceback.format_exc()}")
        return {
            "status": "error",
            "vm_ready": False, 
            "message": str(e)
        }

@router.post("/ensure/{username}/{workspace_name}", response_model=dict)
async def ensure_vm_job(username: str, workspace_name: str, request: Optional[EnsureVMRequest] = None):
    """
    Create a job to ensure a spot VM exists (create or start) for given user and workspace
    """
    # Ensure workspace exists in DB
    try:
        user_workspace = await WorkspaceController.get_workspace(username, workspace_name, raise_exception=False)
        if not user_workspace:
            workspace = UserWorkspace(username=username, workspace_name=workspace_name, workspace_path=DockerConfig.get_project_dir(username, workspace_name))
            user_workspace = await WorkspaceController.create_workspace(workspace)

        # Create job entry
        job = TriggeredJob(job_id=str(uuid.uuid4()), username=username, workspace_name=user_workspace.workspace_name,status="pending",job_type="ensure_vm")
        job_id = await JobRepository.create_job(job)

        # Handle optional request body - default to create=True if not provided
        create_vm = request.create if request else True
        vm_size = request.vm_size if request and request.vm_size else None

        # Background task
        asyncio.create_task(run_ensure_vm_job(username, workspace_name, job_id, create_vm, vm_size=vm_size))

        return {"status": "success", "message": "VM ensure job created", "job_id": job_id}
    except Exception as e:
        logger.error(f"Error creating ensure VM job: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

async def run_ensure_vm_job(username: str, workspace_name: str, job_id: str, create: bool = True, vm_size: Optional[str] = None):
    """Background task to run ensure_vm and update job status"""
    try:
        # Update job status to running
        await JobRepository.update_job_status(job_id, "running")

        manager = SpotVMManager()
        # Use the async allocation method directly
        vm_result = await manager.allocate_or_reuse_vm(user_id=username, workspace_id=workspace_name, force_recreate=create, vm_size=vm_size)
        
        result = False
        tries = 1
        while not result and tries <= 15:
            # Check if VM is ready
            await JobRepository.update_job_status(job_id, "running", metadata={"output": f"Checking VM readiness...{tries}"})
            result = await manager.is_vm_docker_ready(username, workspace_name)
            if not result:
                await asyncio.sleep(10)
                tries += 1
        
        # Check final readiness status
        if result:
            # Update job as completed with VM result
            await JobRepository.update_job_status(job_id, "completed", metadata={"output": vm_result.model_dump_json()})
        else:
            # VM is not ready after maximum tries
            await JobRepository.update_job_status(job_id, "failed", metadata={"error": f"VM not ready after {tries-1} attempts (150 seconds)"})
            
    except Exception as e:
        logger.error(f"Error in ensure_vm_job task: {traceback.format_exc()}")
        await JobRepository.update_job_status(job_id,"failed",metadata={"error": str(e)})
