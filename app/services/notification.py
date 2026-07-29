from typing import Optional

from app.models.video import VideoStatus
from app.utils.logger import app_logger


class NotificationService:
    """Notifies downstream systems about video processing status changes."""

    async def notify(self, video_id: str, status: VideoStatus, message: Optional[str] = None) -> None:
        """Send a status change notification for a given video."""
        app_logger.info("Notification: video={} status={} message={}", video_id, status.value, message)
