"""
Log Watcher Manager Module

This module provides centralized management for Docker Compose log watcher resurrection
on application startup. Deployment-time log watching is handled by follow_compose_logs().
"""

import os
import subprocess
import shlex
import asyncio
from typing import Optional, Dict, List
from app.custom_logging import logger
from app.docker.docker_log_handler import DockerComposeLogHandler
from app.models.workspace import UserWorkspace


class LogWatcherManager:
    """Manages resurrection of Docker Compose log watchers on system startup"""
    
    def __init__(self):
        self._log_handler: Optional[DockerComposeLogHandler] = None
        self._initialized = False
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_interval = 3600  # 1 hour in seconds
    
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
            
            # Start periodic cleanup task
            self._start_periodic_cleanup()
            
            self._initialized = True
            logger.info(f"Log watcher resurrection completed. Resurrected {resurrected_count} log watchers.")
            logger.info(f"Started periodic cleanup task (interval: {self._cleanup_interval}s)")
            return True
            
        except Exception as e:
            logger.error(f"Error during log watcher resurrection: {str(e)}")
            self._log_handler = None
            return False
    
    async def shutdown(self) -> None:
        """Gracefully shutdown all log watchers and cleanup tasks"""
        if not self._initialized:
            return
            
        try:
            # Stop periodic cleanup task
            if self._cleanup_task and not self._cleanup_task.done():
                logger.info("Stopping periodic cleanup task...")
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
            
            # The actual log watchers are cleaned up by individual DockerComposeLogHandler instances
            # during deployment and workspace deletion, so we don't need to do anything here
            
            logger.info("Log watcher manager shutdown completed")
        except Exception as e:
            logger.error(f"Error during log watcher manager shutdown: {str(e)}")
        finally:
            self._log_handler = None
            self._initialized = False
    
    def _start_periodic_cleanup(self):
        """Start the periodic cleanup background task"""
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup_loop())
    
    async def _periodic_cleanup_loop(self):
        """Background task that runs periodic cleanup"""
        try:
            while True:
                await asyncio.sleep(self._cleanup_interval)
                await self._run_periodic_cleanup()
        except asyncio.CancelledError:
            logger.info("Periodic cleanup task cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in periodic cleanup loop: {str(e)}")
    
    async def _run_periodic_cleanup(self):
        """Run a single cleanup cycle to detect and clean orphaned log watchers"""
        try:
            logger.info("Running periodic log watcher cleanup...")
            
            orphaned_count = 0
            total_watchers = 0
            
            # Get all workspaces from database
            from app.database import user_workspace_collection
            async for workspace_dict in user_workspace_collection.find({}):
                workspace = UserWorkspace(**workspace_dict)
                
                # Check if this workspace has log watchers that should be cleaned up
                cleaned = await self._cleanup_orphaned_watcher(workspace)
                if cleaned:
                    orphaned_count += 1
                total_watchers += 1
            
            if orphaned_count > 0:
                logger.info(f"Periodic cleanup completed: cleaned {orphaned_count}/{total_watchers} orphaned log watchers")
            else:
                logger.debug(f"Periodic cleanup completed: no orphaned watchers found ({total_watchers} workspaces checked)")
                
        except Exception as e:
            logger.error(f"Error during periodic cleanup: {str(e)}")
    
    async def _cleanup_orphaned_watcher(self, workspace: UserWorkspace) -> bool:
        """
        Check if a workspace has orphaned log watchers and clean them up
        
        Args:
            workspace: The workspace to check
            
        Returns:
            bool: True if an orphaned watcher was cleaned up, False otherwise
        """
        username = workspace.username
        workspace_name = workspace.workspace_name
        workspace_path = workspace.workspace_path
        
        try:
            # Check if workspace has a docker-compose file
            compose_file = os.path.join(workspace_path, "docker-compose.yml")
            if not os.path.exists(compose_file):
                return False
            
            # Generate project name using the same logic as deployment
            project_name = self._generate_project_name(username, workspace_name)
            
            # Check if containers are still running for this workspace
            running_services = await self._get_running_services(compose_file, project_name)
            
            # If no containers are running, but log files exist, clean them up
            if not running_services:
                # Check if there are log files that might indicate orphaned watchers
                log_file_pattern = f"{project_name}-compose.log"
                potential_log_files = []
                
                # Look for log files in the workspace directory
                if os.path.exists(workspace_path):
                    for file in os.listdir(workspace_path):
                        if file.endswith('-compose.log') and project_name in file:
                            potential_log_files.append(os.path.join(workspace_path, file))
                
                # Also check for position files (indicates active watchers)
                position_files = []
                for log_file in potential_log_files:
                    position_file = f"{log_file}.position"
                    if os.path.exists(position_file):
                        position_files.append(position_file)
                
                if position_files:
                    logger.info(f"Found orphaned log watcher artifacts for {username}/{workspace_name} (no running containers)")
                    
                    # Clean up position files (this indicates the watcher was active but containers stopped)
                    for position_file in position_files:
                        try:
                            os.remove(position_file)
                            logger.debug(f"Removed orphaned position file: {position_file}")
                        except OSError as e:
                            logger.warning(f"Could not remove position file {position_file}: {e}")
                    
                    return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error checking workspace {username}/{workspace_name} for orphaned watchers: {str(e)}")
            return False

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