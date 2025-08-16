"""Docker Compose generation service."""

import logging
import os
from pathlib import Path
from string import Template
from typing import Dict, Any

from models.config import ProjectConfig, LocalConfig

logger = logging.getLogger(__name__)


class DockerService:
    """Service for generating Docker Compose configurations."""

    def __init__(self, project_dir: Path) -> None:
        """Initialize Docker service.

        Args:
            project_dir: Project directory path
        """
        self.project_dir = project_dir
        self.template_path = project_dir / "docker-compose.yaml.template"
        self.output_path = project_dir / "docker-compose.yaml"
        self.env_path = project_dir / ".env"

    def generate_compose(
        self, 
        project_config: ProjectConfig,
        local_config: LocalConfig,
    ) -> None:
        """Generate docker-compose.yaml from template.

        Args:
            project_config: Project configuration from Tenant Manager
            local_config: Local configuration
        """
        if not self.template_path.exists():
            raise FileNotFoundError(f"Template not found: {self.template_path}")

        # Read template
        template_content = self.template_path.read_text()
        template = Template(template_content)

        # Prepare substitution values
        substitutions = {
            "PROJECT_NAME": project_config.project_name.lower().replace(" ", "-"),
            "PROJECT_ID": str(project_config.project_id),
            "ENVIRONMENT": project_config.environment,
            "API_IMAGE": project_config.api_image,
            "MONGO_IMAGE": project_config.mongo_image,
            "REDIS_IMAGE": project_config.redis_image,
            "MONGO_DB_NAME": "livingcontent",  # Default database name
        }

        # Generate docker-compose.yaml
        compose_content = template.safe_substitute(substitutions)
        self.output_path.write_text(compose_content)
        logger.info(f"Generated docker-compose.yaml at {self.output_path}")

        # Generate .env file for docker-compose
        self._generate_env_file(substitutions)

    def _generate_env_file(self, substitutions: Dict[str, Any]) -> None:
        """Generate .env file for docker-compose.

        Args:
            substitutions: Environment variables to write
        """
        env_lines = []
        for key, value in substitutions.items():
            env_lines.append(f"{key}={value}")

        self.env_path.write_text("\n".join(env_lines) + "\n")
        logger.info(f"Generated .env file at {self.env_path}")

    def validate_compose(self) -> bool:
        """Validate the generated docker-compose.yaml.

        Returns:
            True if valid, False otherwise
        """
        if not self.output_path.exists():
            logger.error("docker-compose.yaml does not exist")
            return False

        # Check if docker-compose is available
        try:
            import subprocess
            result = subprocess.run(
                ["docker", "compose", "-f", str(self.output_path), "config"],
                capture_output=True,
                text=True,
                check=False,
            )
            
            if result.returncode != 0:
                logger.error(f"Docker Compose validation failed: {result.stderr}")
                return False
                
            logger.info("Docker Compose configuration is valid")
            return True
            
        except FileNotFoundError:
            logger.warning("Docker Compose not installed, skipping validation")
            return True

    def get_compose_services(self) -> list[str]:
        """Get list of services defined in docker-compose.yaml.

        Returns:
            List of service names
        """
        if not self.output_path.exists():
            return []

        try:
            import yaml
            with open(self.output_path, "r") as f:
                compose_config = yaml.safe_load(f)
                return list(compose_config.get("services", {}).keys())
        except Exception as e:
            logger.error(f"Failed to parse docker-compose.yaml: {e}")
            return []