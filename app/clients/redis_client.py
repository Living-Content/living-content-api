import logging
import redis.asyncio as redis
from redis.exceptions import (
    ConnectionError as RedisConnectionError,
    TimeoutError as RedisTimeoutError,
)
from app.lib.config import get_config
from app.lib.secrets import get_secrets
from typing import Optional


async def init_redis() -> redis.Redis:
    config = get_config()
    secrets = get_secrets()

    redis_db = 0  # Default database index

    ssl_ca_crt = config.get("ingress", {}).get("ssl_ca_crt")
    shared_ssl_crt = config.get("ingress", {}).get("shared_ssl_crt")
    shared_ssl_key = config.get("ingress", {}).get("shared_ssl_key")

    redis_host = secrets.get("redis_host")
    redis_port = secrets.get("redis_port")
    redis_password = secrets.get("redis_password")

    # Validate critical configuration
    if not redis_host or not redis_port:
        raise ValueError(
            "Redis configuration is incomplete: host and port are required."
        )

    logging.debug("Redis variables loaded successfully")

    try:
        logging.debug("Connecting to Redis...")

        # Construct the Redis URL with rediss:// scheme
        redis_url = f"rediss://{redis_host}:{redis_port}/{redis_db}"
        sanitized_url = (
            redis_url.replace(redis_password, "*****") if redis_password else redis_url
        )
        logging.debug(f"Redis URL: {sanitized_url}")

        # Create a connection pool
        pool = redis.ConnectionPool.from_url(
            url=redis_url,
            max_connections=100,  # Adjust this value as needed
            password=redis_password,
            decode_responses=True,
            ssl_ca_certs=ssl_ca_crt,
            ssl_certfile=shared_ssl_crt,
            ssl_keyfile=shared_ssl_key,
        )

        # Create a Redis client using the connection pool
        redis_client = redis.Redis(connection_pool=pool)

        # Test the connection
        await test_redis_connection(redis_client)
        logging.debug("Successfully connected to Redis")

        return redis_client

    except RedisConnectionError as e:
        logging.error(f"Redis connection error: {e}")
        raise

    except RedisTimeoutError as e:
        logging.error(f"Redis timeout error: {e}")
        raise

    except Exception as e:
        logging.error(f"Failed to connect to Redis: {e}")
        raise


async def test_redis_connection(redis_client: redis.Redis):
    """Test the Redis connection to ensure it's healthy."""
    try:
        info = await redis_client.info()
        logging.debug(f"Redis server info: {info}")
        logging.info("Redis connection is healthy.")
    except Exception as e:
        logging.error(f"Failed to connect to Redis: {e}")
        raise


async def get_redis_client(redis_client: Optional[redis.Redis]) -> redis.Redis:
    if redis_client is None:
        raise RuntimeError("Redis client not initialized")
    return redis_client


async def close_redis(redis_client: Optional[redis.Redis]):
    if redis_client:
        try:
            await redis_client.close()
            logging.info("Redis client closed successfully.")
        except Exception as e:
            logging.error(f"Error closing Redis client: {e}")
