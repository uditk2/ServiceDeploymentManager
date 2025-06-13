"""
Log Watcher Manager Module

This module provides centralized management for Docker Compose log watcher resurrection
on application startup. Deployment-time log watching is handled by follow_compose_logs().
"""

import os
import subprocess
import shlex
from typing import Optional, Dict, List
from app.custom_logging import logger
from app.docker.docker_log_handler import DockerComposeLogHandler
from app.docker.config import DockerConfig
from app.models.workspace import UserWorkspace


class LogWatcherManager:
    """Manages resurrection of Docker Compose log watchers on system startup"""
    
    def __init__(self):
        self._log_handler: Optional[DockerComposeLogHandler] = None
        self._initialized = False
    
    @property
    def log_handler(self) -> Optional[DockerComposeLogHandler]:
        """Get the current log handler instance"""
        return self._log_handler
    
    async def initialize(self) -> bool:
        """
        Initialize and resurrect log watchers for running containers on startup
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        if self._initialized:
            logger.warning("Log watcher manager already initialized")
            return True
            
        try:
            logger.info("Starting log watcher resurrection for system restart...")
            
            # Note: We don't initialize a global log handler here anymore
            # Each workspace will use its own workspace directory for logs
            self._log_handler = None
            
            # Discover and resurrect log watchers for running workspaces
            resurrected_count = await self._resurrect_log_watchers()
            
            self._initialized = True
            logger.info(f"Log watcher resurrection completed. Resurrected {resurrected_count} log watchers.")
            return True
            
        except Exception as e:
            logger.error(f"Error during log watcher resurrection: {str(e)}")
            self._log_handler = None
            return False
    
    async def shutdown(self) -> None:
        """Gracefully shutdown all log watchers"""
        if not self._initialized:
            return
            
        try:
            if self._log_handler:
                logger.info("Shutting down log watchers...")
                self._log_handler.shutdown()
                logger.info("Log watchers shutdown completed")
        except Exception as e:
            logger.error(f"Error during log watcher shutdown: {str(e)}")
        finally:
            self._log_handler = None
            self._initialized = False
    
    async def _resurrect_log_watchers(self) -> int:
        """
        Discover and resurrect log watchers for running Docker Compose stacks
        
        Returns:
            int: Number of log watchers successfully resurrected
        """
        resurrected_count = 0
        
        try:
            # Get all workspaces from database
            from app.database import user_workspace_collection
            async for workspace_dict in user_workspace_collection.find({}):
                workspace = UserWorkspace(**workspace_dict)
                
                if await self._resurrect_workspace_log_watcher(workspace):
                    resurrected_count += 1
                    
        except Exception as e:
            logger.error(f"Error during log watcher resurrection: {str(e)}")
            
        return resurrected_count
    
    async def _resurrect_workspace_log_watcher(self, workspace: UserWorkspace) -> bool:
        """
        Resurrect log watcher for a specific workspace if containers are running
        
        Args:
            workspace: The workspace to check and potentially resurrect
            
        Returns:
            bool: True if log watcher was successfully resurrected, False otherwise
        """
        username = workspace.username
        workspace_name = workspace.workspace_name
        workspace_path = workspace.workspace_path
        
        try:
            # Check if workspace has a docker-compose file
            compose_file = os.path.join(workspace_path, "docker-compose.yml")
            if not os.path.exists(compose_file):
                logger.debug(f"No docker-compose.yml found for workspace {username}/{workspace_name}")
                return False
            
            # Generate project name using the same logic as deployment
            project_name = self._generate_project_name(username, workspace_name)
            
            # Check if containers are running for this workspace
            running_services = await self._get_running_services(compose_file, project_name)
            
            if not running_services:
                logger.debug(f"No running containers found for workspace {username}/{workspace_name}")
                return False
            
            logger.info(f"Found running containers for workspace {username}/{workspace_name}: {running_services}")
            
            # Create a log handler for this specific workspace using its own directory
            workspace_log_handler = DockerComposeLogHandler(workspace_path)
            
            # Start log watcher for this workspace using the same method as deployments
            success = workspace_log_handler.follow_compose_logs(
                compose_file=compose_file,
                project_name=project_name,
                retain_logs=True  # Keep existing logs when restarting
            )
            
            if success:
                logger.info(f"Successfully resurrected log watcher for {username}/{workspace_name}")
                return True
            else:
                logger.warning(f"Failed to resurrect log watcher for {username}/{workspace_name}")
            
        except Exception as e:
            logger.error(f"Error resurrecting log watcher for workspace {username}/{workspace_name}: {str(e)}")
            
        return False
    
    async def _get_running_services(self, compose_file: str, project_name: str) -> List[str]:
        """
        Get list of running services for a Docker Compose project
        
        Args:
            compose_file: Path to the docker-compose.yml file
            project_name: Docker Compose project name
            
        Returns:
            List of running service names
        """
        try:
            cmd = f"docker compose -f {compose_file} -p {project_name} ps --services --filter status=running"
            result = subprocess.run(shlex.split(cmd), capture_output=True, text=True, timeout=10)
            
            running_services = result.stdout.strip().split('\n')
            return [s for s in running_services if s.strip()]  # Remove empty strings
            
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout checking running services for project {project_name}")
            return []
        except Exception as e:
            logger.error(f"Error checking running services for project {project_name}: {str(e)}")
            return []
    
    def _generate_project_name(self, username: str, workspace_name: str) -> str:
        """
        Generate Docker Compose project name using the same logic as deployment
        
        Args:
            username: Username
            workspace_name: Workspace name
            
        Returns:
            Generated project name
        """
        from .helper_functions import generate_project_name_from_user_workspace
        return generate_project_name_from_user_workspace(username, workspace_name)
    
    def get_log_handler_for_deployment(self) -> Optional[DockerComposeLogHandler]:
        """
        Get log handler instance for deployment operations (if needed for compatibility)
        
        Returns:
            DockerComposeLogHandler instance if available, None otherwise
        """
        if self._initialized and self._log_handler:
            return self._log_handler
        return None
    
    def get_stats(self) -> Dict:
        """
        Get statistics about managed log watchers
        
        Returns:
            Dictionary containing statistics
        """
        if not self._initialized or not self._log_handler:
            return {
                'initialized': False,
                'active_watchers': 0,
                'active_processes': 0
            }
        
        return {
            'initialized': True,
            'active_watchers': len(self._log_handler.log_watchers),
            'active_processes': len(self._log_handler.processes),
            'watcher_details': {
                name: watcher.get_stats() if hasattr(watcher, 'get_stats') else str(watcher)
                for name, watcher in self._log_handler.log_watchers.items()
            }
        }


# Global instance for application-wide access
log_watcher_manager = LogWatcherManager()