import os
import time

import requests

import google.auth
from google.auth.transport.requests import Request


class LLM:
    def __init__(
        self,
        model: str = os.getenv("LLM_MODEL"),
        endpoint: str = os.getenv("LLM_ENDPOINT"),
        project_id: str = os.getenv("LLM_PROJECT_ID"),
        region: str = os.getenv("LLM_REGION"),
    ) -> None:
        self.model = model
        self.url = f"https://{endpoint}/v1/projects/{project_id}/locations/{region}/endpoints/openapi/chat/completions"

        # Obtain default credentials
        self.__credentials, self.__project = google.auth.default()

        # Refresh the access token
        self._refresh_access_token()

    def _refresh_access_token(self) -> None:
        self.__credentials.refresh(Request())
        self.__access_token = self.__credentials.token
        self.__headers = {
            "Authorization": f"Bearer {self.__access_token}",
            "Content-Type": "application/json",
        }

    def send(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout: int | float,
        temperature: float = 0,
        top_k: int = 10,
        top_p: float = 0.1,
        max_retries: int = 5,
        backoff_factor: int = 2,
    ):
        retry_status_codes = {408, 425, 429, 500, 502, 503, 504}

        data = {
            "model": self.model,
            "stream": False,
            "parameters": {
                "temperature": temperature,
                "top_k": top_k,
                "top_p": top_p,
                # add other parameters as needed, e.g.'max_tokens','stop_sequences', etc.
            },
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        retries = 0
        backoff = 1  # Initial backoff time in seconds

        while retries < max_retries:
            try:
                response = requests.post(
                    self.url, headers=self.__headers, json=data, timeout=timeout
                )

                if response.status_code == 200:
                    return response, retries

                if response.status_code in retry_status_codes:
                    retries += 1
                    time.sleep(backoff)
                    backoff *= backoff_factor
                    continue

                if response.status_code in (401, 403):
                    retries += 1
                    self._refresh_access_token()
                    time.sleep(backoff)
                    backoff *= backoff_factor
                    continue

                return response, retries

            except requests.RequestException as e:
                retries += 1
                if retries >= max_retries:
                    # If max retries reached, raise the exception
                    raise e
                time.sleep(backoff)
                backoff *= backoff_factor

        # If all retries fail, raise an exception or handle it accordingly
        raise requests.RequestException(
            f"Failed to get a valid response after {max_retries} retries due to service unavailability."
        )
