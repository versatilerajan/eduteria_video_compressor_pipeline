from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

from app.config.settings import settings
from app.utils.logger import app_logger


class MongoDBConnection:
    """Manages the lifecycle of the async MongoDB client and database handle."""

    def __init__(self) -> None:
        self._client: Optional[AsyncIOMotorClient] = None
        self._database: Optional[AsyncIOMotorDatabase] = None

    async def connect(self) -> None:
        """Initialize the MongoDB client connection and verify connectivity."""
        self._client = AsyncIOMotorClient(settings.mongodb_uri)
        self._database = self._client[settings.mongodb_db_name]
        await self._client.admin.command("ping")
        await self._create_indexes()
        app_logger.info("Connected to MongoDB database '{}'", settings.mongodb_db_name)

    async def disconnect(self) -> None:
        """Close the MongoDB client connection."""
        if self._client is not None:
            self._client.close()
            app_logger.info("MongoDB connection closed")

    async def _create_indexes(self) -> None:
        """Create required indexes on the videos collection."""
        collection = self.get_collection("videos")
        await collection.create_index("sha256")
        await collection.create_index("status")
        await collection.create_index("created_at")

    def get_database(self) -> AsyncIOMotorDatabase:
        """Return the active database handle."""
        if self._database is None:
            raise RuntimeError("MongoDB connection has not been initialized")
        return self._database

    def get_collection(self, name: str) -> AsyncIOMotorCollection:
        """Return a collection handle by name from the active database."""
        return self.get_database()[name]


mongodb_connection = MongoDBConnection()


def get_videos_collection() -> AsyncIOMotorCollection:
    """Dependency-friendly accessor for the videos collection."""
    return mongodb_connection.get_collection("videos")
