import json
from typing import Awaitable, Callable, Dict

from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage, ServiceBusReceivedMessage

from app.config.settings import Settings, settings
from app.utils.logger import app_logger

MessageHandler = Callable[[Dict], Awaitable[None]]


class ServiceBusQueueService:
    """Async wrapper around Azure Service Bus for the video processing queue."""

    def __init__(self, config: Settings = settings) -> None:
        self._config = config
        self._client: ServiceBusClient = ServiceBusClient.from_connection_string(
            self._config.service_bus_connection_string
        )

    async def send_message(self, payload: Dict) -> None:
        """Publish a JSON-serializable payload to the configured queue."""
        async with self._client.get_queue_sender(self._config.service_bus_queue) as sender:
            message = ServiceBusMessage(json.dumps(payload))
            await sender.send_messages(message)
            app_logger.info("Published message to queue '{}': {}", self._config.service_bus_queue, payload)

    async def consume_forever(self, handler: MessageHandler) -> None:
        """Continuously receive messages and invoke the handler, completing or abandoning as needed."""
        async with self._client.get_queue_receiver(
            queue_name=self._config.service_bus_queue,
            max_wait_time=self._config.worker_poll_wait_seconds,
        ) as receiver:
            async for message in receiver:
                await self._handle_single_message(receiver, message, handler)

    @staticmethod
    async def _handle_single_message(
        receiver,
        message: ServiceBusReceivedMessage,
        handler: MessageHandler,
    ) -> None:
        """Decode, dispatch and acknowledge a single received message."""
        try:
            payload = json.loads(str(message))
            await handler(payload)
            await receiver.complete_message(message)
        except Exception as error:
            app_logger.error("Failed to process queue message, abandoning: {}", error)
            await receiver.abandon_message(message)

    async def close(self) -> None:
        """Close the underlying Service Bus client."""
        await self._client.close()
