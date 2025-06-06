from fastapi import APIRouter, HTTPException
from typing import List, Optional
from app.models.job import TriggeredJob
from app.repositories.job_repository import JobRepository
from app.controllers.workspace_controller import WorkspaceController

router = APIRouter(
    prefix="/api/jobs",
    tags=["jobs"]
)

@router.post("", response_model=dict)
async def create_job(job: TriggeredJob):
    """Create a new job"""
    try:
        job_id = await JobRepository.create_job(job)
        return {"status": "success", "message": "Job created successfully", "job_id": job_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create job: {str(e)}")

@router.get("/{job_id}", response_model=TriggeredJob)
async def get_job(job_id: str):
    """Get details of a specific job"""
    job = await JobRepository.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found")
    return job

@router.get("/user/{username}", response_model=List[TriggeredJob])
async def list_user_jobs(username: str):
    """List all jobs for a user"""
    try:
        jobs = await JobRepository.list_jobs_by_user(username)
        return jobs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {str(e)}")

@router.get("/workspace/{username}/{workspace_name}", response_model=List[TriggeredJob])
async def list_workspace_jobs(username: str, workspace_name: str):
    """List all jobs for a specific workspace"""
    try:
        # First, verify the workspace exists and get the actual workspace name
        workspace = await WorkspaceController.get_workspace(username, workspace_name)
        if not workspace:
            raise HTTPException(status_code=404, 
                               detail=f"Workspace '{workspace_name}' not found for user '{username}'")
        
        # Use the actual workspace name from database for job lookup
        jobs = await JobRepository.list_jobs_by_workspace(username, workspace.workspace_name)
        return jobs
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list workspace jobs: {str(e)}")

@router.put("/{job_id}/status", response_model=dict)
async def update_job_status(job_id: str, status: str, artifact_location: Optional[str] = None):
    """Update the status of a job"""
    if status not in ["pending", "running", "completed", "failed"]:
        raise HTTPException(status_code=400, detail="Invalid status value")
    
    success = await JobRepository.update_job_status(job_id, status, artifact_location)
    if not success:
        raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found")
    
    return {"status": "success", "message": f"Job status updated to {status}"}


@router.delete("/{job_id}", response_model=dict)
async def delete_job(job_id: str):
    """Delete a specific job"""
    success = await JobRepository.delete_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found")
    return {"status": "success", "message": "Job deleted successfully"}