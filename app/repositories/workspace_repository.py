from typing import List, Optional, Dict
from app.database import user_workspace_collection
from app.models.workspace import UserWorkspace, LogWatcherInfo, VMConfig
from app.models.exceptions.known_exceptions import (
    WorkspaceAlreadyExistsException)
from datetime import datetime
import re

class WorkspaceRepository:
    """Repository for managing user workspace data in MongoDB"""
    
    @staticmethod
    async def create_workspace(workspace: UserWorkspace) -> str:
        """Create a new workspace"""
        workspace_dict = workspace.model_dump()
        # Ensure the deployed versions are in reverse chronological order
        workspace_dict["deployed_versions"] = workspace_dict.get("deployed_versions", [])
        
        # Check if workspace already exists (case-insensitive)
        existing = await user_workspace_collection.find_one({
            "username": workspace.username,
            "workspace_name": {"$regex": f"^{re.escape(workspace.workspace_name)}$", "$options": "i"}
        })
        
        if existing:
            raise WorkspaceAlreadyExistsException(f"Workspace {workspace.workspace_name} already exists for user {workspace.username}")
        
        result = await user_workspace_collection.insert_one(workspace_dict)
        return str(result.inserted_id)
    
    @staticmethod
    async def get_workspace(username: str, workspace_name: str) -> Optional[UserWorkspace]:
        """Get a workspace by username and workspace name (case-insensitive for workspace name)"""
        workspace_dict = await user_workspace_collection.find_one({
            "username": username,
            "workspace_name": {"$regex": f"^{re.escape(workspace_name)}$", "$options": "i"}
        })
        
        # check if vm config exists in the workspace dict
        if workspace_dict and "vm_config" in workspace_dict:
            # if instance of vm_config is not VMConfig and is a string, convert it to VMConfig
            if isinstance(workspace_dict["vm_config"], str):
                import json
                config  = json.loads(workspace_dict["vm_config"])
                workspace_dict["vm_config"] = config
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
            {
                "username": username, 
                "workspace_name": {"$regex": f"^{re.escape(workspace_name)}$", "$options": "i"}
            },
            {"$set": update_data}
        )
        
        return result.modified_count > 0
    
    @staticmethod
    async def add_deployed_version(username: str, workspace_name: str, version: str) -> bool:
        """Add a new deployed version to the beginning of the list (reverse chronological order)"""
        result = await user_workspace_collection.update_one(
            {
                "username": username, 
                "workspace_name": {"$regex": f"^{re.escape(workspace_name)}$", "$options": "i"}
            },
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
            "workspace_name": {"$regex": f"^{re.escape(workspace_name)}$", "$options": "i"}
        })
        
        return result.deleted_count > 0
    
    # Log Watcher Management Methods
    
    @staticmethod
    async def update_log_watcher_state(username: str, workspace_name: str, log_watcher_info: LogWatcherInfo) -> bool:
        """Update log watcher state for a workspace"""
        result = await user_workspace_collection.update_one(
            {
                "username": username,
                "workspace_name": {"$regex": f"^{re.escape(workspace_name)}$", "$options": "i"}
            },
            {
                "$set": {
                    "log_watcher": log_watcher_info.model_dump(),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0
    
    @staticmethod
    async def mark_log_watcher_active(username: str, workspace_name: str, project_name: str, 
                                    pid: Optional[int] = None, log_file: Optional[str] = None) -> bool:
        """Mark log watcher as active"""
        log_watcher = LogWatcherInfo()
        log_watcher.mark_as_active(project_name, pid, log_file)
        return await WorkspaceRepository.update_log_watcher_state(username, workspace_name, log_watcher)
    
    @staticmethod
    async def mark_log_watcher_stopped(username: str, workspace_name: str) -> bool:
        """Mark log watcher as stopped"""
        log_watcher = LogWatcherInfo()
        log_watcher.mark_as_stopped()
        return await WorkspaceRepository.update_log_watcher_state(username, workspace_name, log_watcher)
    
    @staticmethod
    async def mark_log_watcher_failed(username: str, workspace_name: str, error_message: str) -> bool:
        """Mark log watcher as failed"""
        # Get current log watcher state to preserve error count
        workspace = await WorkspaceRepository.get_workspace(username, workspace_name)
        if workspace:
            log_watcher = workspace.log_watcher
            log_watcher.mark_as_failed(error_message)
            return await WorkspaceRepository.update_log_watcher_state(username, workspace_name, log_watcher)
        return False
    

    @staticmethod
    async def get_active_log_watchers() -> List[UserWorkspace]:
        """Get all workspaces with active log watchers"""
        cursor = user_workspace_collection.find({
            "log_watcher.status": "active"
        })
        
        workspaces = []
        async for workspace_dict in cursor:
            workspaces.append(UserWorkspace(**workspace_dict))
        
        return workspaces
    
    @staticmethod
    async def cleanup_orphaned_log_watchers() -> int:
        """Mark log watchers as orphaned if their processes are no longer running"""
        import psutil
        
        active_watchers = await WorkspaceRepository.get_active_log_watchers()
        orphaned_count = 0
        
        for workspace in active_watchers:
            if workspace.log_watcher.log_handler_pid:
                try:
                    # Check if process is still running
                    if not psutil.pid_exists(workspace.log_watcher.log_handler_pid):
                        # Mark as orphaned
                        workspace.log_watcher.status = "orphaned"
                        await WorkspaceRepository.update_log_watcher_state(
                            workspace.username, 
                            workspace.workspace_name, 
                            workspace.log_watcher
                        )
                        orphaned_count += 1
                except Exception:
                    # If we can't check the process, mark as orphaned
                    workspace.log_watcher.status = "orphaned"
                    await WorkspaceRepository.update_log_watcher_state(
                        workspace.username, 
                        workspace.workspace_name, 
                        workspace.log_watcher
                    )
                    orphaned_count += 1
        
        return orphaned_count
    
    @staticmethod
    async def update_vm_config_state(username: str, workspace_name: str, vm_config: VMConfig) -> bool:
        """Update VM configuration for a workspace"""
        result = await user_workspace_collection.update_one(
            {
                "username": username,
                "workspace_name": {"$regex": f"^{re.escape(workspace_name)}$", "$options": "i"}
            },
            {
                "$set": {
                    "vm_config": vm_config.model_dump(),
                    "updated_at": datetime.now()
                }
            }
        )
        return result.modified_count > 0

    @staticmethod
    async def clear_vm_config_state(username: str, workspace_name: str) -> bool:
        """Clear VM configuration from a workspace"""
        result = await user_workspace_collection.update_one(
            {
                "username": username,
                "workspace_name": {"$regex": f"^{re.escape(workspace_name)}$", "$options": "i"}
            },
            {
                "$unset": {"vm_config": ""},
                "$set": {"updated_at": datetime.now()}
            }
        )
        return result.modified_count > 0