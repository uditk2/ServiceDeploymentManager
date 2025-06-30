from app.base_agent.connectors import OpenAIConnector
from app.base_agent.helper_functions import get_openai_client
from app.custom_logging import logger
from app.base_agent.multimodal_agent import MultiModalAgent, Reviewer
import json
import json
import ast


class ServerErrorIdentifier:
    SYSTEM_PROMPT = """
    You have good extensive knowledge about docker and its errors. Given a build error from docker, 
    you need to identify if the error is related to the infrastructure or the code itself.
    Once you have identified the error, you need to provide a JSON response with the following format:
    {{
        "error_type": "infrastructure" or "code",
        "reason": "reason why you think this is an infrastructure or code error",
        "suggested_fix": "A brief description of how to fix the error"
    }}
    """

    # REVIEW_PROMPT = """
    # Please review the response and ensure that the error type is either "infrastructure" or "code".
    # If the error type is not clear, please regenerate the response with a more detailed explanation
    # of why it is classified as such and mark it as code type error.
    # """

    def __init__(self):
        """
        Initialize the ServerErrorIdentifier with a multimodal agent.
        The agent is configured with a system prompt that guides it to analyze the docker build error
        and identify if it is related to infrastructure or code.
        """
        self._agent = MultiModalAgent(
            name="ServerErrorIdentifier",
            system_prompt=self.SYSTEM_PROMPT,
            connector=OpenAIConnector(get_openai_client())
            #,reviewer=Reviewer(review_prompt=self.REVIEW_PROMPT)
        )

    def identify_error(self, docker_build_error: str) -> dict:
        """
        Identify the type of error in the docker build process.
        """
        response, _ = self._agent.execute_user_ask(
            user_input=docker_build_error,
            chat_history=None,
            temperature=0.0,
            json_response=True,
            model="gpt-4.1"  # Use the appropriate model
        )
        json_response = json.loads(response)

        logger.info(f" response: {response}")
        if "infrastructure" in json_response.get("error_type", "").lower():
            return "server_error"
        else:
            return None

