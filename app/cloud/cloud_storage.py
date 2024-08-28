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
