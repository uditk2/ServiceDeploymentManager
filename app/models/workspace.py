from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class VMConfig(BaseModel):
    """Model for VM configuration within workspace"""
    vm_name: Optional[str] = None
    vm_id: Optional[str] = None
    resource_group: Optional[str] = None
    location: Optional[str] = None
    vm_size: Optional[str] = None
    private_ip: Optional[str] = None
    nic_id: Optional[str] = None
    vnet_name: Optional[str] = None
    subnet_name: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    created_at: Optional[float] = None
    last_checked: Optional[datetime] = None

class LogWatcherInfo(BaseModel):
    """Embedded model for log watcher state within workspace"""
    status: str = "inactive"  # inactive, active, stopped, failed, orphaned
    project_name: Optional[str] = None  # Docker Compose project name
    log_handler_pid: Optional[int] = None
    log_file_path: Optional[str] = None
    last_health_check: Optional[datetime] = None
    error_count: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    retain_logs: bool = True
    
    def mark_as_active(self, project_name: str, pid: Optional[int] = None, log_file: Optional[str] = None):
        """Mark the watcher as active with process information"""
        self.status = "active"
        self.project_name = project_name
        self.last_health_check = datetime.utcnow()
        if pid:
            self.log_handler_pid = pid
        if log_file:
            self.log_file_path = log_file
        self.error_count = 0
        self.last_error = None
    
    def mark_as_stopped(self):
        """Mark the watcher as stopped"""
        self.status = "stopped"
        self.log_handler_pid = None
    
    def mark_as_failed(self, error_message: str):
        """Mark the watcher as failed with error details"""
        self.status = "failed"
        self.error_count += 1
        self.last_error = error_message
        self.last_error_time = datetime.utcnow()
        self.log_handler_pid = None
    
    def should_be_resurrected(self) -> bool:
        """Determine if this watcher should be resurrected on startup"""
        return self.status in ["active", "stopped"] and self.error_count < 5

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
    
    # Log watcher state
    log_watcher: LogWatcherInfo = Field(default_factory=LogWatcherInfo)
    
    # VM configuration for spot VM deployment
    vm_config: Optional[VMConfig] = None

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
                "service_url": "https://my-app.example.com",
                "log_watcher": {
                    "status": "active",
                    "project_name": "john-doe-my-app",
                    "log_handler_pid": 12345,
                    "log_file_path": "/logs/john-doe-my-app-compose.log"
                }
            }
        }