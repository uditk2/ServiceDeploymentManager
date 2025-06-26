from pydantic import BaseModel
from typing import Optional
from enum import Enum

class DockerOperationType(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    BUILD = "BUILD"

class DockerOperationResult(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
    operation: Optional[DockerOperationType] = None
    metadata: Optional[dict] = None

class DockerContextResult(BaseModel):
    context_name: Optional[str] = None
    ip: Optional[str] = None