import yaml
import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
class FluentdEnabler:
    def __init__(self):
        self.fluentd_host = os.environ.get('FLUENTD_HOST', 'localhost')
        fluentd_port = os.environ.get('FLUENTD_PORT', '24224')
        if fluentd_port.isdigit():  # Ensure port is a valid number
            fluentd_port = int(fluentd_port)
        self.fluentd_port = fluentd_port
    
    def add_fluentd_to_compose(self, compose_file_path: str, username: str, workspace: str) -> str:
        """
        Add fluentd logging driver to all services in a docker-compose file.
        
        Args:
            compose_file_path: Path to the docker-compose.yml file
            username: Username for the log tag
            workspace: Workspace name for the log tag
            
        Returns:
            Path to the modified compose file
        """
        with open(compose_file_path, 'r') as file:
            compose_data = yaml.safe_load(file)
        
        if 'services' not in compose_data:
            return False  # No services found in the compose file
        
        # Configure fluentd logging for each service
        for _, service_config in compose_data['services'].items():
            if 'logging' not in service_config:
                service_config['logging'] = {}
            
            service_config['logging'] = {
                'driver': 'fluentd',
                'options': {
                    'fluentd-address': f"{self.fluentd_host}:{self.fluentd_port}",
                    'tag': f"service.{username}.{workspace}"
                }
            }
        
        # Write the modified compose file
        with open(compose_file_path, 'w') as file:
            yaml.dump(compose_data, file, default_flow_style=False, indent=2)
        
        return True