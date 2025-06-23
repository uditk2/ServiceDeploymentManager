import os
import toml
from pathlib import Path

class TraefikTomlGenerator:
    def __init__(self, base_url=None):
        self.base_url = base_url or os.getenv('BASE_URL', 'localhost')
    
    def generate_toml(self, service_name, directory_path, private_ip, port=80):
        """
        Generate a TOML configuration file for Traefik dynamic configuration.
        
        Args:
            service_name (str): Name of the service
            directory_path (str): Directory where TOML file will be created
            private_ip (str): Private IP address of the service
            port (int): Service port (default: 80)
        """
        config = {
            "http": {
            "routers": {
                f"{service_name}": {
                "rule": f"Host(`{service_name}.{self.base_url}`)",
                "service": f"{service_name}",
                "entryPoints": ["websecure"],
                "middlewares": ["sslheader"],
                "tls": {
                    "certResolver": "letsencrypt"
                }
                }
            },
            "middlewares": {
                "sslheader": {
                "headers": {
                    "customRequestHeaders": {
                    "X-Forwarded-Proto": "https"
                    }
                }
                }
            },
            "services": {
                f"{service_name}": {
                "loadBalancer": {
                    "servers": [
                    {"url": f"http://{private_ip}:{port}"}
                    ]
                }
                }
            }
            }
        }
        
        # Ensure directory exists
        Path(directory_path).mkdir(parents=True, exist_ok=True)
        
        # Write TOML file
        toml_file_path = Path(directory_path) / f"{service_name}.toml"
        with open(toml_file_path, 'w') as f:
            toml.dump(config, f)
        
        return str(toml_file_path)
        