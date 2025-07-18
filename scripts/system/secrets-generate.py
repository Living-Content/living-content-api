import argparse
import os

import yaml


def load_secrets_yaml(env):
    """Load secrets from the secrets.yaml file for the given environment."""
    secrets_file = f"./secrets/{env}/secrets.yaml"
    try:
        with open(secrets_file) as file:
            secrets = yaml.safe_load(file)
            return secrets
    except FileNotFoundError:
        print(f"Secrets file not found: {secrets_file}")
        return None


def write_secret_file(secret_dir, secret_name, secret_value):
    """Write the individual secret to a file under the specified directory."""
    if not os.path.exists(secret_dir):
        os.makedirs(secret_dir, exist_ok=True)

    secret_file = os.path.join(secret_dir, secret_name)

    # Convert non-string values to strings
    if secret_value is None:
        print(
            f"Warning: Secret {secret_name} has a None value and will not be written."
        )
        return
    elif not isinstance(secret_value, str):
        secret_value = str(secret_value)

    try:
        with open(secret_file, "w") as file:
            file.write(secret_value.strip())
        print(f"Secret written to {secret_file}")
    except OSError as e:
        print(f"Error writing secret {secret_name}: {e}")


def generate_secrets(env):
    """Generate secrets files for Docker"""
    secrets = load_secrets_yaml(env)
    if secrets is None:
        return

    # Define Docker and GKE directories
    docker_secret_dir = f"./secrets/{env}/files"

    # List to store secret names
    secret_names = []

    # Go through the secrets structure and write each secret to the directory
    for secret_category, secret_values in secrets.items():
        if isinstance(secret_values, dict):
            for secret_name, secret_value in secret_values.items():
                # Combine the category and secret name without extensions
                full_secret_name = f"{secret_category}_{secret_name}"
                secret_names.append(full_secret_name)  # Add to the secret names list
                # Write to Docker secrets directory
                write_secret_file(docker_secret_dir, full_secret_name, secret_value)
        else:
            print(f"Unexpected format for {secret_category} in secrets.yaml")

    print(f"Secrets generation completed for environment: {env}")


def main():
    parser = argparse.ArgumentParser(
        description="Process config template, copy, and concatenate YAML files."
    )
    parser.add_argument(
        "--env",
        type=str,
        required=True,
        choices=["production", "development", "staging", "all"],
        help='The environment to process. Choose from "production", "development", "staging", or "all".',
    )
    parser.add_argument(
        "--force", action="store_true", help="Force overwrite of existing files."
    )
    args = parser.parse_args()

    envs = [args.env] if args.env != "all" else ["production", "development", "staging"]

    for env in envs:
        generate_secrets(env)


if __name__ == "__main__":
    main()
