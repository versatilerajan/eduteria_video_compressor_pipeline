import asyncio
from pathlib import Path

from app.config.settings import Settings, settings
from app.utils.logger import app_logger


class ThumbnailGenerationError(Exception):
    """Raised when a thumbnail cannot be generated from a video."""


class ThumbnailService:
    """Generates a representative thumbnail image from a video file."""

    def __init__(self, config: Settings = settings) -> None:
        self._config = config

    async def generate(self, input_path: str, output_path: str, duration_seconds: float) -> str:
        """Extract a single frame near the configured offset and save it as a JPEG thumbnail."""
        offset = min(self._config.thumbnail_offset_seconds, max(int(duration_seconds - 1), 0))

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        command = [
            self._config.ffmpeg_path,
            "-y",
            "-ss",
            str(offset),
            "-i",
            input_path,
            "-frames:v",
            "1",
            "-q:v",
            "2",
            output_path,
        ]

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()

        if process.returncode != 0 or not Path(output_path).is_file():
            raise ThumbnailGenerationError(f"Thumbnail generation failed: {stderr.decode(errors='ignore')}")

        app_logger.info("Generated thumbnail at {} (offset {}s)", output_path, offset)
        return output_path
