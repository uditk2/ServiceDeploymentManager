from app.base_agent.connectors import OpenAIConnector
from app.base_agent.helper_functions import get_openai_client
from app.custom_logging import logger
from app.base_agent.multimodal_agent import MultiModalAgent, Reviewer
import json
import json
import ast
class ServicesPortsIdentifier:
    SYSTEM_PROMPT = """
    You are a security expert and also an expert in devOps. YOu understand 
    how to analyze docker compose files and have experience on identifying internal 
    services vs services that are exposed to the outside world.
    Based on the knowledge that you already have, please analyze the docker compose file
    and identify the external facing services and ports that traefik should be pointing to.
    Provide the reason why you selected these services and ports.
    Provide your response in the following JSON format:
    {
        "service1": port1,
        "service2": port2,
        "reason": "Provide a brief reason for each service and port identified"
    }
    In case a service appears to have more than one port, make the port section a list.
    for example:
    {
        "service1": [port1, port2],
        "service2": port3,
        "reason": "Provide a brief reason for each service and port identified"
    }
    Note that these ports will be accessible over https and http protocols.
    """

    REVIEW_PROMPT = """
    Note that I am not interested in internal services and their ports. 
    Please regenerate your response making sure that the above instructions are followed.
    """
    USER_INPUT = """
    Please analyze the docker compose file and identify the ports that traefik should be pointing to.
    {docker_compose}
    """
    def __init__(self):
        """
        Initialize the ServicesPortsIdentifier with a multimodal agent.
        The agent is configured with a system prompt that guides it to analyze the docker compose file
        and identify the ports for the reverse proxy.
        """
        self._agent = MultiModalAgent(
            name="ServicesPortsIdentifier",
            system_prompt=self.SYSTEM_PROMPT,
            connector=OpenAIConnector(get_openai_client()),
            reviewer=Reviewer(review_prompt=self.REVIEW_PROMPT)
        )
    def identify_external_servicesports(self, docker_compose: str) -> dict:
        """
        Identify the services and ports that traefik should be pointing to based on the docker compose file.
        """
        user_input = self.USER_INPUT.format(docker_compose=json.dumps(docker_compose))
        response,_ = self._agent.execute_user_ask(user_input=user_input, 
                                                chat_history=None, 
                                                temperature=0.0, 
                                                json_response=True, 
                                                model="gpt-4o-mini")
        logger.info(f"Services Ports identification response: {response}")
        try:
            services_ports = ast.literal_eval(response) if response else None
        except ValueError as e:
            logger.error(f"Could not parse response as dict: {e}")
            services_ports = None
        # remove the reason key if it exists
        if isinstance(services_ports, dict) and 'reason' in services_ports:
            del services_ports['reason']
        if not services_ports or not isinstance(services_ports, dict):
            logger.error(f"Invalid response format for port identification {response}")
            raise ValueError("Could not identify ports from the provided docker compose file.")
        
        # Ensure all values are lists
        for key, value in services_ports.items():
            if isinstance(value, int):
                services_ports[key] = [value]
            elif isinstance(value, str):
                services_ports[key] = [int(value)] if value.isdigit() else [value]
        return services_ports
