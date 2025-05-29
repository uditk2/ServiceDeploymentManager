from pathlib import Path
import os

def extract_user_id(user_id):
    """Extract user ID from email"""
    return user_id.replace(".", "").split("@")[0]

def generate_unique_name(project_base_path=None, user_id=None):
    """Generate a unique name using project and user ID"""
    project_name = Path(project_base_path).name
    sanitized_name = project_name.lower().replace(' ', '-')
    user_id = extract_user_id(user_id=user_id)
    return f"{sanitized_name}-{user_id}"

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
    return generate_unique_name(project_base_path=project_base_path, user_id=user_id)

def get_log_file_path_user_workspace(project_base_path=None, user_id: str=None) -> str:
    project_name = get_container_name(project_base_path=project_base_path, user_id=user_id)
    return get_log_file_path(project_base_path=project_base_path, project_name=project_name)

def get_log_file_path(project_base_path=None, project_name: str=None) -> str:
    log_file = os.path.join(project_base_path, f'{project_name}-compose.log')
    return log_file