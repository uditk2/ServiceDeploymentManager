from typing import List, Optional, Dict, Any
from app.database import job_collection
from app.models.job import TriggeredJob
from datetime import datetime

class JobRepository:
    """Repository for managing triggered jobs data in MongoDB"""
    
    @staticmethod
    async def create_job(job: TriggeredJob) -> str:
        """Create a new job"""
        job_dict = job.dict()
        result = await job_collection.insert_one(job_dict)
        return job.job_id
    
    @staticmethod
    async def get_job(job_id: str) -> Optional[TriggeredJob]:
        """Get a job by its ID"""
        job_dict = await job_collection.find_one({"job_id": job_id})
        
        if job_dict:
            return TriggeredJob(**job_dict)
        return None
    
    @staticmethod
    async def list_jobs_by_user(username: str) -> List[TriggeredJob]:
        """List all jobs for a user"""
        cursor = job_collection.find({"username": username}).sort("created_at", -1)
        jobs = []
        
        async for job_dict in cursor:
            jobs.append(TriggeredJob(**job_dict))
        
        return jobs
    
    @staticmethod
    async def list_jobs_by_workspace(username: str, workspace_name: str) -> List[TriggeredJob]:
        """List all jobs for a specific workspace"""
        cursor = job_collection.find({
            "username": username,
            "workspace_name": workspace_name
        }).sort("created_at", -1)
        
        jobs = []
        
        async for job_dict in cursor:
            jobs.append(TriggeredJob(**job_dict))
        
        return jobs
    
    @staticmethod
    async def update_job_status(job_id: str, status: str, artifact_location: Optional[str] = None, 
                               metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Update job status and related information"""
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow()
        }
        
        if status in ["completed", "failed"]:
            update_data["completed_at"] = datetime.utcnow()
        
        if artifact_location:
            update_data["artifact_location"] = artifact_location
        
        if metadata:
            update_data["metadata"] = metadata
        
        result = await job_collection.update_one(
            {"job_id": job_id},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
    
    @staticmethod
    async def delete_job(job_id: str) -> bool:
        """Delete a job"""
        job = await job_collection.find_one({"job_id": job_id})
        if not job:
            return False
        try:
            result = await job_collection.delete_one({"job_id": job_id})
            return result.deleted_count > 0
        except Exception:
            return False