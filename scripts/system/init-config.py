import argparse
import os
import re
import secrets
import shutil
import string
from uuid import uuid4


def copy_config_files(env, force):
    # Define the source and destination directories
    source_dir = "./config/templates"
    dest_dir = f"./config/{env}"

    # Ensure the destination directory exists
    os.makedirs(dest_dir, exist_ok=True)

    # Walk through the source directory
    for root, _, files in os.walk(source_dir):
        for file in files:
            source_file = os.path.join(root, file)
            # Construct the relative path to maintain the directory structure
            relative_path = os.path.relpath(source_file, source_dir)
            dest_file = os.path.join(dest_dir, relative_path)

            # Ensure the destination subdirectory exists
            os.makedirs(os.path.dirname(dest_file), exist_ok=True)

            if os.path.exists(dest_file) and not force:
                print(f"Skipping copying existing config file: {dest_file}")
                continue
            else:
                shutil.copy2(source_file, dest_file)
                print(f"Copied {source_file} to {dest_file}")


def copy_secrets_files(env, force):
    source_dir = "./secrets/templates"
    dest_dir = f"./secrets/{env}"

    os.makedirs(dest_dir, exist_ok=True)

    for file in os.listdir(source_dir):
        source_file = os.path.join(source_dir, file)
        dest_file = os.path.join(dest_dir, file)

        if os.path.exists(dest_file) and not force:
            print(f"Skipping existing secrets file: {dest_file}")
            continue
        else:
            shutil.copy2(source_file, dest_file)
            print(f"Copied {source_file} to {dest_file}")


def process_yaml_vars(env, force):
    source_dir = f"./config/{env}"
    yaml_files = [f for f in os.listdir(source_dir) if f.endswith(".yaml")]

    for file in yaml_files:
        file_path = os.path.join(source_dir, file)

        with open(file_path) as f:
            yaml_content = f.read()

        if re.search(r"\{\{.*\}\}", yaml_content):
            # Find all variable placeholders
            variables = re.findall(r"\{\{(.*?)\}\}", yaml_content)
            replacements = {}

            for var in variables:
                if var.startswith("SECRET_"):
                    replacements[var] = generate_secret_value()
                elif var.startswith("UUID_"):
                    replacements[var] = str(uuid4())

            # Replace placeholders with generated values
            for var, value in replacements.items():
                yaml_content = yaml_content.replace(f"{{{{{var}}}}}", value)

            with open(file_path, "w") as f:
                f.write(yaml_content)

            print(f"Processed variables in {file_path}")
        else:
            print(f"No variables to process in {file_path}")


def generate_secret_value(length=32):
    return "".join(
        secrets.choice(string.ascii_letters + string.digits) for _ in range(length)
    )


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


if __name__ == "__main__":
    main()
