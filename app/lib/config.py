import asyncio
import logging
import os
from collections.abc import Callable
from typing import Any

import aiofiles
import yaml


class ConfigSingleton:
    _instance = None
    _config: dict[str, Any] = {}
    _lock = asyncio.Lock()
    _initialized = False
    _logger = logging.getLogger(__name__)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigSingleton, cls).__new__(cls)
        return cls._instance

    @classmethod
    async def initialize(
        cls, allowed_files: list[str], get_mongo_client: Callable | None = None
    ) -> dict[str, Any]:
        if not cls._initialized:
            async with cls._lock:
                if not cls._initialized:
                    # To do: Implement MongoDB config loading
                    # Attempt to load from MongoDB
                    # db_client = await get_mongo_client()
                    # cls._config = await cls._load_config_from_db(db_client)

                    # Fallback to YAML if MongoDB load fails
                    # if not cls._config:
                    #    cls._config = await cls._load_config_from_yaml(allowed_files)

                    cls._config = await cls._load_config_from_yaml(allowed_files)
                    cls._initialized = True
                    cls._logger.info("Config initialized")
        return cls._config

    @classmethod
    async def _load_config_from_db(cls, db_client) -> dict[str, Any]:
        db_config = {}
        db = db_client["config_db"]
        config_collection = db["Config"]

        async for config in config_collection.find({"active": True}):
            db_config[config["category"]] = config["data"]

        return db_config

    @classmethod
    async def _load_config_from_yaml(cls, allowed_files: list[str]) -> dict[str, Any]:
        config_dir = "config/app"
        config_dict = {}

        for filename in allowed_files:
            config_file_path = os.path.join(config_dir, f"{filename}.yaml")
            if os.path.exists(config_file_path):
                async with aiofiles.open(config_file_path, "r") as file:
                    content = await file.read()
                    file_config = yaml.safe_load(content)
                    config_dict.update(file_config)
            else:
                cls._logger.warning(f"Config file {config_file_path} does not exist")

        return config_dict

    @classmethod
    async def reload(
        cls, allowed_files: list[str], get_mongo_client: Callable
    ) -> dict[str, Any]:
        async with cls._lock:
            db_client = await get_mongo_client()
            cls._config = await cls._load_config_from_db(db_client)
            if not cls._config:
                cls._config = await cls._load_config_from_yaml(allowed_files)
            return cls._config

    @classmethod
    def get_config(cls, config_name: str = None) -> Any:
        if not cls._initialized:
            raise RuntimeError(
                "Config not initialized. Call 'await ConfigSingleton.initialize()' first."
            )

        if config_name:
            # Return specific section of the config
            return cls._config.get(config_name)

        # Return entire config if no specific name is provided
        return cls._config


config_singleton = ConfigSingleton()
get_config = config_singleton.get_config
