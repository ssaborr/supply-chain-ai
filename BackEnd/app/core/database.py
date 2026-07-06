import logging
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

logger = logging.getLogger(__name__)

class DatabaseConnection:
    def __init__(self):
        self.client: AsyncIOMotorClient = None
        self.db = None

    async def connect_to_database(self):
        logger.info("Connecting to MongoDB...")
        self.client = AsyncIOMotorClient(settings.MONGODB_URI)
        self.db = self.client[settings.DATABASE_NAME]
        try:
            # The ping command is cheap and checks if the client can connect
            await self.client.admin.command('ping')
            logger.info("MongoDB connection established successfully.")
        except Exception as e:
            logger.error(f"Could not connect to MongoDB: {e}")
            raise e

    async def close_database_connection(self):
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed.")

db_connection = DatabaseConnection()

async def get_db():
    return db_connection.db
