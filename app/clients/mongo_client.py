import logging
import traceback

from motor.motor_asyncio import AsyncIOMotorClient

from app.lib.config import get_config
from app.lib.secrets import get_secrets


async def init_mongo() -> AsyncIOMotorClient:
    config = get_config()
    secrets = get_secrets()

    logging.debug("Initializing MongoDB client")

    # MongoDB connection details from configuration
    ssl_ca_crt = config.get("ingress", {}).get("ssl_ca_crt")
    shared_ssl_pem = config.get("ingress", {}).get("shared_ssl_pem")

    mongo_host = secrets.get("mongo_host")
    mongo_port = secrets.get("mongo_port")
    mongo_db = secrets.get("mongo_db_name")
    mongo_user = secrets.get("mongo_rw_username")
    mongo_password = secrets.get("mongo_rw_password")

    # Validate critical configuration
    if not mongo_host or not mongo_port or not mongo_db:
        raise ValueError(
            "MongoDB configuration is incomplete: host, port, and db_name are required."
        )

    # Construct the MongoDB URI
    if mongo_user and mongo_password:
        mongodb_uri = f"mongodb://{mongo_user}:{mongo_password}@{mongo_host}:{mongo_port}/{mongo_db}?authSource={mongo_db}"
        sanitized_uri = mongodb_uri.replace(mongo_password, "*****")
    else:
        mongodb_uri = f"mongodb://{mongo_host}:{mongo_port}/{mongo_db}"
        sanitized_uri = mongodb_uri

    logging.debug(f"MongoDB URI: {sanitized_uri}")

    try:
        mongo_client = AsyncIOMotorClient(
            mongodb_uri,
            tls=True,
            tlsCAFile=ssl_ca_crt,
            tlsCertificateKeyFile=shared_ssl_pem,
            maxPoolSize=100,
            minPoolSize=10,
        )
        await test_mongo_connection(mongo_client)
        return mongo_client
    except Exception as e:
        logging.error(f"Failed to create MongoDB client: {e}\n{traceback.format_exc()}")
        raise


def get_mongo_client(mongo_pool: AsyncIOMotorClient | None) -> AsyncIOMotorClient:
    if mongo_pool is None:
        raise RuntimeError("MongoDB connection pool not initialized")
    return mongo_pool


def close_mongo(mongo_client: AsyncIOMotorClient | None):
    if mongo_client:
        try:
            mongo_client.close()
            logging.info("MongoDB client closed successfully.")
        except Exception as e:
            logging.error(f"Error closing MongoDB client: {e}")
    else:
        logging.warning("MongoDB client was already None during cleanup.")


async def test_mongo_connection(mongo_client: AsyncIOMotorClient):
    try:
        await mongo_client.server_info()
        logging.info("MongoDB connection is healthy.")
    except Exception as e:
        logging.error(f"Failed to connect to MongoDB: {e}")
        raise
