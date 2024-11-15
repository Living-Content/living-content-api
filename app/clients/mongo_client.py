# app/clients/mongo_client.py

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
    ssl_ca_crt = config["ingress"]["ssl_ca_crt"]
    shared_ssl_pem = config["ingress"]["shared_ssl_pem"]

    mongo_host = secrets["mongo_host"]
    mongo_port = secrets["mongo_port"]
    mongo_db = secrets["mongo_db_name"]
    mongo_user = secrets["mongo_rw_username"]
    mongo_password = secrets["mongo_rw_password"]

    # Construct the MongoDB URI
    if mongo_user and mongo_password:
        mongodb_uri = f"mongodb://{mongo_user}:{mongo_password}@{mongo_host}:{mongo_port}/{mongo_db}?authSource={mongo_db}"
        logging.debug(f"MongoDB URI: {mongodb_uri}")
    else:
        mongodb_uri = f"mongodb://{mongo_host}:{mongo_port}/{mongo_db}"

    try:
        mongo_client = AsyncIOMotorClient(
            mongodb_uri,
            tls=True,
            tlsCAFile=ssl_ca_crt,
            tlsCertificateKeyFile=shared_ssl_pem,
            maxPoolSize=100,
            minPoolSize=10,
        )
        return mongo_client
    except Exception as e:
        logging.error(f"Failed to create MongoDB client: {e}\n{traceback.format_exc()}")
        raise


# Get a client from the pool


def get_mongo_client(mongo_pool):
    if mongo_pool is None:
        raise RuntimeError("MongoDB connection pool not initialized")
    return mongo_pool
