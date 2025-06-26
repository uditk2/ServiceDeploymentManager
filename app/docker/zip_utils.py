import os
import shutil
import tempfile
import requests
from typing import Dict
from app.custom_logging import logger
import traceback
from .config import DockerConfig
from app.models.exceptions.known_exceptions import ZipExtractionFailedException
class ZipUtils:
    """Utilities for handling zip files in the Docker build process"""
    
    @staticmethod
    def extract_zip_file(zip_file_path: str, user_name: str, project_name: str, base_directory: str = None) -> str:
        """
        Extract a local zip file to the user/project directory.
        
        Args:
            zip_file_path: Path to the local zip file
            user_name: Name of the user
            project_name: Name of the project
            base_directory: Optional base directory (defaults to DockerConfig.BASE_DIR)
        
        Returns:
            dict: Result of the operation with success status and message
        """
        destination_path = None
        if base_directory is None:
            destination_path = DockerConfig.get_project_dir(user_name, project_name)
        else:
            destination_path = os.path.join(base_directory, user_name, project_name)
            
        try:
            logger.info(f"Creating destination directory: {destination_path}")
            
            # Create the destination directory if it doesn't exist
            os.makedirs(destination_path, exist_ok=True)
            
            # Extract the zip file
            logger.info(f"Extracting zip file to {destination_path}")
            shutil.unpack_archive(zip_file_path, destination_path)
            
            return destination_path
            
        except Exception as e:
            raise ZipExtractionFailedException(f"Failed to extract zip file {zip_file_path} for user {user_name} and project {project_name}: {str(e)}") from e