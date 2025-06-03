from fastapi import APIRouter, HTTPException, Query, Path
from typing import List, Optional
import os
from pathlib import Path as PathLib
from datetime import datetime
from urllib.parse import unquote

from app.log_parser.python_log_parser import DockerLogParser
from app.controllers.workspace_controller import WorkspaceController
from app.docker.helper_functions import get_log_file_path_user_workspace

router = APIRouter(
    prefix="/api/logs",
    tags=["logs"]
)


@router.get("/{username:path}/{workspace_name}")
async def get_workspace_logs(
    username: str = Path(..., description="The username (can be an email address)"), 
    workspace_name: str = Path(..., description="The workspace name"),
    minutes: Optional[int] = Query(30, description="Get logs from last X minutes"),
    lines: Optional[int] = Query(50, description="Number of log lines to return"),
    service: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
):
    """
    Get logs for a specific workspace.
    
    Args:
        username: The username of the workspace owner
        workspace_name: The name of the workspace
        minutes: Get logs from the last X minutes (default: 30)
        lines: Maximum number of log lines to return (default: 50)
        service: Filter logs by service name
        since: Start time in ISO format (e.g., '2025-05-26T14:30:00')
        until: End time in ISO format (e.g., '2025-05-26T15:30:00')
    
    Returns:
        A list of log entries with timestamps
    """
    try:
        # URL decode the username to handle email addresses properly
        username = unquote(username)
        
        log_file_path = await _get_log_file_path(username, workspace_name)
        if not os.path.exists(log_file_path):
            return {"message": "No logs found for this workspace", "logs": []}
        
        # Parse logs using DockerLogParser
        log_parser = DockerLogParser(log_file_path)
        
        # Get logs based on parameters
        if since and until:
            # Get logs by time range
            logs = log_parser.get_logs_by_timerange(since, until, service, lines)
        else:
            # Get logs by minutes
            logs = log_parser.get_logs_by_minutes(minutes, service, lines)
        
        # Format the logs for the response
        formatted_logs = [
            {
                "timestamp": timestamp.isoformat(),
                "content": content
            } for timestamp, content in logs
        ]
        
        return {
            "workspace": workspace_name,
            "username": username,  # Return the decoded username
            "log_count": len(formatted_logs),
            "logs": formatted_logs
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving logs: {str(e)}")

@router.get("/{username:path}/{workspace_name}/services")
async def get_workspace_log_services(
    username: str = Path(..., description="The username (can be an email address)"),
    workspace_name: str = Path(..., description="The workspace name")
):
    """
    Get a list of services that have logs for the specified workspace.
    
    Args:
        username: The username of the workspace owner
        workspace_name: The name of the workspace
    
    Returns:
        A list of service names
    """
    try:
        # URL decode the username to handle email addresses properly
        username = unquote(username)
        
        # Determine the log file path
        log_file_path = await _get_log_file_path(username, workspace_name)

        
        if not os.path.exists(log_file_path):
            return {"services": []}
            
        # Parse a sample of logs to extract service names
        log_parser = DockerLogParser(log_file_path)
        
        # Get a sample of recent logs
        logs = log_parser.get_logs_by_minutes(60, None, 1000)  # Last hour, up to 1000 lines
        
        # Extract unique service names
        services = set()
        for _, log_line in logs:
            service = log_parser.extract_service_name(log_line)
            if service:
                services.add(service)
                
        return {"services": sorted(list(services))}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving service names: {str(e)}")

@router.get("/{username:path}/{workspace_name}/tail")
async def tail_workspace_logs(
    username: str = Path(..., description="The username (can be an email address)"), 
    workspace_name: str = Path(..., description="The workspace name"),
    lines: int = Query(50, description="Number of log lines to return"),
    service: Optional[str] = None
):
    """
    Tail the latest logs for a workspace.
    
    Args:
        username: The username of the workspace owner
        workspace_name: The name of the workspace
        lines: Number of log lines to return (default: 50)
        service: Filter logs by service name
    
    Returns:
        The latest log lines
    """
    try:
        # URL decode the username to handle email addresses properly
        username = unquote(username)
                   
        # Get the log file path
        log_file_path = await _get_log_file_path(username, workspace_name)
        
        if not os.path.exists(log_file_path):
            return {"message": "No logs found for this workspace", "logs": []}
            
        # Use DockerLogParser to tail the logs
        log_parser = DockerLogParser(log_file_path)
        
        # Open the file and read the last N lines
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as file:
            tail_lines = log_parser._tail_file(file, lines)
            
        # Filter by service if specified
        if service:
            filtered_lines = []
            for line in tail_lines:
                if service.lower() in line.lower():
                    filtered_lines.append(line)
            tail_lines = filtered_lines
                
        return {
            "workspace": workspace_name, 
            "username": username,  # Return the decoded username
            "log_count": len(tail_lines),
            "logs": tail_lines
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error tailing logs: {str(e)}")


async def _get_log_file_path(username: str, workspace_name: str) -> str:
    # First, verify the workspace exists
    try:
        workspace = await WorkspaceController.get_workspace(username, workspace_name)
    except ValueError as e:
        # Workspace not found - return proper 404 error
        raise HTTPException(status_code=404, detail=f"Workspace '{workspace_name}' not found for user '{username}'")
    except Exception as e:
        # Other unexpected errors
        raise HTTPException(status_code=500, detail=f"Error retrieving workspace: {str(e)}")
    
    if not workspace:
        # Extra safety check in case get_workspace returns None instead of raising ValueError
        raise HTTPException(status_code=404, detail=f"Workspace '{workspace_name}' not found for user '{username}'")
    
    project_base_path = workspace.workspace_path
    
    # Determine the log file path
    try:
        log_file_path = get_log_file_path_user_workspace(project_base_path=project_base_path, user_id=username)
        if not log_file_path:
            raise HTTPException(status_code=404, detail="Log file not found for this workspace")
        return log_file_path
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error determining log file path: {str(e)}")
