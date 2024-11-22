import yaml
import argparse
import os
from typing import Dict, Any


def get_nested_value(data: Dict[str, Any], key: str) -> Any:
    try:
        keys = key.split(".")
        value = data
        for k in keys:
            if not isinstance(value, dict):
                return None
            value = value.get(k, {})
        return value if value != {} else None
    except Exception as e:
        print(f"Error getting nested value for key {key}: {e}")
        return None


def extract_values(
    data: Dict[str, Any], section: str, mappings: Dict[str, str]
) -> Dict[str, Any]:
    extracted_data = {}
    try:
        # For secrets, we don't need to look for a section since the data is flat
        section_data = data.get(
            section, data
        )  # Fallback to full data if section not found

        if not isinstance(section_data, dict):
            print(f"Warning: Section '{section}' is not a dictionary")
            return extracted_data

        for env_var, config_key in mappings.items():
            try:
                keys = config_key.split(".")
                value = section_data
                for k in keys:
                    if not isinstance(value, dict) or k not in value:
                        value = None
                        break
                    value = value[k]
                if value is not None:
                    extracted_data[env_var] = value
                else:
                    print(f"Warning: No value found for {env_var} (key: {config_key})")
            except Exception as e:
                print(f"Error extracting value for {env_var}: {e}")

    except Exception as e:
        print(f"Error processing section {section}: {e}")

    return extracted_data


def extract_env_secrets(
    env: str, config_dir: str, secrets_dir: str
) -> Dict[str, Dict[str, Any]]:
    env_data = {}
    secrets_data = {}

    try:
        # Config files and mappings definitions remain the same...
        config_yaml_files = {
            "databases": "databases.yaml",
            "deployment": "deployment.yaml",
            "eqty": "eqty.yaml",
            "ingress": "ingress.yaml",
            "project": "project.yaml",
        }

        env_data["ENV"] = env

        # Existing mappings remain the same...
        config_mappings = {
            "databases": {
                "MONGO_DB": "mongo.db_name",
                "MONGO_HOST": "mongo.host",
                "MONGO_PORT": "mongo.port",
                "MONGO_DB_NAME": "mongo.db_name",
                "REDIS_HOST": "redis.host",
                "REDIS_PORT": "redis.port",
            },
            "ingress": {
                "API_PORT": "api_port",
                "SHARED_SSL_PEM": "shared_ssl_pem",
                "SHARED_SSL_KEY": "shared_ssl_key",
                "SHARED_SSL_CRT": "shared_ssl_crt",
                "API_SSL_PEM": "api_ssl_pem",
                "API_SSL_KEY": "api_ssl_key",
                "SSL_CA_CRT": "ssl_ca_crt",
            },
            "project": {
                "NAMESPACE": "namespace",
                "PROJECT_NAME": "name",
            },
            "deployment": {
                "GOOGLE_ARTIFACT_REGISTRY": "google.artifact_registry",
                "GOOGLE_PROJECT_ID": "google.project_id",
                "GOOGLE_NAMESPACE": "google.namespace",
                "GOOGLE_REGION": "google.region",
                "WORKERS": "scaling.workers",
            },
            "eqty": {
                "EQTY_TRUSTED_HOST_DOMAIN": "trusted_host_domain",
            },
        }

        secrets_yaml_file = "secrets.yaml"
        secret_mappings = {
            "eqty": {
                "EQTY_TRUSTED_HOST_USERNAME": "trusted_host_username",
                "EQTY_TRUSTED_HOST_PASSWORD": "trusted_host_password",
            },
        }

        # Load and extract config values
        for key, filename in config_yaml_files.items():
            filepath = os.path.join(config_dir, filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r") as file:
                        data = yaml.safe_load(file)
                        if not isinstance(data, dict):
                            print(f"Warning: Invalid YAML structure in {filename}")
                            continue
                        if key in config_mappings:
                            extracted = extract_values(data, key, config_mappings[key])
                            env_data.update(extracted)
                except yaml.YAMLError as e:
                    print(f"Error parsing YAML file {filename}: {e}")
                except Exception as e:
                    print(f"Error processing file {filename}: {e}")

        # Load secrets.yaml and parse based on secret mappings
        secrets_filepath = os.path.join(secrets_dir, secrets_yaml_file)
        if os.path.exists(secrets_filepath):
            try:
                with open(secrets_filepath, "r") as file:
                    secrets_data_raw = yaml.safe_load(file)
                    if not isinstance(secrets_data_raw, dict):
                        print("Warning: Invalid secrets.yaml structure")
                    else:
                        for section, mappings in secret_mappings.items():
                            extracted_secrets = extract_values(
                                secrets_data_raw, section, mappings
                            )
                            secrets_data.update(extracted_secrets)
            except yaml.YAMLError as e:
                print(f"Error parsing secrets.yaml: {e}")
            except Exception as e:
                print(f"Error processing secrets.yaml: {e}")

    except Exception as e:
        print(f"Error extracting configuration: {e}")

    return {"env": env_data, "secrets": secrets_data}


def flatten_dict(
    d: Dict[str, Any], parent_key: str = "", sep: str = "_"
) -> Dict[str, Any]:
    try:
        items = []
        if not isinstance(d, dict):
            print(f"Warning: Cannot flatten non-dictionary type: {type(d)}")
            return {}

        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else str(k)
            if isinstance(v, dict):
                items.extend(flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
    except Exception as e:
        print(f"Error flattening dictionary: {e}")
        return {}


def generate_env_file(env: str, output_file: str, force: bool = False) -> bool:
    try:
        config_dir = os.path.join(f"./config/{env}/app")
        secrets_dir = os.path.join(f"./secrets/{env}")

        if not os.path.exists(config_dir):
            print(f"Error: Config directory not found at {config_dir}")
            return False

        if os.path.exists(output_file) and not force:
            print(f"Skipping existing file: {output_file}")
            return False

        env_secrets_dict = extract_env_secrets(env, config_dir, secrets_dir)

        # Validate we got some data
        if not env_secrets_dict["env"] and not env_secrets_dict["secrets"]:
            print("Error: No configuration data was extracted")
            return False

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)

        with open(output_file, "w") as env_file:
            for section in ["env", "secrets"]:
                section_data = env_secrets_dict.get(section, {})
                if not section_data:
                    print(f"Warning: No data found for section '{section}'")
                    continue

                flattened_section = flatten_dict(section_data)
                for key, value in flattened_section.items():
                    if value is not None:  # Skip None values
                        env_file.write(f"{key}={value}\n")
                        print(f"Writing: {key}={value}")

        print(f"Generated file: {output_file}")
        return True

    except Exception as e:
        print(f"Error generating environment file: {e}")
        return False


def main(env, force):
    output_file = ".env"
    generate_env_file(env, output_file, force)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate .env file from YAML configuration and secrets."
    )
    parser.add_argument(
        "--env",
        type=str,
        choices=["production", "staging", "development"],
        required=True,
        help="The environment to use (production, staging, or development).",
    )
    parser.add_argument(
        "--force", action="store_true", help="Force overwrite of existing .env file."
    )
    args = parser.parse_args()

    main(args.env, args.force)
