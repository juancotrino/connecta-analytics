import os
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, wait

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

    def create_folder(self, base_path, dir):
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
