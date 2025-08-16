"""Configuration data models using Pydantic."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ResourceSpec(BaseModel):
    """Resource specifications for a container."""
    cpu: str
    memory: str
    storage: Optional[Dict[str, Any]] = None


class AppConfig(BaseModel):
    """Configuration for an application component (api, mongo, redis)."""
    replicas: int = 1
    requests: Optional[ResourceSpec] = None
    limits: Optional[ResourceSpec] = None
    autoscaling: Optional[Dict[str, Any]] = None
    volume_claim_templates: List[Dict[str, Any]] = Field(default_factory=list)
    persistent_volume_claims: List[Dict[str, Any]] = Field(default_factory=list)


class ProjectConfig(BaseModel):
    """Complete project configuration from Tenant Manager."""
    project_id: int
    project_name: str
    environment: str
    cluster_name: str
    api_image: str
    mongo_image: str
    redis_image: str
    front_end_url: str = ""
    apps: Dict[str, AppConfig] = Field(default_factory=dict)
    tenant_manager_url: Optional[str] = None
    
    class Config:
        """Pydantic config."""
        validate_assignment = True


class LocalConfig(BaseModel):
    """Local configuration stored in .lco-api.json."""
    project_id: int
    project_name: str
    environment: str
    gcp_project_id: str = "living-content"
    tenant_manager_url: Optional[str] = None
    api_token: Optional[str] = None
    
    class Config:
        """Pydantic config."""
        validate_assignment = True


class SSLConfig(BaseModel):
    """SSL certificate configuration for internal container communication."""
    ca_cert_path: str = ".ssl/ca/ca.crt"
    ca_key_path: str = ".ssl/ca/ca.key"
    shared_cert_path: str = ".ssl/shared/shared.crt"
    shared_key_path: str = ".ssl/shared/shared.key"
    shared_pem_path: str = ".ssl/shared/shared.pem"
    validity_days: int = 365
    country: str = "US"
    state: str = "California"
    locality: str = "San Francisco"
    organization: str = "Living Content"
    common_name: str = "*.living-content.local"


class SSLPaths(BaseModel):
    """Paths to generated SSL certificates."""
    ca_cert: str
    ca_key: str
    shared_cert: str
    shared_key: str
    shared_pem: str