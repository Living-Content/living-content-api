import asyncio
import logging
import os
from typing import Any

from dotenv import load_dotenv


class SecretsSingleton:
    _instance = None
    _secrets: dict[str, Any] = None
    _lock = asyncio.Lock()
    _initialized = False
    _logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SecretsSingleton, cls).__new__(cls)
        return cls._instance

    @classmethod
    async def _load_secrets(cls) -> dict[str, Any]:
        """Load secrets from environment variables or .env file."""
        # Load .env file if it exists
        load_dotenv()
        
        secrets = {}
        
        # Define expected secret keys
        secret_keys = [
            "mongo_host",
            "mongo_port",
            "mongo_db_name",
            "mongo_rw_username",
            "mongo_rw_password",
            "redis_host",
            "redis_port",
            "redis_password",
            "openai_api_key",
            "anthropic_api_key",
            "google_api_key",
            "azure_api_key",
        ]
        
        # Load from environment variables
        for key in secret_keys:
            # Try uppercase first (standard for env vars)
            value = os.getenv(key.upper())
            if value is None:
                # Try lowercase for backwards compatibility
                value = os.getenv(key)
            
            if value:
                secrets[key] = value
                cls._logger.debug(f"Loaded secret: {key}")
        
        # Fallback to check ./secrets/ directory for backwards compatibility
        secrets_dir = "./secrets/"
        if os.path.exists(secrets_dir):
            cls._logger.info("Found legacy ./secrets/ directory, loading for backwards compatibility")
            for secret_file in os.listdir(secrets_dir):
                if secret_file not in secrets:  # Don't override env vars
                    secret_file_path = os.path.join(secrets_dir, secret_file)
                    if os.path.isfile(secret_file_path):
                        try:
                            with open(secret_file_path, "r") as f:
                                value = f.read().strip()
                                if value:
                                    secrets[secret_file] = value
                                    cls._logger.debug(f"Loaded legacy secret from file: {secret_file}")
                        except Exception as e:
                            cls._logger.warning(f"Failed to read legacy secret file {secret_file}: {e}")
        
        return secrets


    @classmethod
    async def initialize(cls) -> dict[str, Any]:
        if not cls._initialized:
            async with cls._lock:
                if not cls._initialized:
                    cls._secrets = await cls._load_secrets()
                    cls._initialized = True
                    cls._logger.info("Secrets initialized")
        return cls._secrets

    @classmethod
    def get_secrets(cls) -> dict[str, Any]:
        if not cls._initialized:
            raise RuntimeError(
                "Secrets not initialized. Call 'await SecretsSingleton.initialize()' first."
            )
        return cls._secrets


secrets_singleton = SecretsSingleton()
get_secrets = secrets_singleton.get_secrets
