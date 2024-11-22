import os
import yaml
import json
import argparse
import re

from app.lib.config import ConfigSingleton


def convert_yaml_to_dict(yaml_content):
    return yaml.safe_load(yaml_content)


def load_yaml_file(file_path):
    if os.path.exists(file_path):
        print(f"Loading file: {file_path}")
        with open(file_path, "r") as yaml_file:
            yaml_content = yaml_file.read()
            return convert_yaml_to_dict(yaml_content)
    return {}


def load_all_variables(env):
    config_yaml_path = os.path.join(f"./config/{env}.yaml")

    # Load the entire config file without splitting into specific parts
    config_dict = load_yaml_file(config_yaml_path)

    return config_dict


def load_additional_variables(file_path):
    return load_yaml_file(file_path)


def format_yaml_dict(yaml_dict, indent_level):
    formatted_lines = []
    for key, value in yaml_dict.items():
        indent = " " * indent_level
        if isinstance(value, str) and "," in value:
            formatted_lines.append(f'{indent}{key}: "{value}"')
        elif isinstance(value, list):
            formatted_lines.append(f"{indent}{key}:")
            for item in value:
                formatted_lines.append(f"{indent}  - {item}")
        else:
            formatted_lines.append(f"{indent}{key}: {value}")
    return "\n".join(formatted_lines)


def replace_variables(content, config_dict):
    # Regular expression to match the ${section:variable} pattern
    variable_pattern = re.compile(r"\$\{(\w+):(\w+)\}")

    def variable_replacer(match):
        section = match.group(1)
        key = match.group(2)

        # Check if section exists in the config_dict
        if section in config_dict:
            section_dict = config_dict[section]

            # Check if the key exists in the section
            if isinstance(section_dict, dict) and key in section_dict:
                return str(section_dict[key])

        # If no match found, return the original string
        return match.group(0)

    # If there are multiple YAML documents, handle each one
    try:
        yaml_docs = list(yaml.safe_load_all(content))
        processed_docs = []
        for doc in yaml_docs:
            doc_str = yaml.dump(doc)
            processed_doc = variable_pattern.sub(variable_replacer, doc_str)
            processed_docs.append(yaml.safe_load(processed_doc))
        return yaml.dump_all(processed_docs)
    except yaml.YAMLError as exc:
        print(f"Error in YAML parsing: {exc}")
        return content


def detect_host_dirs():
    deployment_dir = "./deployment"
    return [
        d
        for d in os.listdir(deployment_dir)
        if os.path.isdir(os.path.join(deployment_dir, d))
    ]


def yaml_to_json(yaml_content):
    """Convert YAML content with multiple documents to JSON string"""
    try:
        # Load all YAML documents
        yaml_docs = list(yaml.safe_load_all(yaml_content))

        # If there are multiple documents, return a list of JSON objects
        if len(yaml_docs) > 1:
            json_output = json.dumps(yaml_docs, indent=2)
        else:
            json_output = json.dumps(yaml_docs[0], indent=2)
        return json_output
    except yaml.YAMLError as exc:
        print(f"Error in YAML parsing: {exc}")
        return None


def process_templates(env, config_dict, force):
    hosts = detect_host_dirs()

    for host in hosts:
        template_dir = f"./deployment/{host}/_templates"
        output_dir = f"./deployment/{host}/{env}"
        os.makedirs(output_dir, exist_ok=True)

        if not os.path.exists(template_dir):
            print(f"Template directory not found for host: {host}, skipping...")
            continue

        print(f"Processing templates for host: {host}")

        for filename in os.listdir(template_dir):
            if not filename.endswith(".yaml"):
                continue

            template_path = os.path.join(template_dir, filename)
            output_path = os.path.join(output_dir, filename)

            if os.path.exists(output_path) and not force:
                print(f"Skipping existing file: {output_path}")
                continue

            with open(template_path, "r") as template_file:
                content = template_file.read()

            if host.lower() == "google" and filename == "configmap.yaml":
                processed_content = create_env_configmap(env, config_dict)
            elif host.lower() == "google" and filename in [
                "managed-certificate.yaml",
                "ingress.yaml",
            ]:
                processed_content = process_special_google_case(
                    filename, content, config_dict
                )
            else:
                processed_content = replace_variables(content, config_dict)

            with open(output_path, "w") as output_file:
                output_file.write(processed_content)
            print(f"Processed file (YAML) for {host}: {output_path}")


def create_env_configmap(env, config_dict):
    """Create a ConfigMap YAML string from the config dictionary, including all keys in the 'env' section."""
    configmap = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": f"{env}-env-config"},
        "data": {},
    }

    # Fetch the 'env' section from the config dictionary
    env_config = config_dict.get("env", {})

    for key, value in env_config.items():
        if isinstance(value, list):
            # Convert list to a comma-separated string without extra quotes
            configmap["data"][key] = ",".join(value)
        else:
            # Convert non-string values to strings since ConfigMap only supports string values
            configmap["data"][key] = str(value)

    # Return the final ConfigMap as a YAML string
    return yaml.dump(configmap, default_flow_style=False)


