import os
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, wait

import time
import random

import pandas as pd

import requests

import google.auth
from google.auth.transport.requests import Request
from google.cloud import bigquery
from google.cloud import storage

from office365.runtime.auth.client_credential import ClientCredential
from office365.sharepoint.client_context import ClientContext

class SharePoint:

    def __init__(
        self,
        site_url: str = os.getenv('SITE_URL'),
        client_id: str = os.getenv('CLIENT_ID'),
        client_secret: str = os.getenv('CLIENT_SECRET')
    ) -> None:
        self.site_url = site_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.credentials = ClientCredential(self.client_id, self.client_secret)
        self.ctx = ClientContext(self.site_url).with_credentials(self.credentials)

    def download_file(self, file_path: str) -> BytesIO:
        # Prepare a file-like object to receive the downloaded file
        file_content = BytesIO()

        # Get the file from SharePoint
        self.ctx.web.get_file_by_server_relative_url(file_path).download(file_content).execute_query()

        # Move to the beginning of the BytesIO buffer
        file_content.seek(0)

        return file_content

    def create_folder(self, base_path: str, dir: str = ''):
        folder_url = f"/{'/'.join(self.site_url.split('/')[-3:-1])}/{base_path}/{dir}"
        self.ctx.web.ensure_folder_path(folder_url).execute_query()

    def create_folder_structure(self, base_path: str, dirs: list) -> None:

        max_depth = max(len(path.split('/')) for path in dirs)

        for level in range(max_depth):
            level_dirs = list(set(['/'.join(dir.split('/')[:level + 1]) for dir in dirs if level < len(dir.split('/'))]))
            with ThreadPoolExecutor() as executor:
                futures = [executor.submit(self.create_folder, base_path, dir) for dir in level_dirs]
                wait(futures)

    def list_folders(self, file_url: str):
        # file_url is the sharepoint url from which you need the list of files
        library_root = self.ctx.web.get_folder_by_server_relative_url(file_url)
        self.ctx.load(library_root).execute_query()

        folders = library_root.folders
        self.ctx.load(folders).execute_query()
        return [folder.name for folder in folders]

    def list_files(self, file_url: str):
        # file_url is the sharepoint url from which you need the list of files
        library_root = self.ctx.web.get_folder_by_server_relative_url(file_url)
        files = library_root.get_files()
        self.ctx.load(files)
        self.ctx.execute_query()
        return [file.properties["Name"] for file in files]

    def upload_file(self, folder: str, file_content: BytesIO, file_name: str):
        self.ctx.web.get_folder_by_server_relative_url(f'{folder}/').upload_file(file_name, file_content).execute_query()


def handle_rate_limit(func):
    def wrapper(*args, **kwargs):
        max_retries = 5
        retries = 0

        while retries < max_retries:
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                if "403 Exceeded rate limits" in str(e):
                    # Implement exponential backoff with jitter
                    wait_time = (2 ** retries) + (random.uniform(0, 1) * 0.1)
                    time.sleep(wait_time)
                    retries += 1
                else:
                    # Handle other exceptions
                    print(f"Error: {e}")
                    break

    return wrapper

class BigQueryClient:
    def __init__(self, data_set: str) -> None:
        self.client = bigquery.Client()
        self.schema_id = os.getenv('BIGQUERY_SCHEMA_ID')
        self.data_set = data_set

    @handle_rate_limit
    def load_data(
        self,
        table_name: str,
        data: pd.DataFrame
    ):

        job = self.client.load_table_from_dataframe(data, f'{self.schema_id}.{self.data_set}.{table_name}')  # Make an API request.
        job.result()  # Wait for the job to complete

    def fetch_data(
        self,
        query: str
    ) -> pd.DataFrame:

        return self.client.query(query).to_dataframe()

    @handle_rate_limit
    def delete_data(
        self,
        query: str
    ):

        return self.client.query(query)

    def fetch_available_periods(
        self,
        table_name: str,
        country: str,
        study: str,
        source: str | None = None,
        print_query: bool = False
    ):

        if source:
            source_query = f"AND source = '{source}'"
        else:
            source_query = ""

        query = """
        SELECT DISTINCT
            year,
            cycle,
            CONCAT(year, '_', cycle) AS period
        FROM `{schema}.{data_set}.{table_name}`
        WHERE country = '{country}'
            {source_query}
            AND study = '{study}'
        ORDER BY year, cycle
        """.format(
            schema=self.schema_id,
            data_set=self.data_set,
            table_name=table_name,
            country=country,
            study=study,
            source_query=source_query
        )

        if print_query:
            print(query)

        return self.client.query(query).to_dataframe()

class CloudStorageClient:
    def __init__(self, bucket_name):
        self.bucket_name = bucket_name
        self.storage_client = storage.Client()

    def upload_to_gcs(self, source_file_name, destination_blob_name):
        """Uploads a file to the bucket."""
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(source_file_name)
        return blob.public_url

    def delete_from_gcs(self, blob_name):
        """Deletes a file from the bucket."""
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(blob_name)
        blob.delete()

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
