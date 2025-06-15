"""
Error Identifier Module

This module contains an AI-powered error identifier that uses a multimodal agent
to analyze log stashes and identify error logs with detailed categorization.
"""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.base_agent.multimodal_agent import MultiModalAgent, Reviewer
from app.base_agent.connectors import OpenAIConnector
from app.base_agent.helper_functions import get_openai_client
from app.custom_logging import logger


class ErrorIdentifier:
    """
    AI-powered error identifier using multimodal agent to analyze log stashes
    and identify error logs with detailed categorization and recommendations.
    """
    SYSTEM_PROMPT="""
    Given the log stash, identify if there are any error logs and extract them.
    Make sure to have one entry for every distinct error and logs of the same error should be grouped together. 
    The purpose is to extract as much information as possible for any given error.
    Think step by step and follow the following process to arrive at your response.
    step 1: Are there any error logs in the log stash?
    step 2: If no, return an empty list.
    step 3: If yes, extract the error logs.
    Provide your response in the following JSON format:
    {{
     "errors": [
       "related error_logs",
       "related error_logs",
     ],
    }}
    Please do not try to analyse or summarize anything.
    """

    def __init__(self):
        """
        Initialize the ErrorIdentifier with a multimodal agent.
        The agent is configured with a system prompt that guides it to analyze logs
        and identify related error logs.
        """
        self._agent = MultiModalAgent(name="SmartErrorDetector",
                                      system_prompt=self.SYSTEM_PROMPT,
                                      connector=OpenAIConnector(get_openai_client()))  # Will be set later
        
    def identify_errors(self, log_stash: str) -> Dict[str, Any]:
        response,_ = self._agent.execute_user_ask(user_input=log_stash, 
                                      chat_history=None, 
                                      temperature=0.0, 
                                      json_response=True, model="gpt-4.1")
        try:
            errors = json.loads(response)
            if errors and isinstance(errors, dict) and "errors" in errors:
                error_logs = errors["errors"]
                if isinstance(error_logs, list):
                    return {
                        "status": "success",
                        "error_logs": error_logs
                    }
        except json.JSONDecodeError as e:
            logger.error(f"JSON decoding error: {str(e)}")
            return {
                "status": "error",
                "message": "Invalid response format"
            }
