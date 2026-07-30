from pathlib import Path
from typing import Optional, Set

from azure.core.exceptions import ResourceExistsError
from azure.storage.blob.aio import BlobServiceClient, ContainerClient

from app.config.settings import Settings, settings
from app.utils.logger import app_logger


class BlobStorageService:
    """Async wrapper around Azure Blob Storage for the video pipeline containers.

    Containers are auto-created on first use so no container has to be provisioned
    by hand. Within a container, "folders" are just blob name prefixes (e.g.
    "temp/video123.mp4") that the pipeline decides at runtime - Azure Blob Storage
    has no real folder objects, so nothing needs to be created for them explicitly.
    """

    def __init__(self, config: Settings = settings) -> None:
        self._config = config
        self._client: Optional[BlobServiceClient] = None
        self._ensured_containers: Set[str] = set()

    def _get_client(self) -> BlobServiceClient:
        if self._client is None:
            self._client = BlobServiceClient.from_connection_string(
                self._config.azure_storage_connection_string
            )
        return self._client

    def _get_container_client(self, container_name: str) -> ContainerClient:
        return self._get_client().get_container_client(container_name)

    async def ensure_container(self, container_name: str) -> None:
        """Create a container if it does not already exist, memoizing per instance."""
        if container_name in self._ensured_containers:
            return

        container_client = self._get_container_client(container_name)
        try:
            await container_client.create_container()
            app_logger.info("Created container '{}'", container_name)
        except ResourceExistsError:
            pass

        self._ensured_containers.add(container_name)

    @staticmethod
    def build_blob_path(folder: str, blob_name: str) -> str:
        """Join a folder prefix and a blob name into a single blob path."""
        folder = folder.strip("/")
        return f"{folder}/{blob_name}" if folder else blob_name

    async def close(self) -> None:
        """Close the underlying Azure Blob Service client."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def upload_file(self, container_name: str, blob_name: str, source_path: str) -> str:
        """Upload a local file to a container and return its blob URL."""
        await self.ensure_container(container_name)
        container_client = self._get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_name)

        with open(source_path, "rb") as file_handle:
            await blob_client.upload_blob(file_handle, overwrite=True)

        app_logger.info("Uploaded '{}' to blob '{}/{}'", source_path, container_name, blob_name)
        return blob_client.url

    async def upload_directory(self, container_name: str, blob_prefix: str, source_dir: str) -> str:
        """Upload every file in a local directory under a blob name prefix, return base URL."""
        await self.ensure_container(container_name)
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


