from pydantic import BaseModel

class UploadWorkspaceResult(BaseModel):
    status: str
    message: str
    workspace_path: str
    error: str = None


class CreateWorkspaceResult(BaseModel):
    status: str
    message: str
    workspace_id: str
    workspace_name: str
    username: str
    workspace_path: str

class UpdateWorkspaceResult(BaseModel):
    status: str
    message: str
    data: dict = None
    username: str = None
    workspace_name: str = None