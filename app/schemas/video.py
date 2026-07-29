from typing import Optional

from pydantic import BaseModel, Field


class ProcessVideoRequest(BaseModel):
    """Request payload to trigger video processing."""

    videoId: str = Field(..., min_length=1)
    blobName: str = Field(..., min_length=1)
    title: Optional[str] = None


class ProcessVideoResponse(BaseModel):
    """Response returned immediately after accepting a processing request."""

    status: str
    videoId: str


class VideoResponse(BaseModel):
    """Response representing the current state of a video resource."""

    id: str
    title: Optional[str] = None
    status: str
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
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class HealthResponse(BaseModel):
    """Response for the health check endpoint."""

    status: str
    mongodb: str
    ffmpeg: str
