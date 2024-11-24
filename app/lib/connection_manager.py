import logging
import os
import asyncio
from asyncio import Lock, Event
from typing import Optional, Callable, Any
from fastapi import FastAPI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

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

        This method ensures thread safety using double-checked locking to prevent
        race conditions during the creation of the singleton instance.

        Args:
            app: Optional FastAPI application instance
            max_retries: Maximum number of initialization attempts
            retry_delay: Base delay between retries (uses exponential backoff)

        Returns:
            Initialized ConnectionManager instance
        """
        if not cls._instance:
            async with cls._lock:
                if not cls._instance:
                    instance = cls()
                    if app:
                        instance.app = app
                    cls._instance = instance
                    await instance._initialize_clients()
        return cls._instance

    def __init__(self):
        """Initialize instance variables"""
        self.app: Optional[FastAPI] = None
        self.mongo_client = None
        self.redis_client = None
        self.websocket_client = None
        self._mongo_ready = Event()
        self._redis_ready = Event()
        self._state_lock = Lock()
        self.logger = logging.getLogger(__name__)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
    )
    async def _initialize_mongo(self):
        """Initialize MongoDB client with Tenacity retry logic."""
        self.mongo_client = await init_mongo()
        self._mongo_ready.set()
        self.logger.info("MongoDB client initialized successfully")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
    )
    async def _initialize_redis(self):
        """Initialize Redis client with Tenacity retry logic."""
        self.redis_client = await init_redis()
        self._redis_ready.set()
        self.logger.info("Redis client initialized successfully")

    async def _initialize_websocket(self):
        """Initialize WebSocket client after Redis is ready."""
        worker_id = os.getenv("GUNICORN_WORKER_ID", "default-worker-id")
        self.websocket_client = WebSocketClient(self.redis_client, worker_id=worker_id)
        await self.websocket_client.initialize()
        self.logger.info(
            f"WebSocket client initialized successfully with worker_id {worker_id}"
        )

    async def _initialize_clients(self):
        """Initialize clients sequentially with Redis dependency for WebSocket."""
        self.logger.info("Starting to initialize database clients")
        try:
            async with self._state_lock:
                await self._initialize_mongo()
                await self._initialize_redis()
                await self._initialize_websocket()
        except Exception as e:
            self.logger.error(f"Error initializing clients: {e}")
            await self.close_clients()
            raise

    async def close_clients(self):
        """Safely close all client connections with independent error handling."""
        async with self._state_lock:
            self.logger.info("Closing database clients")
            errors = []

            # MongoDB Cleanup
            if self.mongo_client:
                self.logger.debug("Attempting to close MongoDB client.")
                try:
                    self.mongo_client.close()  # Call directly (not `await`)
                    self.logger.info("MongoDB client closed successfully.")
                except Exception as e:
                    errors.append(f"MongoDB cleanup error: {e}")
                finally:
                    self.mongo_client = None
            else:
                self.logger.warning("MongoDB client is None during cleanup.")

            # Redis Cleanup
            if self.redis_client:
                self.logger.debug("Attempting to close Redis client.")
                try:
                    await self.redis_client.close()
                    self.logger.info("Redis client closed successfully.")
                except Exception as e:
                    errors.append(f"Redis cleanup error: {e}")
                finally:
                    self.redis_client = None
            else:
                self.logger.warning("Redis client is None during cleanup.")

            # WebSocket Client Cleanup
            if self.websocket_client:
                self.logger.debug("Attempting to close WebSocket client.")
                try:
                    await self.websocket_client.close()
                    self.logger.info("WebSocket client closed successfully.")
                except Exception as e:
                    errors.append(f"WebSocket cleanup error: {e}")
                finally:
                    self.websocket_client = None
            else:
                self.logger.warning("WebSocket client is None during cleanup.")

            # Log errors if any
            if errors:
                error_msg = "; ".join(errors)
                self.logger.error(f"Errors during cleanup: {error_msg}")
                raise RuntimeError(f"Cleanup errors occurred: {error_msg}")

    async def get_mongo_client(self):
        """Get MongoDB client with readiness verification"""
        await self._mongo_ready.wait()
        if not self.mongo_client:
            raise RuntimeError("MongoDB client not initialized")
        return self.mongo_client

    async def get_redis_client(self):
        """Get Redis client with readiness verification"""
        await self._redis_ready.wait()
        if not self.redis_client:
            raise RuntimeError("Redis client not initialized")
        return self.redis_client

    async def get_websocket_client(self):
        """Get WebSocket client with proper state verification"""
        async with self._state_lock:
            if not self.websocket_client:
                raise RuntimeError("WebSocket client not initialized")
            return self.websocket_client
