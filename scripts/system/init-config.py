import os
import argparse
import re
import secrets
import string
import yaml
from uuid import uuid4
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import FoldedScalarString
import shutil
import configparser


def get_log_config(env: str):
    log_level = "WARNING" if env in ["production", "staging"] else "DEBUG"
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "{levelname} - {message} ({name} @ {asctime}) - {pathname}:{lineno}",
                "style": "{",
            },
            "access": {
                "format": "{asctime} - {message}",
                "style": "{",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            },
            "access_console": {
                "class": "logging.StreamHandler",
                "formatter": "access",
            },
            "file": {
                "class": "logging.FileHandler",
                "filename": "/living-content-api/logs/uvicorn.log",
                "formatter": "default",
                "mode": "a",
            },
            "access_file": {
                "class": "logging.FileHandler",
                "filename": "/living-content-api/logs/uvicorn_access.log",
                "formatter": "access",
                "mode": "a",
            },
        },
        "loggers": {
            "": {
                "handlers": ["console", "file"],
                "level": log_level,
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["access_console", "access_file"],
                "level": log_level,
                "propagate": False,
            },
            "gunicorn.error": {
                "handlers": ["console", "file"],
                "level": log_level,
                "propagate": False,
            },
            "gunicorn.access": {
                "handlers": ["access_console", "access_file"],
                "level": log_level,
                "propagate": False,
            },
        },
    }


def write_log_config(env, force):
    # Define the logging folder path within the environment
    logging_folder = f"./config/{env}/logging"
    logging_config_ini_path = os.path.join(logging_folder, "logging_config.ini")

    # Ensure the logging folder exists
    os.makedirs(logging_folder, exist_ok=True)

    if os.path.exists(logging_config_ini_path) and not force:
        print(f"Skipping copying existing logging config INI for environment {env}")
        return
    else:
        logging_config = get_log_config(env)

        # Write INI config for Gunicorn
        config = configparser.ConfigParser()

        # Add keys to sections
        config["loggers"] = {
            "keys": ", ".join(
                k if k else "root" for k in logging_config["loggers"].keys()
            )
        }
        config["handlers"] = {"keys": ", ".join(logging_config["handlers"].keys())}
        config["formatters"] = {"keys": ", ".join(logging_config["formatters"].keys())}

        # Add individual logger configurations
        for logger_name, logger_config in logging_config["loggers"].items():
            section_name = f"logger_{logger_name}" if logger_name else "logger_root"
            config[section_name] = {
                k: (
                    str(int(v))
                    if k == "propagate"
                    else str(v) if not isinstance(v, list) else ", ".join(v)
                )
                for k, v in logger_config.items()
            }
            if "qualname" not in config[section_name]:
                config[section_name]["qualname"] = (
                    logger_name if logger_name else "root"
                )

        # Add individual handler configurations
        for handler_name, handler_config in logging_config["handlers"].items():
            section_name = f"handler_{handler_name}"
            if handler_name in ["file", "access_file"]:
                config[section_name] = {
                    "class": handler_config["class"],
                    "formatter": handler_config["formatter"],
                    "args": f"('{handler_config['filename']}', 'a')",
                }
            else:
                config[section_name] = {k: str(v) for k, v in handler_config.items()}

        # Add individual formatter configurations
        for formatter_name, formatter_config in logging_config["formatters"].items():
            section_name = f"formatter_{formatter_name}"
            config[section_name] = {k: str(v) for k, v in formatter_config.items()}

        with open(logging_config_ini_path, "w") as f:
            config.write(f)
        print(f"Written logging config INI to {logging_config_ini_path}")


def replace_environment_variable(content, env):
    return content.replace("${ENV}", env)


def generate_password(length=16):
    """
    Generate a random password excluding certain problematic characters.
    """
    alphabet = string.ascii_letters + string.digits + string.punctuation
    bad_chars = [
        "$",
        "\\",
        "'",
        '"',
        "`",
        " ",
        ":",
        ";",
        "<",
        ">",
        "|",
        "&",
        "(",
        ")",
        "[",
        "]",
        "{",
        "}",
        "!",
        "?",
        ".",
        "+",
        "@",
        "#",
        "%",
        "^",
        "*",
        "=",
        "~",
        ",",
        "/",
    ]
    for char in bad_chars:
        alphabet = alphabet.replace(char, "")
    return "".join(secrets.choice(alphabet) for _ in range(length))


