from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

class TriggeredJob(BaseModel):
    """
    Model for storing jobs triggered on behalf of users
    
    job_id is unique across all jobs
    """
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    workspace_name: str
    job_type: str  # e.g., "build", "deploy", "test"
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    artifact_location: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    class Config:
        schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "username": "john_doe",
                "workspace_name": "my-app",
                "job_type": "deploy",
                "status": "completed",
                "artifact_location": "/app/logs/john_doe/my-app/deploy_550e8400.log",
                "metadata": {
                    "version": "v1.2.0",
                    "environment": "production"
                }
            }
        }