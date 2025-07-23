"""
Docker Compose Log Watcher Module

This module provides a minimalistic log watcher implementation using the Python watchdog library
to monitor Docker Compose log files and process them through configurable processor classes.
"""

import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from app.custom_logging import logger
from .workspace_monitor import WorkspaceMonitor


class ComposeLogFileHandler(FileSystemEventHandler):
    """Watchdog file handler for Docker Compose log files"""
    
    def __init__(self, log_file_path: str, monitor:WorkspaceMonitor, start_position: int = None):
        super().__init__()
        self.log_file_path = log_file_path
        self.monitor = monitor
        self.position_file = f"{log_file_path}.position"  # Store position in companion file
        
        # Determine starting position
        if start_position is not None:
            # Explicit position provided (for new deployments)
            self.last_position = start_position
        else:
            # Try to resume from saved position
            self.last_position = self._load_last_position()
        
        # Save initial position
        self._save_position()
    
    def _load_last_position(self) -> int:
        """Load the last processed position from storage"""
        try:
            if os.path.exists(self.position_file):
                with open(self.position_file, 'r') as f:
                    position = int(f.read().strip())
                    logger.debug(f"Resuming log processing from position {position}")
                    return position
        except (ValueError, IOError) as e:
            logger.warning(f"Could not load last position: {e}")
        
        # Default behavior when no saved position exists:
        # For new deployments, we'll start from beginning (position 0)
        # For restarts of existing deployments, we'll start from end
        # This decision is made by the caller via start_position parameter
        if os.path.exists(self.log_file_path):
            with open(self.log_file_path, 'r') as f:
                f.seek(0, 2)  # Go to end
                position = f.tell()
                logger.info(f"No saved position found, starting from end of existing log file at position {position}")
                return position
        
        logger.info("No saved position found, starting from beginning of new log file")
        return 0
    
    def _save_position(self):
        """Save the current position to storage"""
        try:
            with open(self.position_file, 'w') as f:
                f.write(str(self.last_position))
        except IOError as e:
            logger.warning(f"Could not save position: {e}")
    
    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return
            
        # Resolve symlinks and normalize both paths for comparison (works in production too)
        event_path = os.path.realpath(event.src_path)
        target_path = os.path.realpath(self.log_file_path)
        
        if event_path != target_path:
            return
            
        try:
            with open(self.log_file_path, 'r') as f:
                f.seek(self.last_position)
                new_lines = f.readlines()
                self.last_position = f.tell()
                
                self.monitor.monitor(new_lines)
                
                # Save position after processing
                if new_lines:  # Only save if we actually processed something
                    self._save_position()
                        
        except Exception as e:
            logger.error(f"Error processing log file changes: {str(e)}")


class ComposeLogWatcher:
    """Log watcher instance for Docker Compose stacks using watchdog"""
    
    def __init__(self, stack_name: str, project_name: str, project_path: str = None):
        self.stack_name = stack_name
        self.project_name = project_name
        self.project_path = project_path
        self.observer = None
        self.is_watching = False
        self.file_handler = None
        
        # Create WorkspaceMonitor instance if project_path is provided
        self.monitor = None
        if project_path:
            try:
                self.monitor = WorkspaceMonitor(project_path)
                logger.info(f"Created WorkspaceMonitor for stack {stack_name}")
            except Exception as e:
                logger.error(f"Failed to create WorkspaceMonitor for {stack_name}: {str(e)}")
                # Continue without monitor - log watching will still work, just no error monitoring
        
    def start_watching(self, log_file_path: str, start_from_beginning: bool = False):
        """
        Start watching the log file using watchdog
        
        Args:
            log_file_path: Path to the log file to watch
            start_from_beginning: If True, start from beginning (for new deployments). 
                                 If False, resume from last known position (for restarts)
        """
        if self.is_watching:
            return
            
        try:
            # Create log directory if it doesn't exist
            log_dir = os.path.dirname(log_file_path)
            os.makedirs(log_dir, exist_ok=True)
            # Determine starting position
            start_position = None
            if start_from_beginning:
                # For new deployments, start from the beginning to capture everything
                # remove any existing position file
                            # Create log file if it doesn't exist
                if not os.path.exists(log_file_path):
                    with open(log_file_path, 'w') as f:
                        f.write("")
                position_file = f"{log_file_path}.position"
                if os.path.exists(position_file):
                    os.remove(position_file)
                start_position = 0
                logger.info(f"Starting new log watcher from beginning of file (position 0)")
            else:
                # For restarts, let the handler determine the position (resume from saved position)
                logger.info("Starting log watcher with resume capability")
            
            # Set up file handler with position tracking
            self.file_handler = ComposeLogFileHandler(log_file_path, self.monitor, start_position)
            
            # Set up observer
            self.observer = Observer()
            self.observer.schedule(self.file_handler, log_dir, recursive=False)
            
            # Start watching
            self.observer.start()
            self.is_watching = True
            
            logger.info(f"Started watchdog log watcher for stack: {self.stack_name}")
            
        except Exception as e:
            logger.error(f"Error starting log watcher for {self.stack_name}: {str(e)}")
            
    def stop_watching(self):
        """Stop watching the log file"""
        if self.observer and self.is_watching:
            self.observer.stop()
            self.observer.join(timeout=2)
            self.is_watching = False
            logger.info(f"Stopped log watcher for stack: {self.stack_name}")
            
    def get_stats(self):
        """Get processing statistics"""
        monitor_stats = {}
        if self.monitor:
            monitor_stats = {
                'errors_found': getattr(self.monitor, 'total_errors_found', 0),
                'bugs_submitted': getattr(self.monitor, 'bugs_submitted', 0)
            }
        
        return {
            'stack_name': self.stack_name,
            'project_name': self.project_name,
            'is_watching': self.is_watching,
            'monitor_stats': monitor_stats
        }