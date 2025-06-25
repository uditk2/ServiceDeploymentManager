import os
import sys
import time
import logging
from typing import Dict
import json
# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.docker.services_ports_identifier import ServicesPortsIdentifier
from app.docker.docker_compose_remote_vm_utils import DockerComposeRemoteVMUtils

project_paths = ["/Users/uditkhandelwal/Documents/workspace/RemoteAgentWorkspaces/ServiceDeploymentManager",
                 "/Users/uditkhandelwal/Documents/workspace/RemoteAgentWorkspaces/MultiLingualAppBuilder",
                 "/Users/uditkhandelwal/Documents/generated_workspaces/uditk2@gmail.com/AdventureousChemist",
                 "/Users/uditkhandelwal/Documents/generated_workspaces/uditk2@gmail.com/MultiUserVnC"]

for project_path in project_paths:
    workspace = os.path.basename(project_path)
    compose_content = DockerComposeRemoteVMUtils.read_compose_file(
                compose_file_path=DockerComposeRemoteVMUtils.get_compose_file_path(project_path=project_path)
            )
    ports = ServicesPortsIdentifier().identify_external_servicesports(docker_compose=json.dumps(compose_content))
    print(f"Workspace {workspace} Identified Ports: {ports}")