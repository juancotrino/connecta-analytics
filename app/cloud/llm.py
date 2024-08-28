import os
import time

import requests

import google.auth
from google.auth.transport.requests import Request

class LLM:
    def __init__(
        self,
        model: str = 'meta/llama3-405b-instruct-maas',
        endpoint: str = 'us-central1-aiplatform.googleapis.com',
        project_id: str = os.getenv('GCP_PROJECT_ID'),
        region: str = os.getenv('GCP_REGION')
    ) -> None:

        self.model = model
        self.url = f'https://{endpoint}/v1beta1/projects/{project_id}/locations/{region}/endpoints/openapi/chat/completions'

        # Obtain default credentials
        self.__credentials, self.__project = google.auth.default()

        # Refresh the access token
        self.__credentials.refresh(Request())
        self.__access_token = self.__credentials.token

        # Prepare headers and data
        self.__headers = {
            'Authorization': f'Bearer {self.__access_token}',
            'Content-Type': 'application/json'
        }

    def send(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        top_k: int = 10,
        top_p: float = 0.9
    ):

        data = {
            'model': self.model,
            'stream': False,
            'parameters': {
                'temperature': temperature,
                'top_k': top_k,
                'top_p': top_p,
                # add other parameters as needed, e.g.'max_tokens','stop_sequences', etc.
            },
            'messages': [
                {
                    'role': 'system',
                    'content': system_prompt
                },
                {
                    'role': 'user',
                    'content': user_prompt
                }
            ]
        }

        # Send the POST request
        start_time = time.time()
        response = requests.post(self.url, headers=self.__headers, json=data)
        end_time = time.time()  # End the timer
        elapsed_time = end_time - start_time  # Calculate the elapsed time

        return response, elapsed_time
