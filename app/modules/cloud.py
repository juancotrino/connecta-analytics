import os
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, wait

import time
import random

import pandas as pd

from google.cloud import bigquery

from office365.runtime.auth.client_credential import ClientCredential
from office365.sharepoint.client_context import ClientContext

import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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
    def __init__(self) -> None:
        self.client = bigquery.Client()
        self.schema_id = os.getenv('BIGQUERY_SCHEMA_ID')

    @handle_rate_limit
    def load_data(
        self,
        table_name: str,
        data: pd.DataFrame
    ):

        try:
            job = self.client.load_table_from_dataframe(data, f'{self.schema_id}.{table_name}')  # Make an API request.
            job_result = job.result()  # Wait for the job to complete

            # Gather information about the job result
            result_info = {
                "job_id": job.job_id,
                "state": job.state,
                "errors": job.errors,
                "output_rows": job.output_rows
            }

            logger.debug(f"Job {job.job_id} completed with state {job.state}")
            if job.errors:
                logger.error(f"Job {job.job_id} encountered errors: {job.errors}")
            else:
                logger.info(f"Job {job.job_id} successfully loaded {job.output_rows} rows.")

            return result_info

        except Exception as e:
            logger.error(f"Error loading data to BigQuery: {e}")
            return {"error loading data to BigQuery": str(e)}


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
        FROM `{schema}.{table_name}`
        WHERE country = '{country}'
            {source_query}
            AND study = '{study}'
        ORDER BY year, cycle
        """.format(
            schema=self.schema_id,
            table_name=table_name,
            country=country,
            study=study,
            source_query=source_query
        )

        if print_query:
            print(query)

        return self.client.query(query).to_dataframe()
