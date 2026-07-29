import asyncio
from pathlib import Path

from app.config.settings import Settings, settings
from app.utils.logger import app_logger


class VideoValidationError(Exception):
    """Raised when a video fails one of the validation checks."""


class ValidationService:
    """Validates that an uploaded video file is usable before processing."""

    def __init__(self, config: Settings = settings) -> None:
        self._config = config

    def validate_exists(self, file_path: str) -> None:
        """Ensure the file exists on disk."""
        if not Path(file_path).is_file():
            raise VideoValidationError(f"File does not exist: {file_path}")

    def validate_extension(self, file_path: str) -> None:
        """Ensure the file extension is supported."""
        extension = Path(file_path).suffix.lower()
        if extension not in self._config.allowed_extensions_list:
            raise VideoValidationError(
                f"Unsupported file extension '{extension}'. "
                f"Allowed extensions: {self._config.allowed_extensions_list}"
            )

    def validate_size(self, file_path: str) -> None:
        """Ensure the file does not exceed the maximum allowed upload size."""
        size_bytes = Path(file_path).stat().st_size
        if size_bytes == 0:
            raise VideoValidationError("File is empty")
        if size_bytes > self._config.max_upload_size_bytes:
            raise VideoValidationError(
                f"File size {size_bytes} bytes exceeds maximum allowed "
                f"{self._config.max_upload_size_bytes} bytes"
            )

    async def validate_readable_by_ffmpeg(self, file_path: str) -> None:
        """Ensure FFmpeg/FFprobe can read and parse the video stream."""
        process = await asyncio.create_subprocess_exec(
            self._config.ffprobe_path,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0 or b"video" not in stdout:
            raise VideoValidationError(
                f"File is not readable as a valid video by FFmpeg: {stderr.decode(errors='ignore')}"
            )

    async def validate_all(self, file_path: str) -> None:
        """Run all validation checks against the given file path."""
        app_logger.info("Validating video file: {}", file_path)
        self.validate_exists(file_path)
        self.validate_extension(file_path)
        self.validate_size(file_path)
        await self.validate_readable_by_ffmpeg(file_path)
        app_logger.info("Validation passed for: {}", file_path)
