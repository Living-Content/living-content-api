import yaml
import subprocess
import os
import glob
import argparse
from dotenv import load_dotenv


# Load environment variables from the .env file located in the current directory
def load_environment_variables():
    # Get the current working directory (from where the script is executed)
    working_directory = os.getcwd()
    # Build the path to the .env file in the current working directory
    dotenv_path = os.path.join(working_directory, ".env")

    # Load the .env file
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
        print(f"Loaded environment variables from {dotenv_path}")
    else:
        print(f"No .env file found at {dotenv_path}")


def get_gke_cluster_info():
    try:
        # Get current cluster details using gcloud command
        cluster_info = subprocess.run(
            ["gcloud", "container", "clusters", "list"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        print("Current GKE Clusters:\n", cluster_info)

        # Get current kubectl context details
        kubectl_context = subprocess.run(
            ["kubectl", "config", "current-context"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        print(f"Current kubectl context: {kubectl_context}")

        # Get cluster details in the current kubectl context
        cluster_details = subprocess.run(
            ["kubectl", "cluster-info"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        print("Cluster info:\n", cluster_details)

    except subprocess.CalledProcessError as e:
        print(f"Error retrieving GKE or kubectl info: {e}")


def generate_grouped_kubernetes_secret(
    secret_name, secrets_data, namespace=None, force=False
):
    # Check if the secret already exists
    check_command = f"kubectl get secret {secret_name}"
    if namespace:
        check_command += f" --namespace {namespace}"

    result = subprocess.run(check_command, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        if force:
            print(f"Secret '{secret_name}' already exists. Forcing overwrite.")
            delete_command = f"kubectl delete secret {secret_name}"
            if namespace:
                delete_command += f" --namespace {namespace}"
            subprocess.run(delete_command, shell=True, check=True)
        else:
            print(
                f"Secret '{secret_name}' already exists in namespace '{namespace or 'default'}'. Skipping creation."
            )
            return

    # Build the kubectl command to create the secret with multiple keys
    kubectl_command = f"kubectl create secret generic {secret_name}"

    # Add each sub-key to the secret
    for key, value in secrets_data.items():
        kubectl_command += f" --from-literal={key}={value}"

    if namespace:
        kubectl_command += f" --namespace {namespace}"

    try:
        # Execute the kubectl command
        subprocess.run(kubectl_command, shell=True, check=True)
        print(
            f"Secret '{secret_name}' created successfully in namespace '{namespace or 'default'}'."
        )
    except subprocess.CalledProcessError as e:
        print(f"Failed to create secret '{secret_name}': {e}")


def generate_secret_from_file(secret_name, file_paths, namespace=None, force=False):
    # Check if the secret already exists
    check_command = f"kubectl get secret {secret_name}"
    if namespace:
        check_command += f" --namespace {namespace}"

    result = subprocess.run(check_command, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        if force:
            print(f"Secret '{secret_name}' already exists. Forcing overwrite.")
            delete_command = f"kubectl delete secret {secret_name}"
            if namespace:
                delete_command += f" --namespace {namespace}"
            subprocess.run(delete_command, shell=True, check=True)
        else:
            print(
                f"Secret '{secret_name}' already exists in namespace '{namespace or 'default'}'. Skipping creation."
            )
            return

    # Build the kubectl command to create the secret with SSL files
    kubectl_command = f"kubectl create secret generic {secret_name}"

    for file_path in file_paths:
        file_name = os.path.basename(file_path)
        kubectl_command += f" --from-file={file_name}={file_path}"

    if namespace:
        kubectl_command += f" --namespace {namespace}"

    try:
        # Execute the kubectl command
        subprocess.run(kubectl_command, shell=True, check=True)
        print(
            f"Secret '{secret_name}' created successfully in namespace '{namespace or 'default'}'."
        )
    except subprocess.CalledProcessError as e:
        print(f"Failed to create secret '{secret_name}': {e}")


def parse_and_generate_grouped_secrets(data, namespace=None, force=False):
    # Parse the YAML-like structure
    parsed_data = yaml.safe_load(data)

    # Get the project name from the environment variable
    project_name = os.getenv("PROJECT_NAME", "")

    if not project_name:
        print("Error: PROJECT_NAME environment variable is not set.")
        return

    for primary_key, sub_keys in parsed_data.items():
        secret_data = {}

        for sub_key, value in sub_keys.items():
            # Replace placeholders like ${PASSWORD} with environment variables
            if (
                isinstance(value, str)
                and value.startswith("${")
                and value.endswith("}")
            ):
                env_var = value[2:-1]
                secret_value = os.getenv(env_var, "")
            else:
                # Ensure the value is a string
                secret_value = str(value or "")

            if secret_value:
                # Add the parent key prefix to each sub-key (e.g., redis_password)
                full_key = f"{primary_key}_{sub_key}"
                secret_data[full_key] = secret_value

        if secret_data:
            secret_name = f"{primary_key}"
            generate_grouped_kubernetes_secret(
                secret_name, secret_data, namespace, force
            )
        else:
            print(
                f"Skipping secret creation for '{primary_key}' as no valid values are provided."
            )


def handle_api_config(namespace=None, force=False):
    # Retrieve the environment variable
    env = os.getenv("ENV")
    if not env:
        raise ValueError("The 'ENV' environment variable is not set.")

    # Create the file pattern
    pattern = f"./config/{env}/app/*.yaml"

    # Use glob to find all matching YAML files
    api_config_files = glob.glob(pattern)

    # Check if any YAML files were found
    if not api_config_files:
        raise FileNotFoundError(f"No YAML files found in the directory: {pattern}")

    # Call the generate_secret_from_file function with the list of files
    generate_secret_from_file("api-config-app", api_config_files, namespace, force)


def handle_api_logging_config(namespace=None, force=False):
    env = os.getenv("ENV")
    api_logging_config_files = [f"./config/{env}/logging/logging_config.ini"]

    generate_secret_from_file(
        "api-config-logging", api_logging_config_files, namespace, force
    )


def handle_ssl_secrets(namespace=None, force=False):
    # SSL files for CA
    ca_files = ["./.ssl/ca/ca.key", "./.ssl/ca/ca.crt"]
    generate_secret_from_file("ssl-ca", ca_files, namespace, force)

    # SSL files for API
    env = os.getenv("ENV")
    api_files = [f"./.ssl/{env}/api/api.key", f"./.ssl/{env}/api/api.pem"]
    generate_secret_from_file("ssl-api", api_files, namespace, force)

    # SSL files for shared
    shared_files = [
        f"./.ssl/{env}/shared/shared.key",
        f"./.ssl/{env}/shared/shared.pem",
        f"./.ssl/{env}/shared/shared.crt",
    ]
    generate_secret_from_file("ssl-shared", shared_files, namespace, force)


def main():
    # Load the environment variables from .env file
    load_environment_variables()

    # Define argument parser for CLI usage
    parser = argparse.ArgumentParser(
        description="Generate Kubernetes secrets from a YAML file."
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        help="Path to the YAML file containing secret configurations.",
    )
    parser.add_argument(
        "--namespace",
        help="Kubernetes namespace to create the secrets in.",
        default=None,
    )
    parser.add_argument(
        "--force",
        help="Force secret overwriting if it already exists.",
        action="store_true",
    )

    # Parse the arguments
    args = parser.parse_args()

    # If no namespace is provided, use the 'project_name' from the environment
    if not args.namespace:
        args.namespace = os.getenv("project_name")
        if not args.namespace:
            print(
                "Error: No namespace provided and 'project_name' environment variable is not set."
            )
            return

    if args.input_file:
        # Read the input file
        try:
            with open(args.input_file, "r") as file:
                data = file.read()
                # Call the grouped secret generation function with namespace and force flag
                parse_and_generate_grouped_secrets(data, args.namespace, args.force)
                # Handle SSL secrets
                handle_ssl_secrets(args.namespace, args.force)
                # Handle API config secrets
                handle_api_config(args.namespace, args.force)
                handle_api_logging_config(args.namespace, args.force)
        except FileNotFoundError:
            print(f"Error: File '{args.input_file}' not found.")
        except Exception as e:
            print(f"An error occurred: {e}")
    else:
        # No input file provided: display GKE configuration info and usage instructions
        print(
            "No input file provided. Here's information about your current GKE configuration:"
        )
        get_gke_cluster_info()
        print("\nInstructions to use this script:")
        print("1. Create a YAML file with your secret configurations in the format:\n")
        print(
            """
aws:
  account_id: "your_account_id"
  access_key_id: "your_access_key"
  secret_access_key: "your_secret_key"

mongo:
  root_username: "root"
  root_password: "your_root_password"
  rw_username: "rw_user"
  rw_password: "your_rw_password"

redis:
  password: "your_redis_password"
"""
        )
        print("2. Run the script by specifying the YAML file path, like so:")
        print("   python generate_k8s_secrets.py /path/to/your/file.yaml")
        print("   You can also specify a Kubernetes namespace using --namespace.")
        print("   To force overwriting of secrets, add the --force option.")


if __name__ == "__main__":
    main()
