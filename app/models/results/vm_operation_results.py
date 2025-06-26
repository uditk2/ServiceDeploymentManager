from pydantic import BaseModel

class VMInfoResult(BaseModel):
    ip: str
    vm_name: str
    vm_status: str