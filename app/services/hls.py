import asyncio
from pathlib import Path

from app.config.settings import Settings, settings
from app.utils.logger import app_logger


class HLSGenerationError(Exception):
    """Raised when HLS playlist and segment generation fails."""


class HLSService:
    """Generates an HLS playlist with segments from a compressed video."""

    def __init__(self, config: Settings = settings) -> None:
        self._config = config

    async def generate(self, input_path: str, output_dir: str) -> str:
        """Generate playlist.m3u8 and associated .ts segments inside output_dir."""
        output_directory = Path(output_dir)
        output_directory.mkdir(parents=True, exist_ok=True)

        playlist_path = output_directory / "playlist.m3u8"
        segment_pattern = output_directory / "segment_%03d.ts"

        command = [
            self._config.ffmpeg_path,
            "-y",
            "-i",
            input_path,
            "-c:v",
            "copy",
            "-c:a",
            "copy",
            "-start_number",
            "0",
            "-hls_time",
            str(self._config.hls_segment_seconds),
            "-hls_list_size",
            "0",
            "-hls_segment_filename",
            str(segment_pattern),
            "-f",
            "hls",
            str(playlist_path),
        ]

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()

        if process.returncode != 0 or not playlist_path.is_file():
            raise HLSGenerationError(f"HLS generation failed: {stderr.decode(errors='ignore')}")

        app_logger.info("Generated HLS playlist at {}", playlist_path)
        return str(playlist_path)
