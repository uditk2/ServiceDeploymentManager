import os
import shutil
import tempfile
import requests
from typing import Dict
from app.custom_logging import logger
from .config import DockerConfig

class ZipUtils:
    """Utilities for handling zip files in the Docker build process"""
    
    @staticmethod
    def download_and_extract_zip(zip_url: str, user_name: str, project_name: str, base_directory: str = None) -> Dict:
        """
        Download a zip file from the given URL and extract it to the user/project directory.
        
        Args:
            zip_url: URL of the zip file to download
            user_name: Name of the user
            project_name: Name of the project
            base_directory: Optional base directory (defaults to DockerConfig.BASE_DIR)
        
        Returns:
            dict: Result of the operation with success status and message
        """
            
        destination_path = DockerConfig.get_project_dir(user_name, project_name)
        
        try:
            # Create a temporary file to store the downloaded zip
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
                temp_path = temp_file.name
            
            logger.info(f"Downloading zip file from {zip_url} to {temp_path}")
            
            # Download the zip file
            response = requests.get(zip_url, stream=True)
            if response.status_code != 200:
                return {
                    "success": False,
                    "message": f"Failed to download zip file: HTTP {response.status_code}"
                }
            
            # Save the downloaded content to the temporary file
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Creating destination directory: {destination_path}")
            
            # Create the destination directory if it doesn't exist
            os.makedirs(destination_path, exist_ok=True)
            
            # Extract the zip file
            logger.info(f"Extracting zip file to {destination_path}")
            shutil.unpack_archive(temp_path, destination_path)
            
            # Clean up the temporary file
            os.unlink(temp_path)
            
            return {
                "success": True,
                "message": "Zip file downloaded and extracted successfully",
                "project_path": destination_path
            }
            
        except requests.RequestException as e:
            logger.error(f"Error downloading zip file: {str(e)}")
            return {
                "success": False,
                "message": f"Error downloading zip file: {str(e)}"
            }
        except shutil.ReadError as e:
            logger.error(f"Error extracting zip file: {str(e)}")
            return {
                "success": False,
                "message": f"Error extracting zip file: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error in download_and_extract_zip: {str(e)}")
            return {
                "success": False,
                "message": f"Unexpected error: {str(e)}"
            }
    
    @staticmethod
    def extract_zip_file(zip_file_path: str, user_name: str, project_name: str, base_directory: str = None) -> Dict:
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
            
            return {
                "success": True,
                "message": "Zip file extracted successfully",
                "project_path": destination_path
            }
            
        except shutil.ReadError as e:
            logger.error(f"Error extracting zip file: {str(e)}")
            return {
                "success": False,
                "message": f"Error extracting zip file: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error in extract_zip_file: {str(e)}")
            return {
                "success": False,
                "message": f"Unexpected error: {str(e)}"
            }