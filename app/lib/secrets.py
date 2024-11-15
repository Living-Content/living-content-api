import os
import asyncio
import aiofiles
import logging
from typing import Dict, Any


class SecretsSingleton:
    _instance = None
    _secrets: Dict[str, Any] = None
    _lock = asyncio.Lock()
    _initialized = False
    _logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SecretsSingleton, cls).__new__(cls)
        return cls._instance

    @classmethod
    async def _load_secrets(cls) -> Dict[str, Any]:
        """Load secrets from files in the ./secrets/ directory."""
        secrets = {}
        secrets_dir = "./secrets/"  # Secrets directory

        try:
            # List all files in the secrets directory
            secret_files = os.listdir(secrets_dir)
        except FileNotFoundError:
            cls._logger.error(f"Secrets directory not found: {secrets_dir}")
            return secrets
        except Exception as e:
            cls._logger.error(f"Error accessing secrets directory: {e}")
            return secrets

        # Process each secret file, skipping directories
        for secret_file in secret_files:
            secret_file_path = os.path.join(secrets_dir, secret_file)

            # Skip if the item is a directory
            if os.path.isdir(secret_file_path):
                cls._logger.debug(f"Skipping directory: {secret_file_path}")
                continue

            cls._logger.info(f"Attempting to load secret from file: {secret_file_path}")

            secret_value = await cls._load_secret_from_file(secret_file_path)

            if secret_value:
                # Use the filename (without the directory) as the key
                secrets[secret_file] = secret_value
            else:
                cls._logger.warning(
                    f"Secret file '{secret_file}' could not be read or is empty."
                )

        return secrets

    @classmethod
    async def _load_secret_from_file(cls, secret_file_path: str) -> str:
        try:
            async with aiofiles.open(secret_file_path, "r") as file:
                secret_value = await file.read()
                return secret_value.strip()  # Remove any extra whitespace/newlines
        except FileNotFoundError:
            cls._logger.error(f"Secret file {secret_file_path} not found.")
        except Exception as e:
            cls._logger.error(f"Error reading secret from {secret_file_path}: {e}")
        return None

    @classmethod
    async def initialize(cls) -> Dict[str, Any]:
        if not cls._initialized:
            async with cls._lock:
                if not cls._initialized:
                    cls._secrets = await cls._load_secrets()
                    cls._initialized = True
                    cls._logger.info("Secrets initialized")
        return cls._secrets

    @classmethod
    def get_secrets(cls) -> Dict[str, Any]:
        if not cls._initialized:
            raise RuntimeError(
                "Secrets not initialized. Call 'await SecretsSingleton.initialize()' first."
            )
        return cls._secrets


secrets_singleton = SecretsSingleton()
get_secrets = secrets_singleton.get_secrets
