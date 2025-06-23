#!/usr/bin/env python3
import yaml
import os
import copy
from typing import Dict, Any
from app.custom_logging import logger

class TraefikLabeler:
    """
    A simple class to add Traefik labels to Docker Compose services.
    """
    
    def __init__(self, domain_base: str = "apps.synergiqai.com", network_name: str = "traefik-public"):
        """
        Initialize the TraefikLabeler.
        
        Args:
            domain_base: Base domain for services (e.g., synergiqai.com)
            network_name: Name of the Traefik network (default: traefik-public)
        """
        self.domain_base = domain_base
        self.network_name = network_name
    
    def add_traefik_labels(self, compose_file: str, project_name: str, output_file) -> str:
        """
        Add Traefik labels to services in a docker-compose.yml file.
        
        Args:
            compose_file: Path to the docker-compose.yml file
            project_name: Project name for the deployment
            
        Returns:
            Path to the generated compose file with Traefik labels
        """
        # Read the docker-compose file
        with open(compose_file, 'r') as f:
            compose_data = yaml.safe_load(f)
        
        # Apply Traefik configuration
        updated_compose, service_urls = self._process_compose_data(compose_data, project_name)
        # Write the updated compose file
        with open(output_file, 'w') as f:
            yaml.dump(updated_compose, f, default_flow_style=False, sort_keys=False)
        
        return service_urls
    
    def _process_compose_data(self, compose_data: Dict[str, Any], project_name: str) -> Dict[str, Any]:
        """
        Process the compose data to add Traefik labels.
        
        Args:
            compose_data: Docker Compose data as dictionary
            project_name: Project name for the deployment
            
        Returns:
            Updated Docker Compose data with Traefik labels and a dict of service URLs
        """
        result = copy.deepcopy(compose_data)
        service_urls = {}
        # Ensure version is specified
        if "version" not in result:
            result["version"] = "3"
        
        # Ensure networks section exists
        if "networks" not in result:
            result["networks"] = {}
        
        # Add traefik-public network as external
        if self.network_name not in result["networks"]:
            result["networks"][self.network_name] = {"external": True}
        
        # Process each service
        for service_name, service_config in result.get("services", {}).items():
            # Skip services that don't have a build context (external images like Redis)
            if "build" not in service_config and "image" not in service_config:
                continue
                
            # Process services that have ports defined
            if "ports" in service_config:
                # Try to find the internal port
                target_port = self._extract_port(service_config["ports"])
                
                # If we couldn't determine the port, skip this service
                if not target_port:
                    continue
                
                # Convert ports to expose (internal only)
                if "expose" not in service_config:
                    service_config["expose"] = []
                
                # Add the target port to expose if not already there
                if target_port not in service_config["expose"]:
                    service_config["expose"].append(target_port)
                
                # Remove the external port mappings as Traefik will handle this
                service_config.pop("ports", None)
                
                # Ensure the service has labels
                if "labels" not in service_config:
                    service_config["labels"] = []
                
                # Convert dict labels to list if needed
                if isinstance(service_config["labels"], dict):
                    old_labels = service_config["labels"]
                    service_config["labels"] = []
                    for k, v in old_labels.items():
                        service_config["labels"].append(f"{k}={v}")
                
                # Create service specific domain
                service_domain = f"{service_name}-{project_name}.{self.domain_base}"
                service_domain = service_domain.replace("_", "-").replace(" ", "-")
                logger.info(f"Service domain: {service_domain}")
                router_name = f"{service_name}-{project_name}".replace("_", "-").replace(" ", "-")
                logger.info(f"Router domain: {router_name}")
                # Add only essential Traefik labels
                traefik_labels = [
                    "traefik.enable=true",
                    f"traefik.docker.network={self.network_name}",
                    f"traefik.http.routers.{router_name}.rule=Host(`{service_domain}`)",
                    f"traefik.http.routers.{router_name}.entrypoints=websecure",
                    f"traefik.http.routers.{router_name}.tls=true",
                    f"traefik.http.routers.{router_name}.tls.certresolver=letsencrypt",
                    f"traefik.http.services.{router_name}.loadbalancer.server.port={target_port}"
                ]
                service_urls[service_name] = f"https://{service_domain}"

                # Add labels that don't already exist
                existing_labels = set(service_config["labels"])
                for label in traefik_labels:
                    if label not in existing_labels:
                        service_config["labels"].append(label)
                
                # Ensure service is connected to the traefik network
                if "networks" not in service_config:
                    service_config["networks"] = [self.network_name]
                elif isinstance(service_config["networks"], list) and self.network_name not in service_config["networks"]:
                    service_config["networks"].append(self.network_name)
                elif isinstance(service_config["networks"], dict) and self.network_name not in service_config["networks"]:
                    service_config["networks"][self.network_name] = None
        
        return result, service_urls
    
    def _extract_port(self, ports_config):
        """Extract the internal port from ports configuration."""
        for port_mapping in ports_config:
            # Handle string format like "80:80" or "8080:80"
            if isinstance(port_mapping, str):
                parts = port_mapping.split(":")
                if len(parts) >= 2:
                    # Get the internal port (right side)
                    return parts[-1].split("/")[0]  # Remove /tcp or /udp if present
                else:
                    # If just a single port like "80", it's both external and internal
                    return parts[0].split("/")[0]
            
            # Handle dictionary format like {target: 80, published: 8080}
            elif isinstance(port_mapping, dict) and "target" in port_mapping:
                return port_mapping["target"]
        
        # Default if we can't determine port
        return None


