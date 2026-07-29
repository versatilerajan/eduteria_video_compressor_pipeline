import asyncio
import json
from pathlib import Path
from typing import Any, Dict, Optional

from app.config.settings import Settings, settings
from app.utils.logger import app_logger


class MetadataExtractionError(Exception):
    """Raised when video metadata cannot be extracted."""


class MetadataService:
    """Extracts technical metadata from a video file using ffprobe."""

    def __init__(self, config: Settings = settings) -> None:
        self._config = config

    @staticmethod
    def _parse_fps(fps_fraction: str) -> Optional[float]:
        """Convert an ffprobe fraction string such as '30000/1001' into a float."""
        try:
            if "/" in fps_fraction:
                numerator, denominator = fps_fraction.split("/")
                denominator_value = float(denominator)
                if denominator_value == 0:
                    return None
                return round(float(numerator) / denominator_value, 3)
            return round(float(fps_fraction), 3)
        except (ValueError, ZeroDivisionError):
            return None

    async def extract(self, file_path: str) -> Dict[str, Any]:
        """Extract duration, resolution, fps, codec, bitrate and file size from a video."""
        command = [
            self._config.ffprobe_path,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            file_path,
        ]

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise MetadataExtractionError(f"ffprobe failed: {stderr.decode(errors='ignore')}")

        probe_data = json.loads(stdout.decode())

        video_stream = next(
            (stream for stream in probe_data.get("streams", []) if stream.get("codec_type") == "video"),
            None,
        )
        if video_stream is None:
            raise MetadataExtractionError("No video stream found in file")

        format_info = probe_data.get("format", {})

        metadata = {
            "duration": float(format_info.get("duration", 0.0)),
            "width": int(video_stream.get("width", 0)),
            "height": int(video_stream.get("height", 0)),
            "codec": video_stream.get("codec_name"),
            "fps": self._parse_fps(video_stream.get("r_frame_rate", "0/1")),
            "bitrate": int(format_info.get("bit_rate", 0)) if format_info.get("bit_rate") else None,
            "file_size": Path(file_path).stat().st_size,
        }

        app_logger.info("Extracted metadata for {}: {}", file_path, metadata)
        return metadata
