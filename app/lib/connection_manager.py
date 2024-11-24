import logging
import os
import asyncio
from asyncio import Lock
from typing import Optional
from fastapi import FastAPI

from app.clients.mongo_client import init_mongo
from app.clients.redis_client import init_redis
from app.clients.websocket_client import WebSocketClient


class ConnectionManager:
    _instance: Optional["ConnectionManager"] = None
    _lock = Lock()

    @classmethod
    async def create(
        cls,
        app: Optional[FastAPI] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> "ConnectionManager":
        """
        Create and initialize a ConnectionManager instance.

        Args:
            app: Optional FastAPI application instance
            max_retries: Maximum number of initialization attempts
            retry_delay: Base delay between retries (uses exponential backoff)

        Returns:
            Initialized ConnectionManager instance
        """
        async with cls._lock:
            if not cls._instance:
                instance = cls()
                if app:
                    instance.app = app
                cls._instance = instance
                await instance._initialize_with_retry(max_retries, retry_delay)
            return cls._instance

    def __init__(self):
        """Initialize instance variables"""
        self.app: Optional[FastAPI] = None
        self.mongo_client = None
        self.redis_client = None
        self.websocket_client = None
        self._state_lock = Lock()
        self.logger = logging.getLogger(__name__)

    async def _initialize_with_retry(self, max_retries: int = 3, delay: float = 1.0):
        """Initialize clients with exponential backoff retry logic"""
        for attempt in range(max_retries):
            try:
                await self._initialize_clients()
                return
            except Exception as e:
                if attempt == max_retries - 1:
                    self.logger.error(
                        f"Failed to initialize after {max_retries} attempts"
                    )
                    raise
                wait_time = delay * (2**attempt)
                self.logger.warning(
                    f"Initialization attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {wait_time} seconds..."
                )
                await asyncio.sleep(wait_time)

    async def _initialize_clients(self):
        """Initialize all clients with proper locking and error handling"""
        self.logger.info("Starting to initialize database clients")
        try:
            async with self._state_lock:
                # Initialize MongoDB client
                self.mongo_client = await init_mongo()
                self.logger.info("MongoDB client initialized successfully")

                # Initialize Redis client
                self.redis_client = await init_redis()
                self.logger.info("Redis client initialized successfully")

                # Initialize WebSocket client with worker ID
                worker_id = os.getenv("GUNICORN_WORKER_ID", "default-worker-id")
                self.websocket_client = WebSocketClient(
                    self.redis_client, worker_id=worker_id
                )
                await self.websocket_client.initialize()
                self.logger.info(
                    f"WebSocket client initialized successfully with worker_id {worker_id}"
                )
        except Exception as e:
            self.logger.error(f"Error initializing clients: {e}")
            await self.close_clients()
            raise

    async def close_clients(self):
        """Safely close all client connections with independent error handling"""
        async with self._state_lock:
            self.logger.info("Closing database clients")
            errors = []

            if self.mongo_client:
                try:
                    await self.mongo_client.close()
                except Exception as e:
                    errors.append(f"MongoDB cleanup error: {e}")
                finally:
                    self.mongo_client = None

            if self.redis_client:
                try:
                    await self.redis_client.close()
                except Exception as e:
                    errors.append(f"Redis cleanup error: {e}")
                finally:
                    self.redis_client = None

            if self.websocket_client:
                try:
                    await self.websocket_client.close()
                except Exception as e:
                    errors.append(f"WebSocket cleanup error: {e}")
                finally:
                    self.websocket_client = None

            if errors:
                error_msg = "; ".join(errors)
                self.logger.error(f"Errors during cleanup: {error_msg}")
                raise RuntimeError(f"Cleanup errors occurred: {error_msg}")

    async def get_mongo_client(self):
        """Get MongoDB client with proper state verification"""
        async with self._state_lock:
            if not self.mongo_client:
                raise RuntimeError("MongoDB client not initialized")
            return self.mongo_client

    async def get_redis_client(self):
        """Get Redis client with proper state verification"""
        async with self._state_lock:
            if not self.redis_client:
                raise RuntimeError("Redis client not initialized")
            return self.redis_client

    async def get_websocket_client(self):
        """Get WebSocket client with proper state verification"""
        async with self._state_lock:
            if not self.websocket_client:
                raise RuntimeError("WebSocket client not initialized")
            return self.websocket_client
