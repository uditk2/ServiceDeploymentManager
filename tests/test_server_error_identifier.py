import os
import sys
import time
import logging
from typing import Dict
import json
# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.docker.server_error_identifier import ServerErrorIdentifier


error_string="""
Cannot connect to the Docker daemon at http://docker.example.com. Is the docker daemon running?
"""


result = ServerErrorIdentifier().identify_error(docker_build_error=error_string)

print(f"Result: {result}")