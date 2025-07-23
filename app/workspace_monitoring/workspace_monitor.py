"""
Workspace Monitor Module

This module provides a workspace monitor that analyzes log stashes for errors
and submits bug reports through the error reporter system.
"""

from typing import List, Dict, Any
from app.custom_logging import logger
from app.workspace_monitoring.log_processor.error_identifier import ErrorIdentifier
from app.workspace_monitoring.error_reporter import ErrorReporter
from app.docker.helper_functions import extract_username_and_workspace_from_path


class WorkspaceMonitor:
    """
    A workspace monitor that processes log stashes, identifies errors,
    and submits bug reports to the App Builder through the error reporter.
    """
    
    def __init__(self, project_path: str):
        """
        Initialize the WorkspaceMonitor.
        
        Args:
            project_path (str): The full path to the project/workspace directory
        """
        self.project_path = project_path
        
        # Extract username and workspace name from project path
        try:
            self.user_id, self.workspace_name = extract_username_and_workspace_from_path(project_path)
        except ValueError as e:
            logger.error(f"Failed to extract username and workspace from path '{project_path}': {str(e)}")
            raise ValueError(f"Invalid project path structure: {str(e)}")
        
        self.error_identifier = ErrorIdentifier()
        self.error_reporter = ErrorReporter()
        
        logger.info(f"Initialized WorkspaceMonitor for workspace '{self.workspace_name}' (user: {self.user_id})")
    
    def monitor(self, log_stash: str) -> Dict[str, Any]:
        """
        Monitor a log stash by checking for errors and submitting bug reports.
        
        Args:
            log_stash str: The log stash to process, typically a list of log lines.
            
        Returns:
            Dict[str, Any]: Summary of monitoring results
        """
        if not log_stash:
            return {"success": True, "message": "No logs to process", "errors_found": 0, "bugs_submitted": 0}
        
        logger.debug(f"[WorkspaceMonitor-{self.workspace_name}] Monitoring {len(log_stash)} log lines")
        
        try:
            log_stash = "\n".join(log_stash) if isinstance(log_stash, List) else log_stash
            # Identify errors using ErrorIdentifier
            error_result = self.error_identifier.identify_errors(log_stash)
            
            if not error_result or error_result.get("status") != "success":
                error_msg = error_result.get("message", "Error identification failed") if error_result else "No result returned"
                logger.error(f"[WorkspaceMonitor-{self.workspace_name}] {error_msg}")
                return {"success": False, "message": error_msg, "errors_found": 0, "bugs_submitted": 0}
            
            # Process identified errors
            error_logs = error_result.get("error_logs", [])
            errors_found = len(error_logs)
            
            if errors_found == 0:
                logger.debug(f"[WorkspaceMonitor-{self.workspace_name}] No errors found")
                return {"success": True, "message": "No errors detected", "errors_found": 0, "bugs_submitted": 0}
            
            logger.info(f"[WorkspaceMonitor-{self.workspace_name}] Found {errors_found} error groups, submitting bug reports")
            
            # Submit bug reports for each error
            bugs_submitted = 0
            for i, error_log in enumerate(error_logs):
                try:
                    bug_description = f"""Automated Error Report - Workspace: {self.workspace_name}

Error Group {i + 1} of {errors_found}:

{error_log}

---
Auto-detected by Workspace Monitor
User: {self.user_id}
Workspace: {self.workspace_name}
"""
                    
                    result = self.error_reporter.submit_bug(
                        user_id=self.user_id,
                        workspace_name=self.workspace_name,
                        bug_description=bug_description
                    )
                    
                    if result.get("success", False):
                        bugs_submitted += 1
                        logger.debug(f"[WorkspaceMonitor-{self.workspace_name}] Submitted bug report {i + 1}")
                    else:
                        logger.error(f"[WorkspaceMonitor-{self.workspace_name}] Failed to submit bug report {i + 1}: {result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    logger.error(f"[WorkspaceMonitor-{self.workspace_name}] Exception submitting bug report {i + 1}: {str(e)}")
            
            message = f"Found {errors_found} errors, submitted {bugs_submitted} bug reports"
            logger.debug(f"[WorkspaceMonitor-{self.workspace_name}] {message}")
            
            return {
                "success": True,
                "message": message,
                "errors_found": errors_found,
                "bugs_submitted": bugs_submitted
            }
            
        except Exception as e:
            error_msg = f"Monitoring failed: {str(e)}"
            logger.error(f"[WorkspaceMonitor-{self.workspace_name}] {error_msg}")
            return {"success": False, "message": error_msg, "errors_found": 0, "bugs_submitted": 0}

