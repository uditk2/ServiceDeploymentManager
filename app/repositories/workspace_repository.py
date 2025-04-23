from typing import List, Optional, Dict
from app.database import user_workspace_collection
from app.models.workspace import UserWorkspace
from datetime import datetime

class WorkspaceRepository:
    """Repository for managing user workspace data in MongoDB"""
    
    @staticmethod
    async def create_workspace(workspace: UserWorkspace) -> str:
        """Create a new workspace"""
        workspace_dict = workspace.dict()
        # Ensure the deployed versions are in reverse chronological order
        workspace_dict["deployed_versions"] = workspace_dict.get("deployed_versions", [])
        
        # Check if workspace already exists
        existing = await user_workspace_collection.find_one({
            "username": workspace.username,
            "workspace_name": workspace.workspace_name
        })
        
        if existing:
            raise ValueError(f"Workspace {workspace.workspace_name} already exists for user {workspace.username}")
        
        result = await user_workspace_collection.insert_one(workspace_dict)
        return str(result.inserted_id)
    
    @staticmethod
    async def get_workspace(username: str, workspace_name: str) -> Optional[UserWorkspace]:
        """Get a workspace by username and workspace name"""
        workspace_dict = await user_workspace_collection.find_one({
            "username": username,
            "workspace_name": workspace_name
        })
        
        if workspace_dict:
            return UserWorkspace(**workspace_dict)
        return None
    
    @staticmethod
    async def list_workspaces(username: str) -> List[UserWorkspace]:
        """List all workspaces for a user"""
        cursor = user_workspace_collection.find({"username": username})
        workspaces = []
        
        async for workspace_dict in cursor:
            workspaces.append(UserWorkspace(**workspace_dict))
        
        return workspaces
    
    @staticmethod
    async def update_workspace(username: str, workspace_name: str, update_data: Dict) -> bool:
        """Update workspace information"""
        # Don't allow changing the username or workspace_name
        if "username" in update_data or "workspace_name" in update_data:
            raise ValueError("Cannot change username or workspace_name")
        
        update_data["updated_at"] = datetime.now()
        
        result = await user_workspace_collection.update_one(
            {"username": username, "workspace_name": workspace_name},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
    
    @staticmethod
    async def add_deployed_version(username: str, workspace_name: str, version: str) -> bool:
        """Add a new deployed version to the beginning of the list (reverse chronological order)"""
        result = await user_workspace_collection.update_one(
            {"username": username, "workspace_name": workspace_name},
            {
                "$push": {"deployed_versions": {"$each": [version], "$position": 0}},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        return result.modified_count > 0
    
    @staticmethod
    async def delete_workspace(username: str, workspace_name: str) -> bool:
        """Delete a workspace"""
        result = await user_workspace_collection.delete_one({
            "username": username,
            "workspace_name": workspace_name
        })
        
        return result.deleted_count > 0