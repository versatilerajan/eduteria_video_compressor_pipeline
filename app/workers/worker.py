import asyncio
from typing import Dict

from app.services.factory import build_pipeline
from app.services.queue import ServiceBusQueueService
from app.utils.logger import app_logger


class VideoProcessingWorker:
    """Continuously consumes video processing jobs from Azure Service Bus."""

    def __init__(self) -> None:
        self._queue_service = ServiceBusQueueService()

    async def _handle_message(self, payload: Dict) -> None:
        """Handle a single decoded queue message by running it through the pipeline."""
        video_id = payload["videoId"]
        blob_name = payload["blobName"]
        title = payload.get("title")

        app_logger.info("Worker picked up job: video_id={} blob_name={}", video_id, blob_name)

        pipeline = build_pipeline()
        result = await pipeline.process(video_id=video_id, blob_name=blob_name, title=title)

        app_logger.info("Worker finished job: video_id={} status={}", video_id, result.status.value)

    async def run_forever(self) -> None:
        """Start the infinite consume loop for the worker."""
        app_logger.info("Video processing worker started, listening for jobs")
        await self._queue_service.consume_forever(self._handle_message)

    async def stop(self) -> None:
        """Gracefully stop the worker and close the queue connection."""
        await self._queue_service.close()


async def main() -> None:
    """Entry point for running the worker as a standalone process."""
    worker = VideoProcessingWorker()
    try:
        await worker.run_forever()
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
