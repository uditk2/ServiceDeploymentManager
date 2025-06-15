import requests
import json
from typing import Dict, Any, Optional
import os
class ErrorReporter:
    """
    A class to submit bug reports to the task handler API.
    """
    
    def __init__(self):
        """
        Initialize the BugReporter with the base URL of the API.
        
        Args:
            base_url (str): The base URL of the task handler API
        """
        self.base_url = os.getenv("APP_BUILDER_URL")
    
    def submit_bug(self, user_id: str, workspace_name: str, bug_description: str) -> Dict[str, Any]:
        """
        Submit a bug report to the task handler API.
        
        Args:
            user_id (str): The user ID
            workspace_name (str): The workspace name
            bug_description (str): Description of the bug
            
        Returns:
            Dict[str, Any]: API response containing success status and data
        """
        url = f"{self.base_url}/task-handler/api/{user_id}/{workspace_name}/submit-bug"
        
        payload = {
            "bug_description": bug_description
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "data": response.json() if response.content else {}
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Request failed: {str(e)}",
                "data": {}
            }
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": "Invalid JSON response",
                "data": {}
            }