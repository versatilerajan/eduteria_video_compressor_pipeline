from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from motor.motor_asyncio import AsyncIOMotorCollection

from app.config.settings import Settings, settings
from app.models.video import VideoStatus
from app.services.blob_storage import BlobStorageService
from app.services.cleanup import CleanupService
from app.services.compressor import CompressorService
from app.services.duplicate import DuplicateDetectionService
from app.services.hls import HLSService
from app.services.metadata import MetadataService
from app.services.notification import NotificationService
from app.services.thumbnail import ThumbnailService
from app.services.validation import ValidationService
from app.services.virus_scan import VirusScanService
from app.utils.hashing import compute_sha256
from app.utils.logger import app_logger


@dataclass
class ProcessingResult:
    video_id: str
    status: VideoStatus
    is_duplicate: bool
    blob_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    hls_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class VideoProcessingPipeline:
    """Orchestrates the full video processing workflow from upload to storage update."""

    def __init__(
        self,
        videos_collection: AsyncIOMotorCollection,
        validation_service: ValidationService,
        virus_scan_service: VirusScanService,
        duplicate_service: DuplicateDetectionService,
        compressor_service: CompressorService,
        metadata_service: MetadataService,
        thumbnail_service: ThumbnailService,
        hls_service: HLSService,
        blob_storage_service: BlobStorageService,
        cleanup_service: CleanupService,
        notification_service: NotificationService,
        config: Settings = settings,
    ) -> None:
        self._videos = videos_collection
        self._validation = validation_service
        self._virus_scan = virus_scan_service
        self._duplicate = duplicate_service
        self._compressor = compressor_service
        self._metadata = metadata_service
        self._thumbnail = thumbnail_service
        self._hls = hls_service
        self._blob_storage = blob_storage_service
        self._cleanup = cleanup_service
        self._notification = notification_service
        self._config = config

    async def _update_status(self, video_id: str, status: VideoStatus, **extra_fields: Any) -> None:
        """Persist a status transition and any additional fields to MongoDB."""
        update_payload = {"status": status.value, "updated_at": datetime.now(timezone.utc)}
        update_payload.update(extra_fields)
        await self._videos.update_one({"_id": video_id}, {"$set": update_payload}, upsert=True)
        await self._notification.notify(video_id, status)

    async def process(self, video_id: str, blob_name: str, title: Optional[str] = None) -> ProcessingResult:
        """Run the full processing pipeline for a single video and return the result."""
        temp_input_path = str(Path(self._config.storage_temp_dir) / f"{video_id}_{blob_name}")
        processed_output_path = str(Path(self._config.storage_processed_dir) / f"{video_id}.mp4")
        thumbnail_output_path = str(Path(self._config.storage_thumbnail_dir) / f"{video_id}.jpg")
        hls_output_dir = str(Path(self._config.storage_processed_dir) / f"{video_id}_hls")

        cleanup_paths = [temp_input_path, processed_output_path, thumbnail_output_path]
        temp_blob_path = self._blob_storage.build_blob_path(self._config.folder_temp, blob_name)

        try:
            await self._update_status(video_id, VideoStatus.PROCESSING, title=title)

            await self._blob_storage.download_blob(
                self._config.container_temp, temp_blob_path, temp_input_path
            )

            await self._validation.validate_all(temp_input_path)

            is_clean = await self._virus_scan.scan_file(temp_input_path)
            if not is_clean:
                raise RuntimeError("Video failed virus scan")

            sha256_hash = await compute_sha256(temp_input_path)
            original_size = Path(temp_input_path).stat().st_size

            existing_video = await self._duplicate.find_existing_by_hash(sha256_hash)
            if existing_video:
                result = ProcessingResult(
                    video_id=video_id,
                    status=VideoStatus.READY,
                    is_duplicate=True,
                    blob_url=existing_video.get("blob_url"),
                    thumbnail_url=existing_video.get("thumbnail_url"),
                    hls_url=existing_video.get("hls_url"),
                )
                await self._update_status(
                    video_id,
                    VideoStatus.READY,
                    sha256=sha256_hash,
                    original_size=original_size,
                    is_duplicate=True,
                    blob_url=result.blob_url,
                    thumbnail_url=result.thumbnail_url,
                    hls_url=result.hls_url,
                )
                self._cleanup.delete_files([temp_input_path])
                return result

            source_metadata = await self._metadata.extract(temp_input_path)

            await self._update_status(video_id, VideoStatus.COMPRESSING, sha256=sha256_hash, original_size=original_size)

            used_codec = await self._compressor.compress(
                temp_input_path, processed_output_path, source_metadata["duration"]
            )

            final_metadata = await self._metadata.extract(processed_output_path)
            final_metadata["codec"] = used_codec

            await self._thumbnail.generate(
                temp_input_path, thumbnail_output_path, source_metadata["duration"]
            )

            await self._hls.generate(processed_output_path, hls_output_dir)

            await self._update_status(video_id, VideoStatus.UPLOADING_RESULT)

            processed_blob_url = await self._blob_storage.upload_file(
                self._config.container_processed,
                self._blob_storage.build_blob_path(self._config.folder_processed, f"{video_id}.mp4"),
                processed_output_path,
            )
            thumbnail_blob_url = await self._blob_storage.upload_file(
                self._config.container_thumbnail,
                self._blob_storage.build_blob_path(self._config.folder_thumbnail, f"{video_id}.jpg"),
                thumbnail_output_path,
            )
            hls_blob_url = await self._blob_storage.upload_directory(
                self._config.container_hls,
                self._blob_storage.build_blob_path(self._config.folder_hls, video_id),
                hls_output_dir,
            )

            await self._blob_storage.delete_blob(self._config.container_temp, temp_blob_path)

            self._cleanup.delete_files(cleanup_paths)
            self._cleanup.delete_directory(hls_output_dir)

            await self._update_status(
                video_id,
                VideoStatus.READY,
                compressed_size=final_metadata["file_size"],
                duration=final_metadata["duration"],
                width=final_metadata["width"],
                height=final_metadata["height"],
                codec=final_metadata["codec"],
                fps=final_metadata["fps"],
                bitrate=final_metadata["bitrate"],
                blob_url=processed_blob_url,
                thumbnail_url=thumbnail_blob_url,
                hls_url=hls_blob_url,
                is_duplicate=False,
            )

            return ProcessingResult(
                video_id=video_id,
                status=VideoStatus.READY,
                is_duplicate=False,
                blob_url=processed_blob_url,
                thumbnail_url=thumbnail_blob_url,
                hls_url=hls_blob_url,
                metadata=final_metadata,
            )

        except Exception as error:
            app_logger.error("Processing failed for video '{}': {}", video_id, error)
            self._cleanup.delete_files(cleanup_paths)
            self._cleanup.delete_directory(hls_output_dir)
            await self._update_status(video_id, VideoStatus.FAILED, error_message=str(error))
            return ProcessingResult(
                video_id=video_id,
                status=VideoStatus.FAILED,
                is_duplicate=False,
                error_message=str(error),
            )
