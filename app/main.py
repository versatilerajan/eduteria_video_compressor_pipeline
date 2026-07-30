from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as video_router
from app.config.settings import settings
from app.database.mongodb import mongodb_connection
from app.services.blob_storage import BlobStorageService
from app.utils.logger import app_logger


def _ensure_storage_directories() -> None:
    """Create local storage directories used for temporary and processed files."""
    for directory in (
        settings.storage_temp_dir,
        settings.storage_processed_dir,
        settings.storage_thumbnail_dir,
    ):
        Path(directory).mkdir(parents=True, exist_ok=True)


async def _ensure_blob_containers() -> None:
    """Ensure every Azure container currently in use exists, without manual setup."""
    blob_storage = BlobStorageService()
    containers = {
        settings.container_temp,
        settings.container_processed,
        settings.container_thumbnail,
        settings.container_hls,
    }
    for container_name in containers:
        await blob_storage.ensure_container(container_name)
    await blob_storage.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown of shared resources for the application."""
    _ensure_storage_directories()
    await mongodb_connection.connect()
    await _ensure_blob_containers()
    app_logger.info("Video processing service started")
    yield
    await mongodb_connection.disconnect()
    app_logger.info("Video processing service stopped")


def create_app() -> FastAPI:
    """Application factory that assembles and configures the FastAPI instance."""
    application = FastAPI(
        title="Video Processing Pipeline",
        description="EdTech video ingestion, compression and delivery pipeline service",
        version="1.0.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(video_router, tags=["videos"])

    return application


app = create_app()