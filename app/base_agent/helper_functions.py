import os
from openai import OpenAI
import anthropic
from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
import re
load_dotenv()
from app.custom_logging import logger
import traceback
from openai import AzureOpenAI

 
def get_openai_client():
    load_dotenv()
    client = OpenAI(api_key = os.environ['OPENAI_API_KEY'], organization = os.environ['OPENAI_API_ORG'])
    return client

def get_azure_opensource_client():
    client = ChatCompletionsClient(endpoint=os.environ['AZURE_ENDPOINT'], 
                                   credential=AzureKeyCredential(os.environ["AZUREAI_ENDPOINT_KEY"]))
    return client

def get_claude_client():
    client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])
    return client

def get_openai_azure_client():
    client = AzureOpenAI(  
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],  
        api_key=os.environ["AZUREAI_ENDPOINT_KEY"],  
        api_version="2024-12-01-preview",
    )
    return client 

def get_openai_azure_dalle_client():
    client = AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_DALLE_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_DALLE_KEY"],
        api_version="2024-02-01"
    )
    return client