from app.base_agent.connectors import OpenAIConnector
from app.base_agent.helper_functions import get_openai_client
from app.custom_logging import logger
from app.base_agent.multimodal_agent import MultiModalAgent
import json
class PortIdentifier:
    SYSTEM_PROMPT = """
    We have traefik as a reverse proxy providing a unique subdomain to the service.
    Given the docker compose file, identify the ports that traefik should be pointing to.
    Provide your response in the following JSON format:
    {
        "ports": [
            "port1",
            "port2",
            ...
        ]
    }
    """
    USER_INPUT = """
    Please analyze the docker compose file and identify the ports that traefik should be pointing to.
    {docker_compose}
    """
    def __init__(self):
        """
        Initialize the PortIdentifier with a multimodal agent.
        The agent is configured with a system prompt that guides it to analyze the docker compose file
        and identify the ports for the reverse proxy.
        """
        self._agent = MultiModalAgent(
            name="PortIdentifier",
            system_prompt=self.SYSTEM_PROMPT,
            connector=OpenAIConnector(get_openai_client())
        )
    def identify_ports(self, docker_compose: str) -> dict:
        """
        Identify the ports that traefik should be pointing to based on the docker compose file.
        """
        user_input = self.USER_INPUT.format(docker_compose=docker_compose)
        response = self._agent.execute_user_ask(user_input=user_input, 
                                                chat_history=None, 
                                                temperature=0.0, 
                                                json_response=True, 
                                                model="gpt-4.1")
        logger.info(f"Port identification response: {response}")
        ports = json.loads(response)["ports"] if response else None
        if not ports or not isinstance(ports, list):
            logger.error(f"Invalid response format for port identification {response}")
            raise ValueError("Could not identify ports from the provided docker compose file.")
        return ports
            
    