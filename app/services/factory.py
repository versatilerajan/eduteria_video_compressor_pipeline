from app.database.mongodb import get_videos_collection
from app.services.blob_storage import BlobStorageService
from app.services.cleanup import CleanupService
from app.services.compressor import CompressorService
from app.services.duplicate import DuplicateDetectionService
from app.services.hls import HLSService
from app.services.metadata import MetadataService
from app.services.notification import NotificationService
from app.services.pipeline import VideoProcessingPipeline
from app.services.thumbnail import ThumbnailService
from app.services.validation import ValidationService
from app.services.virus_scan import VirusScanService


def build_pipeline() -> VideoProcessingPipeline:
    """Construct a VideoProcessingPipeline with all of its service dependencies wired up."""
    videos_collection = get_videos_collection()

    return VideoProcessingPipeline(
        videos_collection=videos_collection,
        validation_service=ValidationService(),
        virus_scan_service=VirusScanService(),
        duplicate_service=DuplicateDetectionService(videos_collection),
        compressor_service=CompressorService(),
        metadata_service=MetadataService(),
        thumbnail_service=ThumbnailService(),
        hls_service=HLSService(),
        blob_storage_service=BlobStorageService(),
        cleanup_service=CleanupService(),
        notification_service=NotificationService(),
    )