def validate_domain(domain):
    """
    Ensure the domain is valid, does not contain a port number, and is not 'localhost'.

    Args:
        domain: String representing a domain name, possibly with port number

    Returns:
        str: Valid domain name without port number
        None: If domain is invalid
    """
    # Remove port number if present
    domain = re.sub(r":\d+$", "", domain)

    # Ensure 'localhost' and similar values are removed
    if domain.lower() in ["localhost", "localhost.localdomain"]:
        print(f"Invalid domain (localhost): {domain}")
        return None

    # RFC 1123 compliant domain validation
    pattern = (
        r"^(?!-)"  # No leading hyphen
        r"(?!.*--)"  # No consecutive hyphens
        r"(?:[a-zA-Z0-9-]{1,63}"  # Label content: alphanumeric + single hyphens
        r"(?<!-))"  # No trailing hyphen for each label
        r"(?:\."  # Dot separator
        r"(?!-)"  # No leading hyphen in next label
        r"(?!.*--)"  # No consecutive hyphens in next label
        r"(?:[a-zA-Z0-9-]{1,63}"
        r"(?<!-)))*"  # Repeat for all labels
        r"\.?"  # Optional trailing dot
        r"(?!.*[0-9]$)"  # TLD must not be all numeric
        r"[a-zA-Z0-9]+"  # TLD content
        r"$"
    )

    if len(domain) > 253 or not re.match(pattern, domain, re.IGNORECASE):
        print(f"Invalid domain: {domain}")
        return None

    return domain


def process_managed_certificate(content, config_dict):
    # Parse the YAML content
    yaml_content = yaml.safe_load(content)

    env_config = config_dict["env"]
    domains = set()

    # Add domains from configuration
    domains.add(env_config.get("DOMAIN_NAME", ""))
    domains.add(env_config.get("API_HOST_URL", "").replace("https://", ""))
    domains.update(env_config.get("ALLOWED_ORIGINS", []))

    # Process domains: remove 'https://', filter out empty strings, validate domains
    domains = {
        validate_domain(domain.replace("https://", "")) for domain in domains if domain
    }
    # Remove any invalid (None) domains
    domains = {domain for domain in domains if domain}

    # Update the domains in the YAML structure
    yaml_content["spec"]["domains"] = sorted(domains)

    # Convert back to YAML
    return yaml.dump(yaml_content, default_flow_style=False)


def get_absolute_path(env_config):
    """Get API root path, default to '/' if empty or not provided."""
    path = env_config.get("API_ROOT_PATH", "/")
    # Ensure the path is '/' if it's an empty string
    return path if path.strip() else "/"


def process_ingress(content, config_dict):
    yaml_content = yaml.safe_load(content)
    env_config = config_dict["env"]
    hosts = set()

    # Add hosts from the configuration
    hosts.add(env_config.get("DOMAIN_NAME", ""))
    hosts.add(env_config.get("API_HOST_URL", "").replace("https://", ""))
    hosts.update(env_config.get("ALLOWED_ORIGINS", []))

    # Sanitize hosts (remove 'https://', ports, and invalid hosts)
    hosts = {validate_domain(host.replace("https://", "")) for host in hosts if host}
    hosts = {host for host in hosts if host}  # Remove None values

    # Create rules
    rules = []
    for host in sorted(hosts):
        rule = {
            "host": host,
            "http": {
                "paths": [
                    {
                        "path": get_absolute_path(env_config),
                        "pathType": "Prefix",
                        "backend": {
                            "service": {
                                "name": "api",
                                "port": {"number": env_config.get("API_PORT", 8000)},
                            }
                        },
                    }
                ]
            },
        }
        rules.append(rule)

    yaml_content["spec"]["rules"] = rules

    return yaml.dump(yaml_content, default_flow_style=False)


def process_special_google_case(filename, content, config_dict):
    # First, process all variables in the content
    processed_content = replace_variables(content, config_dict)

    if filename == "managed-certificate.yaml":
        processed_content = process_managed_certificate(processed_content, config_dict)
    elif filename == "ingress.yaml":
        processed_content = process_ingress(processed_content, config_dict)

    # Print final content to verify

    return processed_content  # Return processed content for other files


async def main(env, force):
    envs = [env] if env != "all" else ["production", "staging", "development"]

    config = await ConfigSingleton.initialize()

    for env in envs:
        print(f"Processing environment: {env}")
        process_templates(env, config, force)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process deployment templates with environment variables."
    )
    parser.add_argument(
        "--env",
        type=str,
        choices=["production", "staging", "all", "development"],
        required=True,
        help="The environment to source the YAML files for.",
    )
    parser.add_argument(
        "--force", action="store_true", help="Force overwrite of existing files."
    )
    args = parser.parse_args()

    main(args.env, args.force)
