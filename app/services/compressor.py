import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from app.config.settings import Settings, settings
from app.utils.logger import app_logger


class CompressionError(Exception):
    """Raised when FFmpeg fails to compress a video with all attempted codecs."""


@dataclass
class CompressionAttempt:
    codec_name: str
    ffmpeg_video_codec: str
    extra_args: List[str]


class CompressorService:
    """Compresses source videos to a target size range using FFmpeg with codec fallback."""

    def __init__(self, config: Settings = settings) -> None:
        self._config = config
        self._attempts: List[CompressionAttempt] = [
            CompressionAttempt("h265", "libx265", ["-tag:v", "hvc1", "-preset", "medium"]),
            CompressionAttempt("h264", "libx264", ["-preset", "medium", "-profile:v", "high"]),
            CompressionAttempt("av1", "libsvtav1", ["-preset", "6"]),
        ]

    def _calculate_target_bitrate_kbps(self, duration_seconds: float) -> int:
        """Calculate a target video bitrate in kbps to hit the desired output size."""
        target_size_bits = self._config.target_max_size_bytes * 8
        audio_bitrate_kbps = 128
        available_bits = target_size_bits - (audio_bitrate_kbps * 1000 * duration_seconds)
        video_bitrate_kbps = max(int(available_bits / duration_seconds / 1000), 300)
        return video_bitrate_kbps

    async def _run_ffmpeg(
        self,
        input_path: str,
        output_path: str,
        attempt: CompressionAttempt,
        bitrate_kbps: int,
    ) -> None:
        """Execute a single FFmpeg compression attempt."""
        command = [
            self._config.ffmpeg_path,
            "-y",
            "-i",
            input_path,
            "-c:v",
            attempt.ffmpeg_video_codec,
            "-b:v",
            f"{bitrate_kbps}k",
            "-maxrate",
            f"{int(bitrate_kbps * 1.2)}k",
            "-bufsize",
            f"{int(bitrate_kbps * 2)}k",
            *attempt.extra_args,
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            output_path,
        ]

        app_logger.info("Running FFmpeg compression attempt '{}': {}", attempt.codec_name, " ".join(command))

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()

        if process.returncode != 0:
            raise CompressionError(
                f"FFmpeg codec '{attempt.codec_name}' failed: {stderr.decode(errors='ignore')[-2000:]}"
            )

        if not Path(output_path).is_file() or Path(output_path).stat().st_size == 0:
            raise CompressionError(f"FFmpeg codec '{attempt.codec_name}' produced no output")

    async def compress(
        self,
        input_path: str,
        output_path: str,
        duration_seconds: float,
    ) -> str:
        """Compress a video, trying each codec in order until one succeeds."""
        bitrate_kbps = self._calculate_target_bitrate_kbps(duration_seconds)
        last_error: Optional[Exception] = None

        for attempt in self._attempts:
            try:
                await self._run_ffmpeg(input_path, output_path, attempt, bitrate_kbps)
                app_logger.info("Compression succeeded using codec '{}'", attempt.codec_name)
                return attempt.codec_name
            except CompressionError as error:
                app_logger.warning("Compression attempt '{}' failed: {}", attempt.codec_name, error)
                last_error = error
                continue

        raise CompressionError(f"All compression attempts failed. Last error: {last_error}")
