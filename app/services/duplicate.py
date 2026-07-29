from typing import Optional

from motor.motor_asyncio import AsyncIOMotorCollection

from app.models.video import VideoStatus
from app.utils.logger import app_logger


class DuplicateDetectionService:
    """Detects previously processed videos by comparing SHA-256 hashes."""

    def __init__(self, videos_collection: AsyncIOMotorCollection) -> None:
        self._collection = videos_collection

    async def find_existing_by_hash(self, sha256_hash: str) -> Optional[dict]:
        """Return an existing ready video document that matches the given hash, if any."""
        existing = await self._collection.find_one(
            {"sha256": sha256_hash, "status": VideoStatus.READY.value}
        )
        if existing:
            app_logger.info("Duplicate video detected for hash {}", sha256_hash)
        return existing
