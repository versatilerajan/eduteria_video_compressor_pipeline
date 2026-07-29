from pathlib import Path
from typing import Optional

from azure.storage.blob.aio import BlobServiceClient, ContainerClient

from app.config.settings import Settings, settings
from app.utils.logger import app_logger


class BlobStorageService:
    """Async wrapper around Azure Blob Storage for the video pipeline containers."""

    def __init__(self, config: Settings = settings) -> None:
        self._config = config
        self._client: Optional[BlobServiceClient] = None

    def _get_client(self) -> BlobServiceClient:
        if self._client is None:
            self._client = BlobServiceClient.from_connection_string(
                self._config.azure_storage_connection_string
            )
        return self._client

    def _get_container_client(self, container_name: str) -> ContainerClient:
        return self._get_client().get_container_client(container_name)

    async def close(self) -> None:
        """Close the underlying Azure Blob Service client."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def download_blob(self, container_name: str, blob_name: str, destination_path: str) -> str:
        """Download a blob from Azure to a local file path."""
        Path(destination_path).parent.mkdir(parents=True, exist_ok=True)
        container_client = self._get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_name)

        stream = await blob_client.download_blob()
        with open(destination_path, "wb") as file_handle:
            data = await stream.readall()
            file_handle.write(data)

        app_logger.info("Downloaded blob '{}/{}' to '{}'", container_name, blob_name, destination_path)
        return destination_path

    async def upload_file(self, container_name: str, blob_name: str, source_path: str) -> str:
        """Upload a local file to a container and return its blob URL."""
        container_client = self._get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_name)

        with open(source_path, "rb") as file_handle:
            await blob_client.upload_blob(file_handle, overwrite=True)

        app_logger.info("Uploaded '{}' to blob '{}/{}'", source_path, container_name, blob_name)
        return blob_client.url

    async def upload_directory(self, container_name: str, blob_prefix: str, source_dir: str) -> str:
        """Upload every file in a local directory under a blob name prefix, return base URL."""
        container_client = self._get_container_client(container_name)
        base_url = ""

        for file_path in Path(source_dir).rglob("*"):
            if file_path.is_file():
                relative_name = file_path.relative_to(source_dir).as_posix()
                blob_name = f"{blob_prefix}/{relative_name}"
                blob_client = container_client.get_blob_client(blob_name)
                with open(file_path, "rb") as file_handle:
                    await blob_client.upload_blob(file_handle, overwrite=True)
                if relative_name == "playlist.m3u8":
                    base_url = blob_client.url

        app_logger.info("Uploaded directory '{}' to container '{}' under prefix '{}'", source_dir, container_name, blob_prefix)
        return base_url

    async def delete_blob(self, container_name: str, blob_name: str) -> None:
        """Delete a blob from a container if it exists."""
        container_client = self._get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_name)
        await blob_client.delete_blob()
        app_logger.info("Deleted blob '{}/{}'", container_name, blob_name)
