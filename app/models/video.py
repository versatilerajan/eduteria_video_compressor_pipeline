from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class VideoStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPRESSING = "compressing"
    UPLOADING_RESULT = "uploading_result"
    READY = "ready"
    FAILED = "failed"


class VideoDocument(BaseModel):
    """Represents the persisted MongoDB document for a video resource."""

    id: str = Field(alias="_id")
    title: Optional[str] = None
    status: VideoStatus = VideoStatus.UPLOADED
    original_size: Optional[int] = None
    compressed_size: Optional[int] = None
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    codec: Optional[str] = None
    fps: Optional[float] = None
    bitrate: Optional[int] = None
    sha256: Optional[str] = None
    blob_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    hls_url: Optional[str] = None
    is_duplicate: bool = False
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"populate_by_name": True, "use_enum_values": True}

    def to_mongo(self) -> Dict[str, Any]:
        """Serialize the model into a MongoDB-ready dictionary."""
        payload = self.model_dump(by_alias=True, exclude_none=False)
        return payload