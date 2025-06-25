from pathlib import Path
import os
from dotenv import load_dotenv
load_dotenv()
def extract_user_id(user_id):
    """Extract user ID from email"""
    return user_id.replace(".", "").split("@")[0]

def extract_username_and_workspace_from_path(project_path: str) -> tuple[str, str]:
    """
    Extract username and workspace name from project path.
    
    This function analyzes the project path structure to determine the username
    and workspace name. The path typically follows patterns like:
    /path/to/workspaces/{username}/{workspace_name}
    
    Args:
        project_path (str): The full path to the project/workspace
        
    Returns:
        tuple[str, str]: (username, workspace_name)
        
    Raises:
        ValueError: If the path structure doesn't match expected patterns
    """
    path_obj = Path(project_path)
    path_parts = path_obj.parts
    
    if len(path_parts) >= 2:
        username = path_parts[-2]
        workspace_name = path_parts[-1]
        return username, workspace_name
    raise ValueError(f"Could not extract username and workspace from path '{project_path}': {str(e)}")

def generate_unique_name(project_base_path=None, username=None):
    """Generate a unique name using project and user ID"""
    project_name = Path(project_base_path).name
    sanitized_name = project_name.lower().replace(' ', '-')
    username = extract_user_id(user_id=username)
    return f"{sanitized_name}-{username}"

def generate_project_name_from_user_workspace(username: str, workspace_name: str) -> str:
    """
    Generate Docker Compose project name from username and workspace name
    
    This uses the same logic as generate_unique_name but works directly with
    username and workspace_name instead of requiring project_base_path.
    
    Args:
        username: Username (can be email)
        workspace_name: Workspace name
        
    Returns:
        Generated project name in format: {workspace_name}-{extracted_user_id}
    """
    sanitized_workspace = workspace_name.lower().replace(' ', '-')
    extracted_user_id = extract_user_id(username)
    return f"{sanitized_workspace}-{extracted_user_id}"

def generate_context_name_from_user_workspace(username: str, workspace_name: str) -> str:
    """
    Generate Docker context name from username and workspace name

    This uses the same logic as generate_project_name_from_user_workspace but
    returns a context name in the format: ws-{username}-{workspace_name}

    Args:
        username: Username (can be email)
        workspace_name: Workspace name

    Returns:
        Generated context name
    """
    extracted_user_id = extract_user_id(username)
    sanitized_user_id = "".join(c for c in extracted_user_id if c.isalnum())
    sanitized_workspace_name = "".join(c for c in workspace_name if c.isalnum())
    return f"ws-{sanitized_user_id}-{sanitized_workspace_name}"

def generate_collection_name(project_base_path=None, user_id=None):
    """Generate a unique name using project and user ID"""
    project_name = Path(project_base_path).name
    sanitized_name = project_name.lower().replace(' ', '-')
    user_id = extract_user_id(user_id=user_id)
    collection_name= f"{sanitized_name}_{user_id}"
    collection_name = collection_name.lower()[:60]
    return collection_name

def get_container_name(project_base_path=None, user_id=None):
    """Get container name using project and user ID"""
    return generate_unique_name(project_base_path=project_base_path, username=user_id)

def get_log_file_path_user_workspace(project_base_path=None, user_id: str=None) -> str:
    project_name = get_container_name(project_base_path=project_base_path, user_id=user_id)
    return get_service_log_file_path(project_base_path=project_base_path)

def get_service_log_file_path(project_base_path=None) -> str:
    username, workspace_name = extract_username_and_workspace_from_path(project_base_path)
    base_path = os.getenv('LOG_WATCHER_PATH')
    project_path = os.path.join(base_path, username, workspace_name)
    log_file = os.path.join(project_path, f'logs/app.log')
    return log_file

def get_build_log_file_path(project_base_path=None, project_name: str=None) -> str:
    build_log_file = os.path.join(project_base_path, f'{project_name}-build.log')
    return build_log_file