import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class DockerConfig:
    """Configuration for Docker-related operations"""
    
    # Base directory for project files
    # Default is /deployments, but can be overridden with DOCKER_BASE_DIR env var
    BASE_DIR = os.getenv("DOCKER_BASE_DIR", "/app/docker/deployments")
    
    # Default port range for container mapping
    BASE_PORT = int(os.getenv("DOCKER_BASE_PORT", "8000"))
    MAX_PORT_OFFSET = int(os.getenv("DOCKER_MAX_PORT_OFFSET", "1000"))
    
    # Network configuration
    DOCKER_NETWORK = os.getenv("DOCKER_NETWORK", "traefik-public")
    
    # Domain configuration
    BASE_DOMAIN = os.getenv("DOCKER_BASE_DOMAIN", "synergiqai.com")
    
    @staticmethod
    def get_project_dir(user_name: str, project_name: str) -> str:
        """
        Get the full path to a project directory
        
        Args:
            user_name: Name of the user
            project_name: Name of the project
            
        Returns:
            str: Full path to the project directory
        """
        return os.path.join(DockerConfig.BASE_DIR, user_name, project_name)