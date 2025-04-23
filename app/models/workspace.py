from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class UserWorkspace(BaseModel):
    """
    Model for storing user workspace information
    
    username and workspace_name together form a unique key
    """
    username: str
    workspace_name: str
    api_keys: Optional[Dict[str, str]] = Field(default_factory=dict)
    docker_image_name: Optional[str] = None
    deployed_versions: Optional[List[str]] = Field(default_factory=list)
    workspace_path: str
    service_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        schema_extra = {
            "example": {
                "username": "john_doe",
                "workspace_name": "my-app",
                "api_keys": {
                    "github": "ghp_123456789abcdef",
                    "aws": "AKIAIOSFODNN7EXAMPLE"
                },
                "docker_image_name": "my-app:latest",
                "deployed_versions": ["v1.2.0", "v1.1.0", "v1.0.0"],
                "service_url": "https://my-app.example.com"
            }
        }