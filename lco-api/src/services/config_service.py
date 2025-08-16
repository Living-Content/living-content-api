"""Configuration management service using Pydantic models."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yaml
from google.cloud import firestore
from pydantic import ValidationError

from models.config import LocalConfig, ProjectConfig
from utils.auth import get_tenant_manager_token

logger = logging.getLogger(__name__)


class ConfigService:
    """Handles configuration fetching, storage, and management."""
    
    def __init__(self, project_root: Optional[Path] = None):
        """Initialize config service.
        
        Args:
            project_root: Root directory of the project (defaults to cwd)
        """
        self.project_root = project_root or Path.cwd()
        self.config_dir = self.project_root / "config"
        self.local_config_file = self.project_root / ".lco-api.json"
        self._db_client = None
        self._project_config: Optional[ProjectConfig] = None
        self._local_config: Optional[LocalConfig] = None
        
    @property
    def db(self) -> firestore.Client:
        """Lazy-load Firestore client."""
        if self._db_client is None:
            project_id = self.get_gcp_project_id()
            self._db_client = firestore.Client(project=project_id)
        return self._db_client
    
    @property
    def local_config(self) -> LocalConfig:
        """Get cached local config or load from file."""
        if self._local_config is None:
            self._local_config = self.load_local_config()
        return self._local_config
    
    def get_gcp_project_id(self) -> str:
        """Get GCP project ID from local config or environment."""
        # Check local config first
        if self.local_config_file.exists():
            try:
                config = self.load_local_config()
                return config.gcp_project_id
            except (ValidationError, FileNotFoundError):
                pass
        
        # Fall back to environment
        import os
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "living-content")
        return project_id
    
    def fetch_config_with_token(self, token: str, tenant_manager_url: str) -> ProjectConfig:
        """Fetch project configuration using one-time token.
        
        Args:
            token: One-time configuration token
            tenant_manager_url: URL of the Tenant Manager API
            
        Returns:
            ProjectConfig object with fetched configuration
        """
        logger.info("Fetching configuration with token")
        
        response = requests.get(
            f"{tenant_manager_url}/projects/config",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30
        )
        
        if response.status_code != 200:
            error = response.json().get("error", {})
            raise ValueError(f"Failed to fetch config: {error.get('message', 'Unknown error')}")
        
        data = response.json()
        logger.debug(f"Fetched config for project {data['project_name']}")
        
        # Parse apps section properly
        if "apps" in data:
            for app_name, app_data in data["apps"].items():
                # Convert nested dicts to proper models
                if "requests" in app_data and app_data["requests"]:
                    from models.config import ResourceSpec
                    app_data["requests"] = ResourceSpec(**app_data["requests"])
                if "limits" in app_data and app_data["limits"]:
                    from models.config import ResourceSpec
                    app_data["limits"] = ResourceSpec(**app_data["limits"])
                
                # Create AppConfig
                from models.config import AppConfig
                data["apps"][app_name] = AppConfig(**app_data)
        
        # Create ProjectConfig object with validation
        config = ProjectConfig(**data)
        config.tenant_manager_url = tenant_manager_url
        
        # Save essential info to local config
        self.save_local_config(config)
        
        # Cache the project config
        self._project_config = config
        
        return config
    
    def save_local_config(self, project_config: ProjectConfig):
        """Save essential config locally for CLI operations.
        
        Args:
            project_config: ProjectConfig object to extract local data from
        """
        local_config = LocalConfig(
            project_id=project_config.project_id,
            project_name=project_config.project_name,
            environment=project_config.environment,
            gcp_project_id="living-content",  # TODO: Get from project config
            tenant_manager_url=project_config.tenant_manager_url
        )
        
        # Save using model_dump at the boundary
        with open(self.local_config_file, "w") as f:
            json.dump(local_config.model_dump(), f, indent=2)
        
        # Update cache
        self._local_config = local_config
        
        logger.info(f"Saved local config to {self.local_config_file}")
    
    def load_local_config(self) -> LocalConfig:
        """Load and validate local configuration file.
        
        Returns:
            LocalConfig object
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValidationError: If config is invalid
        """
        if not self.local_config_file.exists():
            raise FileNotFoundError(f"Local config not found at {self.local_config_file}")
        
        with open(self.local_config_file) as f:
            data = json.load(f)
        
        return LocalConfig(**data)
    
    def store_in_firestore(
        self, 
        config: ProjectConfig, 
        exclude_keys: Optional[List[str]] = None
    ):
        """Store configuration in Firestore.
        
        Args:
            config: ProjectConfig object to store
            exclude_keys: List of keys to exclude from Firestore storage
        """
        exclude_keys = exclude_keys or [
            "clients", "eqty", "internal_functions", "persona", "plugins"
        ]
        
        # Use model_dump at the boundary
        config_dict = config.model_dump()
        
        # Filter out excluded keys
        firestore_data = {
            k: v for k, v in config_dict.items() 
            if k not in exclude_keys
        }
        
        # Add metadata
        firestore_data["_updated_at"] = firestore.SERVER_TIMESTAMP
        firestore_data["_version"] = "1.0.0"
        
        # Store in Firestore
        doc_ref = self.db.collection("project_configs").document(str(config.project_id))
        doc_ref.set(firestore_data, merge=True)
        
        logger.info(f"Stored config in Firestore for project {config.project_id}")
    
    def load_from_firestore(self, project_id: int) -> Optional[ProjectConfig]:
        """Load configuration from Firestore.
        
        Args:
            project_id: Project ID to load config for
            
        Returns:
            ProjectConfig object or None if not found
        """
        doc_ref = self.db.collection("project_configs").document(str(project_id))
        doc = doc_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            # Remove metadata fields
            data.pop("_updated_at", None)
            data.pop("_version", None)
            
            try:
                config = ProjectConfig(**data)
                logger.info(f"Loaded config from Firestore for project {project_id}")
                return config
            except ValidationError as e:
                logger.error(f"Invalid config in Firestore: {e}")
                return None
        
        logger.warning(f"No Firestore config found for project {project_id}")
        return None
    
    def load_yaml_configs(self) -> Dict[str, Any]:
        """Load YAML configuration files that stay local.
        
        Returns:
            Dictionary with loaded YAML configurations
        """
        yaml_files = ["clients", "eqty", "internal_functions", "persona", "plugins"]
        configs = {}
        
        for file_name in yaml_files:
            file_path = self.config_dir / f"{file_name}.yaml"
            if file_path.exists():
                with open(file_path) as f:
                    configs[file_name] = yaml.safe_load(f)
                logger.debug(f"Loaded {file_name}.yaml")
            else:
                logger.warning(f"Config file {file_path} not found")
        
        return configs
    
    def get_permanent_token(self) -> str:
        """Get or generate permanent API token for Tenant Manager.
        
        Returns:
            JWT token for API authentication
        """
        # Check if we have a stored token
        if self.local_config.api_token:
            # TODO: Validate token expiry
            return self.local_config.api_token
        
        # Generate new permanent token
        token = get_tenant_manager_token(self.local_config.project_id)
        
        # Update local config
        self.local_config.api_token = token
        
        # Save using model_dump
        with open(self.local_config_file, "w") as f:
            json.dump(self.local_config.model_dump(), f, indent=2)
        
        return token
    
    def update_config(self, updates: Dict[str, Any], store_in_firestore: bool = True):
        """Update configuration values.
        
        Args:
            updates: Dictionary of updates to apply
            store_in_firestore: Whether to update Firestore as well
        """
        # Update local config
        for key, value in updates.items():
            if hasattr(self.local_config, key):
                setattr(self.local_config, key, value)
        
        # Save local config using model_dump
        with open(self.local_config_file, "w") as f:
            json.dump(self.local_config.model_dump(), f, indent=2)
        
        # Update Firestore if requested
        if store_in_firestore and self.local_config.project_id:
            doc_ref = self.db.collection("project_configs").document(
                str(self.local_config.project_id)
            )
            updates["_updated_at"] = firestore.SERVER_TIMESTAMP
            doc_ref.update(updates)
        
        logger.info(f"Updated config with {len(updates)} changes")