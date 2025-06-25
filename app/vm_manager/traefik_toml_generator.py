import os
import toml
from pathlib import Path

class TraefikTomlGenerator:
    def __init__(self, base_url=None):
        self.base_url = base_url or os.getenv('SUBDOMAIN', 'localhost')
        self.base_location =  os.getenv('TRAFFIC_TOML_LOCATION')
    
    def generate_toml(self, service_name, private_ip, service_ports={}):
        """
        Generate a TOML configuration file for Traefik dynamic configuration.
        
        Args:
            service_name (str): Name of the service
            private_ip (str): Private IP address of the service
            service_ports (dict): Dictionary of service ports
        """
        routers = {}
        services = {}
        final_urls = []
        for service, ports in service_ports.items():
            multiport = len(ports) > 1
            index=1
            for port in ports:
                suffix= str(index) if multiport else ''
                index += 1                 
                router_name = f"{service_name}-{service}{suffix}"
                service_entry_name = f"{service_name}-{service}{suffix}"
                url = f"{service_entry_name}.{self.base_url}"
                final_urls.append(url)
                routers[router_name] = {
                    "rule": f"Host(`{url}`)",
                    "service": service_entry_name,
                    "entryPoints": ["websecure"],
                    "middlewares": ["sslheader"],
                    "tls": {"certResolver": "letsencrypt"}
                }
                services[service_entry_name] = {
                    "loadBalancer": {
                        "servers": [
                            {"url": f"http://{private_ip}:{port}"}
                        ]
                    }
                }
        config = {
            "http": {
                "routers": routers,
                "middlewares": {
                    "sslheader": {
                        "headers": {
                            "customRequestHeaders": {
                                "X-Forwarded-Proto": "https"
                            }
                        }
                    }
                },
                "services": services
            }
        }
        
        # Ensure directory exists
        Path(self.base_location).mkdir(parents=True, exist_ok=True)

        # Write TOML file
        toml_file_path = Path(self.base_location) / f"{service_name}.toml"
        with open(toml_file_path, 'w') as f:
            toml.dump(config, f)
        
        return toml_file_path, final_urls
