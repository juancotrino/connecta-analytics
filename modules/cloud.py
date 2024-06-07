import os
from io import BytesIO

from office365.runtime.auth.client_credential import ClientCredential
from office365.sharepoint.client_context import ClientContext

site_url = os.getenv('SITE_URL')
client_id = os.getenv('CLIENT_ID')
client_secret = os.getenv('CLIENT_SECRET')

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

    def _get_context(self):
        # Authenticate and create a context
        credentials = ClientCredential(self.client_id, self.client_secret)
        return ClientContext(self.site_url).with_credentials(credentials)

    def download_file(self, file_path: str) -> BytesIO:
        # Path to the Excel file in SharePoint
        file_url = 'Documentos compartidos/dbs/norma_noel.xlsx'

        # Prepare a file-like object to receive the downloaded file
        file_content = BytesIO()

        ctx = self._get_context()

        # Get the file from SharePoint
        ctx.web.get_file_by_server_relative_url(file_path).download(file_content).execute_query()

        # Move to the beginning of the BytesIO buffer
        file_content.seek(0)

        return file_content
