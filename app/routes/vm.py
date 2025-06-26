import asyncio
import uuid
from fastapi import APIRouter, HTTPException
from typing import Dict

from app.models.job import TriggeredJob
from app.repositories.job_repository import JobRepository
from app.controllers.workspace_controller import WorkspaceController
from app.vm_manager.spot_vm_manager import SpotVMManager
from app.models.workspace import UserWorkspace
from app.docker.config import DockerConfig  # for project dir generation similar approach
from app.custom_logging import logger
import traceback
router = APIRouter(
    prefix="/api/vm",
    tags=["vm"]
)

@router.post("/ensure/{username}/{workspace_name}", response_model=dict)
async def ensure_vm_job(username: str, workspace_name: str):
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

        # Background task
        asyncio.create_task(run_ensure_vm_job(username, workspace_name, job_id))

        return {"status": "success", "message": "VM ensure job created", "job_id": job_id}
    except Exception as e:
        logger.error(f"Error creating ensure VM job: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

async def run_ensure_vm_job(username: str, workspace_name: str, job_id: str):
    """Background task to run ensure_vm and update job status"""
    try:
        # Update job status to running
        await JobRepository.update_job_status(job_id, "running")

        manager = SpotVMManager()
        # Use the async allocation method directly
        result = await manager.allocate_or_reuse_vm(user_id=username, workspace_id=workspace_name)

        # Update job as completed with VM result
        await JobRepository.update_job_status(job_id, "completed", metadata={"output": result.model_dump_json()})
    except Exception as e:
        logger.error(f"Error in ensure_vm_job task: {traceback.format_exc()}")
        await JobRepository.update_job_status(job_id,"failed",metadata={"error": str(e)})
