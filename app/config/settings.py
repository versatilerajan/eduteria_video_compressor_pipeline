from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    mongodb_uri: str
    mongodb_db_name: str = "video_pipeline"

    azure_storage_connection_string: str

    azure_container_name: str
    azure_container_processed: Optional[str] = None
    azure_container_thumbnail: Optional[str] = None
    azure_container_hls: Optional[str] = None

    folder_processed: str = "processed"
    folder_thumbnail: str = "thumbnails"
    folder_hls: str = "hls"

    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"

    max_upload_size_mb: int = 500
    allowed_extensions: str = ".mp4,.mov,.mkv,.avi,.webm"
    target_min_size_mb: int = 20
    target_max_size_mb: int = 30

    storage_temp_dir: str = "storage/temp"
    storage_processed_dir: str = "storage/processed"
    storage_thumbnail_dir: str = "storage/thumbnails"

    thumbnail_offset_seconds: int = 10
    hls_segment_seconds: int = 6

    log_level: str = "INFO"
    log_file: str = "logs/app.log"

    @property
    def container_processed(self) -> str:
        """Return the container used for processed videos, defaulting to the shared container."""
        return self.azure_container_processed or self.azure_container_name

    @property
    def container_thumbnail(self) -> str:
        """Return the container used for thumbnails, defaulting to the shared container."""
        return self.azure_container_thumbnail or self.azure_container_name

    @property
    def container_hls(self) -> str:
        """Return the container used for HLS output, defaulting to the shared container."""
        return self.azure_container_hls or self.azure_container_name

    @property
    def allowed_extensions_list(self) -> List[str]:
        """Return normalized list of allowed file extensions."""
        return [ext.strip().lower() for ext in self.allowed_extensions.split(",") if ext.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        """Return maximum upload size expressed in bytes."""
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def target_min_size_bytes(self) -> int:
        """Return target minimum compressed size expressed in bytes."""
        return self.target_min_size_mb * 1024 * 1024

    @property
    def target_max_size_bytes(self) -> int:
        """Return target maximum compressed size expressed in bytes."""
        return self.target_max_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of the application settings."""
    return Settings()


settings = get_settings()
