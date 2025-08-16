"""Configuration management that fetches from Tenant Manager.

This provides a unified interface for both configuration and secrets:
1. Fetches complete config from Tenant Manager at startup
2. Caches everything in memory for fast access
3. Provides backward compatibility with existing code
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

import aiohttp
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class ConfigSingleton:
    """Configuration singleton that fetches from Tenant Manager."""
    
    _instance = None
    _config: Dict[str, Any] = {}
    _lock = asyncio.Lock()
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigSingleton, cls).__new__(cls)
        return cls._instance
    
    @classmethod
    async def initialize(
        cls,
        allowed_files: Optional[list[str]] = None,  # Kept for compatibility
        get_mongo_client: Optional[Any] = None,  # Kept for compatibility
    ) -> Dict[str, Any]:
        """Initialize configuration from Tenant Manager.
        
        Args:
            allowed_files: Ignored, kept for backward compatibility
            get_mongo_client: Ignored, kept for backward compatibility
            
        Returns:
            Complete configuration dictionary
        """
        if cls._initialized:
            return cls._config
            
        async with cls._lock:
            if cls._initialized:
                return cls._config
                
            logger.info("Initializing configuration from Tenant Manager...")
            
            # Load environment variables (for TM URL and token)
            load_dotenv()
            
            # Get Tenant Manager URL and API token
            tm_url = os.getenv("TENANT_MANAGER_URL")
            api_token = os.getenv("API_TOKEN")
            project_id = os.getenv("PROJECT_ID")
            
            if not all([tm_url, api_token, project_id]):
                # Fallback to local config for development
                logger.warning("Missing TM config, falling back to local files")
                cls._config = await cls._load_local_config()
            else:
                try:
                    # Fetch from Tenant Manager
                    cls._config = await cls._fetch_from_tenant_manager(
                        tm_url, api_token, project_id
                    )
                except Exception as e:
                    logger.error(f"Failed to fetch from TM: {e}, using local fallback")
                    cls._config = await cls._load_local_config()
            
            cls._initialized = True
            logger.info(f"Configuration initialized with {len(cls._config)} values")
            
        return cls._config
    
    @classmethod
    async def _fetch_from_tenant_manager(
        cls, tm_url: str, api_token: str, project_id: str
    ) -> Dict[str, Any]:
        """Fetch configuration from Tenant Manager.
        
        Args:
            tm_url: Tenant Manager base URL
            api_token: API authentication token
            project_id: Project ID
            
        Returns:
            Configuration dictionary
        """
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {api_token}"}
            url = f"{tm_url}/api/config/{project_id}"
            
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise Exception(f"TM returned {response.status}")
                
                data = await response.json()
                
                # Flatten the response into a config dict
                config = {}
                
                # Infrastructure config
                config["project_id"] = data.get("project_id")
                config["project_name"] = data.get("project_name")
                config["environment"] = data.get("environment")
                config["cluster_name"] = data.get("cluster_name")
                
                # Image URLs
                config["api_image"] = data.get("api_image")
                config["mongo_image"] = data.get("mongo_image")
                config["redis_image"] = data.get("redis_image")
                
                # Client configs (as nested dicts)
                config["clients"] = data.get("clients", {})
                config["persona"] = data.get("persona", {})
                config["eqty"] = data.get("eqty", {})
                config["internal_functions"] = data.get("internal_functions", {})
                config["plugins"] = data.get("plugins", {})
                
                # Secrets are included in the response
                secrets = data.get("secret_keys", [])
                for key in secrets:
                    # TM should have resolved these already
                    config[key] = os.getenv(key.upper())
                
                return config
    
    @classmethod
    async def _load_local_config(cls) -> Dict[str, Any]:
        """Load configuration from local files (fallback).
        
        Returns:
            Configuration dictionary from local YAML files
        """
        config = {}
        
        # Load from environment variables
        for key, value in os.environ.items():
            config[key.lower()] = value
        
        # Try to load YAML files if they exist
        import yaml
        import aiofiles
        
        config_files = [
            "clients", "persona", "eqty", "internal_functions", "plugins"
        ]
        
        for filename in config_files:
            try:
                file_path = f"config/{filename}.yaml"
                if os.path.exists(file_path):
                    async with aiofiles.open(file_path, "r") as f:
                        content = await f.read()
                        config[filename] = yaml.safe_load(content)
            except Exception as e:
                logger.warning(f"Failed to load {filename}.yaml: {e}")
        
        return config
    
    @classmethod
    async def reload(
        cls,
        allowed_files: Optional[list[str]] = None,
        get_mongo_client: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Reload configuration from Tenant Manager.
        
        Args:
            allowed_files: Ignored, kept for backward compatibility
            get_mongo_client: Ignored, kept for backward compatibility
            
        Returns:
            Reloaded configuration dictionary
        """
        async with cls._lock:
            cls._initialized = False
            return await cls.initialize()
    
    @classmethod
    def get_config(cls, config_name: Optional[str] = None) -> Any:
        """Get configuration value.
        
        Args:
            config_name: Optional specific config key or section
            
        Returns:
            Config value or entire config if no key specified
        """
        if not cls._initialized:
            raise RuntimeError(
                "Config not initialized. Call 'await ConfigSingleton.initialize()' first."
            )
        
        if config_name:
            # Check for nested path (e.g., "clients.openai.api_key")
            if "." in config_name:
                parts = config_name.split(".")
                value = cls._config
                for part in parts:
                    if isinstance(value, dict):
                        value = value.get(part)
                    else:
                        return None
                return value
            
            # Direct key lookup
            return cls._config.get(config_name)
        
        # Return entire config
        return cls._config


# Singleton instance
config_singleton = ConfigSingleton()
get_config = config_singleton.get_config

# For backward compatibility with code expecting get_secrets
def get_secrets() -> Dict[str, Any]:
    """Get secrets (now part of unified config).
    
    Returns:
        Dictionary of secrets
    """
    # Filter config to only return secret-like keys
    config = get_config()
    secrets = {}
    
    # Common secret patterns
    secret_patterns = [
        "password", "secret", "key", "token",
        "mongo_", "redis_", "api_key"
    ]
    
    for key, value in config.items():
        if any(pattern in key.lower() for pattern in secret_patterns):
            secrets[key] = value
    
    return secrets