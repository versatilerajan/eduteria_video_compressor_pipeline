import asyncio
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiofiles
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorCollection

from app.config.settings import settings
from app.database.mongodb import get_videos_collection, mongodb_connection
from app.models.video import VideoStatus
from app.schemas.video import (
    HealthResponse,
    ProcessVideoRequest,
    ProcessVideoResponse,
    UploadVideoResponse,
    VideoResponse,
)
from app.services.factory import build_pipeline
from app.utils.logger import app_logger

router = APIRouter()

UPLOAD_CHUNK_SIZE = 4 * 1024 * 1024


def _document_to_response(document: dict) -> VideoResponse:
    """Convert a raw MongoDB document into a VideoResponse schema instance."""
    return VideoResponse(
        id=document["_id"],
        title=document.get("title"),
        status=document.get("status", VideoStatus.UPLOADED.value),
        original_size=document.get("original_size"),
        compressed_size=document.get("compressed_size"),
        duration=document.get("duration"),
        width=document.get("width"),
        height=document.get("height"),
        codec=document.get("codec"),
        fps=document.get("fps"),
        bitrate=document.get("bitrate"),
        sha256=document.get("sha256"),
        blob_url=document.get("blob_url"),
        thumbnail_url=document.get("thumbnail_url"),
        hls_url=document.get("hls_url"),
        is_duplicate=document.get("is_duplicate", False),
        error_message=document.get("error_message"),
        created_at=document.get("created_at").isoformat() if document.get("created_at") else None,
        updated_at=document.get("updated_at").isoformat() if document.get("updated_at") else None,
    )


async def _run_pipeline_background(video_id: str, blob_name: str, title: str | None) -> None:
    """Execute the processing pipeline in the background without blocking the request."""
    pipeline = build_pipeline()
    await pipeline.process(video_id=video_id, blob_name=blob_name, title=title)


@router.post("/upload-video", response_model=UploadVideoResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(file: UploadFile = File(...), title: str | None = Form(None)) -> UploadVideoResponse:
    """Stream an uploaded video file to local temp storage and record it.

    The raw file stays on local disk only - it is never pushed to blob storage. Blob
    storage only ever receives the compressed result once /process-video finishes, so a
    100MB upload never turns into a 100MB blob; only the ~30MB compressed output does.
    """
    extension = Path(file.filename or "").suffix.lower()
    if extension not in settings.allowed_extensions_list:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file extension '{extension}'. Allowed: {', '.join(settings.allowed_extensions_list)}",
        )

    video_id = str(uuid.uuid4())
    blob_name = f"{video_id}{extension}"
    local_path = Path(settings.storage_temp_dir) / blob_name
    local_path.parent.mkdir(parents=True, exist_ok=True)

    total_bytes = 0
    try:
        async with aiofiles.open(local_path, "wb") as destination:
            while chunk := await file.read(UPLOAD_CHUNK_SIZE):
                total_bytes += len(chunk)
                if total_bytes > settings.max_upload_size_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum allowed size of {settings.max_upload_size_mb} MB",
                    )
                await destination.write(chunk)
    except HTTPException:
        if local_path.exists():
            os.remove(local_path)
        raise
    finally:
        await file.close()

    videos_collection: AsyncIOMotorCollection = get_videos_collection()
    now = datetime.now(timezone.utc)
    await videos_collection.update_one(
        {"_id": video_id},
        {
            "$set": {
                "title": title,
                "status": VideoStatus.UPLOADED.value,
                "original_size": total_bytes,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )

    app_logger.info("Uploaded video '{}' ({} bytes) to local temp storage as '{}'", video_id, total_bytes, blob_name)
    return UploadVideoResponse(videoId=video_id, blobName=blob_name, originalSize=total_bytes)


@router.post("/process-video", response_model=ProcessVideoResponse, status_code=status.HTTP_202_ACCEPTED)
async def process_video(request: ProcessVideoRequest) -> ProcessVideoResponse:
    """Kick off compression for a previously uploaded video.

    Runs the pipeline directly as an in-process background task - there is no external
    queue in the middle, so nothing can get stuck waiting on a broker. The video is
    compressed locally and only the compressed result is uploaded to blob storage.
    """
    videos_collection: AsyncIOMotorCollection = get_videos_collection()

    await videos_collection.update_one(
        {"_id": request.videoId},
        {
            "$set": {
                "title": request.title,
                "status": VideoStatus.PROCESSING.value,
                "updated_at": datetime.now(timezone.utc),
            },
            "$setOnInsert": {"created_at": datetime.now(timezone.utc)},
        },
        upsert=True,
    )

    asyncio.create_task(_run_pipeline_background(request.videoId, request.blobName, request.title))

    return ProcessVideoResponse(status="accepted", videoId=request.videoId)


@router.get("/video/{video_id}", response_model=VideoResponse)
async def get_video(video_id: str) -> VideoResponse:
    """Fetch the current processing status and metadata for a video."""
    videos_collection: AsyncIOMotorCollection = get_videos_collection()
    document = await videos_collection.find_one({"_id": video_id})

    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    return _document_to_response(document)


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Report the health of the service and its critical dependencies."""
    mongodb_status = "ok"
    try:
        mongodb_connection.get_database()
    except RuntimeError:
        mongodb_status = "unavailable"

    ffmpeg_status = "ok"
    try:
        process = await asyncio.create_subprocess_exec(
            settings.ffmpeg_path,
            "-version",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await process.communicate()
        if process.returncode != 0:
            ffmpeg_status = "unavailable"
    except FileNotFoundError:
        ffmpeg_status = "unavailable"

    overall_status = "healthy" if mongodb_status == "ok" and ffmpeg_status == "ok" else "degraded"

    return HealthResponse(status=overall_status, mongodb=mongodb_status, ffmpeg=ffmpeg_status)