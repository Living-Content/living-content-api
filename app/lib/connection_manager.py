# app/lib/connection_manager.py

import logging
import os
from app.clients.mongo_client import init_mongo
from app.clients.redis_client import init_redis
from app.clients.websocket_client import WebSocketClient


class ConnectionManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConnectionManager, cls).__new__(cls)
            cls._instance.__initialized = False
        return cls._instance

    def __init__(self):
        if self.__initialized:
            return
        self.mongo_client = None
        self.redis_client = None
        self.websocket_client = None
        self.__initialized = True
        self.logger = logging.getLogger(__name__)

    async def initialize_clients(self):
        self.logger.info("Starting to initialize database clients")
        try:
            # Initialize the MongoDB client
            self.mongo_client = await init_mongo()
            self.logger.info("MongoDB client initialized successfully")

            # Initialize the Redis client
            self.redis_client = await init_redis()
            self.logger.info("Redis client initialized successfully")

            # Retrieve the worker_id from environment variables
            worker_id = os.getenv("GUNICORN_WORKER_ID", "default-worker-id")
            self.websocket_client = WebSocketClient(
                self.redis_client, worker_id=worker_id
            )
            await self.websocket_client.initialize()
            self.logger.info(
                f"WebSocket client initialized successfully with worker_id {worker_id}"
            )
            self.logger.info("WebSocket client initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing clients: {e}")
            raise

    async def close_clients(self):
        self.logger.info("Closing database clients")
        if self.mongo_client:
            self.mongo_client.close()
            self.mongo_client = None
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None

    async def get_mongo_client(self):
        if not self.mongo_client:
            self.logger.error("MongoDB client not initialized")
            raise RuntimeError("MongoDB client not initialized")
        return self.mongo_client

    async def get_redis_client(self):
        if not self.redis_client:
            self.logger.error("Redis client not initialized")
            raise RuntimeError("Redis client not initialized")
        return self.redis_client

    async def get_websocket_client(self):
        if not self.websocket_client:
            self.logger.error("WebSocket client not initialized")
            raise RuntimeError("WebSocket client not initialized")
        return self.websocket_client
