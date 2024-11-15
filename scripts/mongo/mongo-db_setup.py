# scripts/mongo-db_setup.py

import logging
import os
import sys
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure
from uuid import uuid4
from datetime import datetime, timezone

# Setup logging to console and file

# Remove existing handlers if Python < 3.8
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Setup logging to console only
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(stream=sys.stdout),
    ],
)
logger = logging.getLogger()  # Configure root logger

# Ensure that logs are flushed immediately
logging.getLogger().handlers[0].flush = sys.stdout.flush

# Optionally, set propagate to True if using module-level loggers
logger.propagate = True


def setup_database():
    def get_secret(secret_name):
        """
        Get the secret from a Docker secret file or fallback to an environment variable.
        """
        secret_path = f"./secrets/{secret_name}"

        # Check if the secret is available as a Docker secret file
        if os.path.exists(secret_path):
            with open(secret_path, "r") as secret_file:
                return secret_file.read().strip()
        else:
            # Fallback to environment variable if the secret file does not exist
            return os.getenv(secret_name)

    # MongoDB connection details
    mongo_host = os.getenv("MONGO_HOST")
    mongo_port = os.getenv("MONGO_PORT")
    mongo_db = os.getenv("MONGO_DB_NAME")

    ssl_ca_crt = os.getenv("SSL_CA_CRT")
    ssl_pem_file = os.getenv("SHARED_SSL_PEM")

    # Fetch secrets using the get_secret function
    mongo_password = get_secret("mongo_rw_password")
    mongo_user = get_secret("mongo_rw_username")

    logger.info("Establishing MongoDB connection...")

    # Construct the MongoDB URI
    mongodb_uri = f"mongodb://{mongo_user}:{mongo_password}@{mongo_host}:{mongo_port}/{mongo_db}?authSource={mongo_db}"
    logger.info(f"MongoDB URI (for testing): {mongodb_uri}")

    # Create a MongoDB client with SSL/TLS configuration
    try:
        mongo_client = MongoClient(
            mongodb_uri,
            tls=True,
            tlsCAFile=ssl_ca_crt,
            tlsCertificateKeyFile=ssl_pem_file,
        )
        logger.info("MongoDB client created successfully")
    except ConnectionFailure as e:
        logger.error(f"Failed to create MongoDB client: {e}")
        raise

    logger.info(f"Mongo client: {mongo_client}")
    # Access the specified database
    try:
        db = mongo_client[mongo_db]
        logger.info(f"Accessed database: {mongo_db}")
    except Exception as e:
        logger.error(f"Failed to access database: {e}")
        raise

    # Function to setup the database with initial collections and documents

    try:
        # Ensure indexes are set correctly
        logger.info("Creating indexes on relevant fields...")

        db.permissions_tokens.create_index([("userId", ASCENDING)])
        db.content_sessions.create_index([("userId", ASCENDING)])
        db.content_sessions.create_index([("contentSessionId", ASCENDING)])
        db.notifications.create_index([("userId", ASCENDING)])
        db.notifications.create_index([("expiresAt", ASCENDING)], expireAfterSeconds=0)
        db.users.create_index([("authProviders", ASCENDING)])
        db.users.create_index([("accessToken", ASCENDING)])

        logger.info("Indexes created on relevant fields.")

        user_id = str(uuid4())
        permissions_token = str(uuid4())
        access_token = str(uuid4())
        content_session_id = str(uuid4())

        # Insert initial user document
        user_doc = {
            "_id": user_id,
            "accessToken": access_token,
            "permissionsToken": permissions_token,
            "activeContentSessionId": content_session_id,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "lastAccessed": datetime.now(timezone.utc).isoformat(),
            "requests": {"allTime": 0},
            "unreadNotifications": {},
            "authProviders": {},
            "verified": False,
            "emailAddress": None,
            "password": None,
            "locked": False,
        }
        db.users.insert_one(user_doc)
        logger.info("Initial user document inserted")

        # Insert initial permissions token document
        permissions_token_doc = {
            "_id": permissions_token,
            "userId": user_id,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "lastAccessed": datetime.now(timezone.utc).isoformat(),
            "permissions": {"role": "user"},
        }
        db.permissions_tokens.insert_one(permissions_token_doc)
        logger.info("Initial permissions token document inserted")

        # Insert initial content session document
        content_session_doc = {
            "_id": content_session_id,
            "userId": user_id,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "lastAccessed": datetime.now(timezone.utc).isoformat(),
            "unreadMessages": False,
            "name": None,
            "sessionData": {"storageKey": {"exampleKey": "exampleValue"}},
        }
        db.content_sessions.insert_one(content_session_doc)
        logger.info("Initial content session document inserted")

        # Insert initial notifications document
        notification_id = str(uuid4())
        message_id = str(uuid4())
        task_id = str(uuid4())
        notifications_doc = {
            "_id": notification_id,
            "userId": user_id,
            "contentSessionId": content_session_id,
            "associatedMessageId": message_id,
            "associatedTaskId": task_id,
            "associatedImage": "https://example.com/image.jpg",
            "messageId": message_id,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "type": "text",
            "toastMessage": "You have a new message!",
            "associatedMessage": "Welcome to Living Content!",
            "urgency": "normal",
            "persistent": False,
            "seen": False,
            "seenAt": None,
            "responseData": {"exampleKey": "exampleValue"},
        }
        db.notifications.insert_one(notifications_doc)
        logger.info("Initial notifications document inserted")

    except Exception as e:
        logger.error(f"Error during database setup: {e}")
        raise


# Run the setup function
setup_database()
logger.info("MongoDB setup complete with initial collections and documents")