def replace_placeholders(content):
    content = re.sub(r"\$\{PASSWORD\}", lambda _: generate_password(), content)
    return re.sub(r"\$\{UUID4\}", lambda _: str(uuid4()), content)


def process_yaml_vars(env, force):
    secrets_path = f"./secrets/{env}/secrets.yaml"

    # Process the secrets file
    try:
        with open(secrets_path, "r") as secrets_file:
            content = secrets_file.read()

        # Replace password placeholders in the secrets content
        processed_content = replace_placeholders(content)

        # Write the processed content back to the same secrets file
        with open(secrets_path, "w") as output_file:
            output_file.write(processed_content)
        print(f"Processed YAML in secrets file: {secrets_path}")

    except Exception as e:
        print(f"Error processing YAML in secrets file {secrets_path}: {e}")


# Initialize YAML handler with 80-column width
yaml = YAML()
yaml.preserve_quotes = True
yaml.width = 80  # Set 80-column width for output


def process_and_append_file(file_path, output_file):
    try:
        with open(file_path, "r") as f:
            yaml_data = yaml.load(f)

        if yaml_data:
            yaml_data = fold_long_strings(yaml_data)
            with open(output_file, "a") as output:
                yaml.dump(yaml_data, output)
            print(f"Appended file: {file_path}")
        else:
            print(f"Skipped empty file: {file_path}")
    except Exception as e:
        print(f"Error processing file {file_path}: {e}")


def fold_long_strings(data, max_length=80):
    """
    Recursively process YAML content to fold long strings to max_length columns.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            data[key] = fold_long_strings(value, max_length)
    elif isinstance(data, list):
        for i in range(len(data)):
            data[i] = fold_long_strings(data[i], max_length)
    elif isinstance(data, str):
        if len(data) > max_length:
            return FoldedScalarString(data)  # Fold long strings
    return data


def copy_config_files(env, force):
    src_folder = f"./.templates/config/"
    config_folder = f"./config/{env}/app"

    if not os.path.exists(src_folder):
        print(f"Source directory {src_folder} does not exist.")
        return

    if not os.path.exists(config_folder):
        os.makedirs(config_folder)
        print(f"Created directory: {config_folder}")

    # Iterate over YAML files in the source folder
    for filename in sorted(os.listdir(src_folder)):
        if filename.endswith(".yaml"):
            src_file_path = os.path.join(src_folder, filename)
            dest_file_path = os.path.join(config_folder, filename)

            # Skip if the destination file already exists and force is not set
            if os.path.exists(dest_file_path) and not force:
                print(f"Skipping copying existing config file: {dest_file_path}")
                continue

            try:
                with open(src_file_path, "r") as src_file:
                    yaml_data = yaml.load(src_file)

                # Process long strings to fold them to 80 columns
                if yaml_data:
                    yaml_data = fold_long_strings(yaml_data)

                    with open(dest_file_path, "w") as dest_file:
                        yaml.dump(yaml_data, dest_file)
                    print(f"Processed and saved file: {dest_file_path}")
                else:
                    print(f"Skipped processing empty file: {src_file_path}")

            except Exception as e:
                print(f"Error processing file {src_file_path}: {e}")


def copy_secrets_files(env, force):
    src_file = f"./.templates/secrets.yaml"
    dest_folder = f"./secrets/{env}/"
    dest_file = f"{dest_folder}secrets.yaml"

    if not os.path.exists(src_file):
        print(f"Source file {src_file} does not exist.")
        return

    if not os.path.exists(dest_folder):
        os.makedirs(dest_folder)
        print(f"Created directory: {dest_folder}")

    if os.path.exists(dest_file) and not force:
        print(f"Skipping copying existing secrets file: {dest_file}")
        return

    try:
        shutil.copy(src_file, dest_file)
        print(f"Copied secrets file to: {dest_file}")
    except Exception as e:
        print(f"Failed to copy secrets file: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Process config template, copy, and process YAML files individually."
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
        copy_config_files(env, args.force)
        copy_secrets_files(env, args.force)
        process_yaml_vars(env, args.force)
        write_log_config(env, args.force)


if __name__ == "__main__":
    main()
