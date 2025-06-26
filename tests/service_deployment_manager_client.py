"""
ServiceDeploymentManagerClient - A professional API client for the Service Deployment Manager API.

This client provides a clean interface for interacting with all API endpoints
while handling authentication, error handling, and response parsing.
"""

import requests
import json
import os
import base64
from typing import Dict, Any, Optional, List, Union
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class ServiceDeploymentManagerClient:
    """
    Professional API client for Service Deployment Manager.
    
    This client handles authentication, request formatting, and provides
    convenient methods for all API endpoints.
    """
    
    def __init__(self, base_url: str = None, username: str = None, password: str = None):
        """
        Initialize the client.
        
        Args:
            base_url: The base URL of the API (defaults to environment variable)
            username: Username for authentication (defaults to environment variable)
            password: Password for authentication (defaults to environment variable)
        """
        self.base_url = base_url or os.getenv('API_BASE_URL', 'http://localhost:8005')
        self.username = username or os.getenv('TEST_USERNAME')
        self.password = password or os.getenv('TEST_PASSWORD')
        
        if not self.username or not self.password:
            raise ValueError("Username and password must be provided or set in environment variables TEST_USERNAME and TEST_PASSWORD")
        
        # Ensure base_url doesn't end with slash
        self.base_url = self.base_url.rstrip('/')
        
        # API endpoint URLs
        self.docker_api_url = f"{self.base_url}/api/docker"
        self.jobs_api_url = f"{self.base_url}/api/jobs"
        self.logs_api_url = f"{self.base_url}/api/logs"
        self.stats_api_url = f"{self.base_url}/api/stats"
        self.workspaces_api_url = f"{self.base_url}/api/workspaces"
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Generate Authorization header for custom token auth."""
        token = os.getenv('AUTH_TOKEN')
        if token:
            return {"Authorization": token}
        # fallback to basic auth for legacy
        credentials = f"{self.username}:{self.password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        return {"Authorization": f"Basic {encoded_credentials}"}
    
    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Make an authenticated HTTP request.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            url: Request URL
            **kwargs: Additional arguments passed to requests
            
        Returns:
            requests.Response object
        """
        headers = kwargs.get('headers', {})
        auth_headers = self._get_auth_headers()
        headers.update(auth_headers)
        kwargs['headers'] = headers
        
        method = method.upper()
        if method == 'GET':
            return requests.get(url, **kwargs)
        elif method == 'POST':
            return requests.post(url, **kwargs)
        elif method == 'PUT':
            return requests.put(url, **kwargs)
        elif method == 'DELETE':
            return requests.delete(url, **kwargs)
        elif method == 'PATCH':
            return requests.patch(url, **kwargs)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
    
    # Docker API Methods
    def build_deploy_docker_image(self, username: str, workspace: str, zip_file_path: str) -> requests.Response:
        """
        Build and deploy a Docker image from a zip file.
        
        Args:
            username: Username
            workspace: Workspace name
            zip_file_path: Path to the zip file containing the project
            
        Returns:
            requests.Response object
        """
        url = f"{self.docker_api_url}/build_deploy/{username}/{workspace}"
        
        with open(zip_file_path, 'rb') as f:
            files = {'zip_file': (zip_file_path, f)}
            headers = {'Accept': 'application/json'}
            return self._make_request('POST', url, files=files, headers=headers)
    
    # Jobs API Methods
    def create_job(self, job_data: Dict[str, Any]) -> requests.Response:
        """
        Create a new job.
        
        Args:
            job_data: Job data dictionary
            
        Returns:
            requests.Response object
        """
        return self._make_request('POST', self.jobs_api_url, json=job_data)
    
    def get_job(self, job_id: str) -> requests.Response:
        """
        Get a specific job by ID.
        
        Args:
            job_id: Job ID
            
        Returns:
            requests.Response object
        """
        url = f"{self.jobs_api_url}/{job_id}"
        return self._make_request('GET', url)
    
    def list_user_jobs(self, username: str) -> requests.Response:
        """
        List all jobs for a user.
        
        Args:
            username: Username
            
        Returns:
            requests.Response object
        """
        url = f"{self.jobs_api_url}/user/{username}"
        return self._make_request('GET', url)
    
    def update_job_status(self, job_id: str, status: str, artifact_location: str = None) -> requests.Response:
        """
        Update job status.
        
        Args:
            job_id: Job ID
            status: New status
            artifact_location: Optional artifact location
            
        Returns:
            requests.Response object
        """
        url = f"{self.jobs_api_url}/{job_id}/status"
        params = {"status": status}
        if artifact_location:
            params["artifact_location"] = artifact_location
        return self._make_request('PUT', url, params=params)
    
    def delete_job(self, job_id: str) -> requests.Response:
        """
        Delete a job.
        
        Args:
            job_id: Job ID
            
        Returns:
            requests.Response object
        """
        url = f"{self.jobs_api_url}/{job_id}"
        return self._make_request('DELETE', url)
    
    # Logs API Methods
    def get_logs(self, username: str, workspace: str, lines: int = 50, minutes: int = None) -> requests.Response:
        """
        Get logs for a workspace.
        
        Args:
            username: Username
            workspace: Workspace name
            lines: Number of lines to retrieve (default: 50)
            minutes: Filter logs from last N minutes
            
        Returns:
            requests.Response object
        """
        url = f"{self.logs_api_url}/{username}/{workspace}"
        params = {'lines': lines}
        if minutes is not None:
            params['minutes'] = minutes
        return self._make_request('GET', url, params=params)
    
    # Stats API Methods
    def get_stats(self, username: str, workspace: str) -> requests.Response:
        """
        Get stats for a workspace.
        
        Args:
            username: Username
            workspace: Workspace name
            
        Returns:
            requests.Response object
        """
        url = f"{self.stats_api_url}/{username}/{workspace}"
        return self._make_request('GET', url)
    
    # Workspaces API Methods
    def create_workspace(self, workspace_data: Dict[str, Any]) -> requests.Response:
        """
        Create a new workspace.
        
        Args:
            workspace_data: Workspace data dictionary
            
        Returns:
            requests.Response object
        """
        return self._make_request('POST', self.workspaces_api_url, json=workspace_data)
    
    def get_workspace(self, username: str, workspace_name: str) -> requests.Response:
        """
        Get a specific workspace.
        
        Args:
            username: Username
            workspace_name: Workspace name
            
        Returns:
            requests.Response object
        """
        url = f"{self.workspaces_api_url}/{username}/{workspace_name}"
        return self._make_request('GET', url)
    
    def list_user_workspaces(self, username: str) -> requests.Response:
        """
        List all workspaces for a user.
        
        Args:
            username: Username
            
        Returns:
            requests.Response object
        """
        url = f"{self.workspaces_api_url}/{username}"
        return self._make_request('GET', url)
    
    def update_workspace(self, username: str, workspace_name: str, update_data: Dict[str, Any]) -> requests.Response:
        """
        Update a workspace.
        
        Args:
            username: Username
            workspace_name: Workspace name
            update_data: Update data dictionary
            
        Returns:
            requests.Response object
        """
        url = f"{self.workspaces_api_url}/{username}/{workspace_name}"
        return self._make_request('PUT', url, json=update_data)
    
    def delete_workspace(self, username: str, workspace_name: str) -> requests.Response:
        """
        Delete a workspace.
        
        Args:
            username: Username
            workspace_name: Workspace name
            
        Returns:
            requests.Response object
        """
        url = f"{self.workspaces_api_url}/{username}/{workspace_name}"
        return self._make_request('DELETE', url)
    
    def upload_workspace(self, username: str, workspace_name: str, zip_file_path: str) -> requests.Response:
        """
        Upload a workspace zip file.
        
        Args:
            username: Username
            workspace_name: Workspace name
            zip_file_path: Path to the zip file
            
        Returns:
            requests.Response object
        """
        url = f"{self.workspaces_api_url}/upload/{username}/{workspace_name}"
        
        with open(zip_file_path, 'rb') as f:
            files = {'zip_file': ('workspace.zip', f, 'application/zip')}
            return self._make_request('POST', url, files=files)
    
    def add_workspace_version(self, username: str, workspace_name: str, version: str) -> requests.Response:
        """
        Add a deployed version to a workspace.
        
        Args:
            username: Username
            workspace_name: Workspace name
            version: Version to add
            
        Returns:
            requests.Response object
        """
        url = f"{self.workspaces_api_url}/{username}/{workspace_name}/versions"
        update_data = {"add_deployed_version": version}
        return self._make_request('PATCH', url, json=update_data)
    
    # Convenience methods for common operations
    def wait_for_job_completion(self, job_id: str, timeout: int = 300, poll_interval: int = 5) -> Dict[str, Any]:
        """
        Wait for a job to complete and return the final status.
        
        Args:
            job_id: Job ID to monitor
            timeout: Maximum time to wait in seconds (default: 300)
            poll_interval: Time between status checks in seconds (default: 5)
            
        Returns:
            Dictionary with job status information
        """
        import time
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = self.get_job(job_id)
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'error': f'Failed to get job status: {response.status_code}',
                    'response': response.text
                }
            
            job_data = response.json()
            status = job_data.get('status')
            
            if status not in ['pending', 'running']:
                return {
                    'success': status == 'completed',
                    'status': status,
                    'job_data': job_data
                }
            
            time.sleep(poll_interval)
        
        return {
            'success': False,
            'error': 'Timeout waiting for job completion',
            'timeout': timeout
        }
    
    def test_authentication(self) -> Dict[str, Any]:
        """
        Test authentication by making a simple API call.
        
        Returns:
            Dictionary with authentication test results
        """
        try:
            auth_headers = self._get_auth_headers()
            return {
                'success': True,
                'username': self.username,
                'headers_generated': 'Authorization' in auth_headers,
                'base_url': self.base_url
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }