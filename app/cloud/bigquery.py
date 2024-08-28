import os
import time
import random

import pandas as pd

from google.cloud import bigquery

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
