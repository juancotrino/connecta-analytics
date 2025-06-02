from io import BytesIO

from google.cloud import storage


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

    def list_files(self, folder_path=None):
        """
        Lists all files within a folder in the bucket.

        Args:
            folder_path (str, optional): The folder path to list files from.
                                       If None, lists all files in the bucket.

        Returns:
            list: A list of file names (blob names) in the specified folder.
        """
        bucket = self.storage_client.bucket(self.bucket_name)

        # If folder_path is provided, ensure it ends with a slash
        if folder_path and not folder_path.endswith("/"):
            folder_path = f"{folder_path}/"

        # List all blobs in the bucket/folder
        blobs = bucket.list_blobs(prefix=folder_path)

        # Extract file names and remove the folder path prefix
        file_names = []
        for blob in blobs:
            name = blob.name
            if folder_path:
                name = name[len(folder_path) :]  # Remove folder path prefix
            if name:  # Skip empty names (which would be the folder itself)
                file_names.append(name)

        return file_names

    def download_as_bytes(self, blob_name):
        """
        Downloads a file from GCS and returns its contents as a BytesIO object.

        Args:
            blob_name (str): The name/path of the file to download.

        Returns:
            BytesIO: A file-like object containing the file contents.

        Raises:
            google.cloud.exceptions.NotFound: If the file doesn't exist.
        """
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(blob_name)
        return BytesIO(blob.download_as_bytes())
