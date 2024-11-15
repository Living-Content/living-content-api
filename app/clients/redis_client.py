# /app/clients/redis_client.py

import logging
import redis.asyncio as redis
from redis.exceptions import (
    ConnectionError as RedisConnectionError,
    TimeoutError as RedisTimeoutError,
)
from app.lib.config import get_config
from app.lib.secrets import get_secrets


async def init_redis() -> redis.Redis:
    config = get_config()
    secrets = get_secrets()

    redis_db = 0

    ssl_ca_crt = config["ingress"]["ssl_ca_crt"]
    shared_ssl_crt = config["ingress"]["shared_ssl_crt"]
    shared_ssl_key = config["ingress"]["shared_ssl_key"]

    redis_host = secrets["redis_host"]
    redis_port = secrets["redis_port"]
    redis_password = secrets["redis_password"]

    logging.debug("Redis variables loaded successfully")

    try:
        logging.debug("Connecting to Redis...")

        # Construct the Redis URL with rediss:// scheme
        redis_url = f"rediss://{redis_host}:{redis_port}/{redis_db}"

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
        await redis_client.ping()
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


async def get_redis_client(redis_client):
    if redis_client is None:
        raise RuntimeError("Redis client not initialized")
    return redis_client
