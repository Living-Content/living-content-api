import os
import sys
import argparse
import logging
import subprocess
import signal
import ipaddress
import yaml

from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

import psutil
from cryptography import x509
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PrivateFormat,
    NoEncryption,
)
from cryptography.x509.oid import NameOID

DEFAULT_TIMEOUT = 20
LOG_FILE = "lc.log"


# Load environment variables from .env file
def load_environment():
    """
    Load environment variables from .env file in the current working directory.
    """
    current_directory = os.getcwd()
    env_path = os.path.join(current_directory, ".env")

    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path)
        logger.debug(f"Loaded .env file from {env_path}")
    else:
        logger.warning(f"No .env file found in {current_directory}")


logger = logging.getLogger(__name__)


def initialize_logging(args):
    """
    Initialize logging based on command-line arguments.
    """
    # Clear existing handlers
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    handlers = []

    if args.log:
        # Add file handler
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        handlers.append(file_handler)

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    handlers.append(console_handler)

    # Set logging level based on verbose flag
    logging_level = logging.DEBUG if args.verbose else logging.INFO

    logging.basicConfig(level=logging_level, handlers=handlers)

    global logger
    logger = logging.getLogger(__name__)


def parse_env(args_env):
    """
    Parse the environment from arguments or .env file, fail if not set.

    :param args_env: The environment argument.
    :return: The environment string.
    """
    if args_env:
        return args_env

    env = os.getenv("ENV")
    if env:
        return env

    print(
        "Error: Environment not set. Please use --env flag or run 'lc.sh env:set <environment>'"
    )
    sys.exit(1)


def run_command(
    command,
    timeout=DEFAULT_TIMEOUT,
    env_vars=None,
    verbose=False,
    force=False,
    nocache=False,
):
    """
    Execute a shell command with optional flags and environment variables.

    :param command: The command to run.
    :param timeout: The timeout duration for the command.
    :param env_vars: A dictionary of environment variables to set.
    :param verbose: If True, log command output at DEBUG level.
    :param force: If True, add --force flag to the command.
    :param nocache: If True, add --no-cache flag to the command.
    """
    flags = []
    if force:
        flags.append("--force")
    if nocache:
        flags.append("--no-cache")

    command_with_flags = f"{command} {' '.join(flags)}"
    logger.debug(f"Running command: {command_with_flags}")

    # Prepare the environment variables
    process_env = os.environ.copy()
    if env_vars:
        process_env.update(env_vars)

    process = subprocess.Popen(
        command_with_flags,
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
        universal_newlines=True,
        env=process_env,
    )

    try:
        for line in process.stdout:
            line = line.strip()
            logger.debug(line)
        process.wait(timeout=timeout)
        if process.returncode != 0:
            stderr = process.stderr.read().strip()
            logger.error(stderr)
            raise subprocess.CalledProcessError(process.returncode, command_with_flags)
    except subprocess.TimeoutExpired:
        error_msg = f"Command '{command_with_flags}' timed out after {timeout} seconds."
        logger.error(error_msg)
        proc = psutil.Process(process.pid)
        for proc_child in proc.children(recursive=True):
            proc_child.send_signal(signal.SIGTERM)
        proc.send_signal(signal.SIGTERM)
        _, _ = process.communicate()
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc = psutil.Process(process.pid)
            for proc_child in proc.children(recursive=True):
                proc_child.kill()
            proc.kill()
            stdout, stderr = process.communicate()
        logger.error(stdout)
        logger.error(stderr)
        raise subprocess.CalledProcessError(124, command_with_flags)


# Environment and dependency management
def install_dependencies(verbose=False):
    """
    Install project dependencies.

    :param verbose: If True, enable verbose output.
    """
    eqty_trusted_host_domain = os.getenv("EQTY_TRUSTED_HOST_DOMAIN")
    eqty_trusted_host_password = os.getenv("EQTY_TRUSTED_HOST_PASSWORD")
    eqty_trusted_host_username = os.getenv("EQTY_TRUSTED_HOST_USERNAME")
    run_command(
        f"venv/bin/pip install --no-cache-dir -r ./requirements/requirements.txt --extra-index-url http://{eqty_trusted_host_username}:{eqty_trusted_host_password}@{eqty_trusted_host_domain}/simple/ --trusted-host {eqty_trusted_host_domain}",
        60,
        verbose=verbose,
    )


def venv_create(verbose=False):
    """
    Create a virtual environment for the project.

    :param verbose: If True, enable verbose output.
    """
    venv_path = Path("venv")
    if venv_path.exists():
        logger.info("Virtual environment already exists.")
        return

    try:
        import venv

        venv.create("venv", with_pip=True)
        logger.info(
            "Virtual environment created successfully. Run 'source venv/bin/activate' to activate."
        )
    except Exception as e:
        logger.error(f"Error creating virtual environment: {e}")
        sys.exit(1)


def init_config(env, force=False, verbose=False):
    """
    Initialize configuration for the specified environment.

    :param env: The environment to use.
    :param force: If True, force the operation.
    :param verbose: If True, enable verbose output.
    """
    run_command(
        f"python ./scripts/system/init-config.py --env={env}",
        env_vars={"ENV": env},
        verbose=verbose,
        force=force,
    )


def init_deployment(env, force=False, verbose=False):
    """
    Initialize deployment for the specified environment.

    :param env: The environment to use.
    :param force: If True, force the operation.
    :param verbose: If True, enable verbose output.
    """
    run_command(
        f"python ./scripts/system/init-deployment.py --env={env}",
        env_vars={"ENV": env},
        verbose=verbose,
        force=force,
    )


def env_generate(env, force=False, verbose=False):
    """
    Generate environment files for the specified environment.

    :param env: The environment to use.
    :param force: If True, force the operation.
    :param verbose: If True, enable verbose output.
    """
    # Run the command to generate the environment
    run_command(
        f"python ./scripts/system/env-generate.py --env={env}",
        env_vars={"ENV": env},
        verbose=verbose,
        force=force,
    )

    # Provide instructions to load .env into the current shell
    logger.info(
        "\n\nTo load these variables into your current shell session, run the following command:\n"
        "> eval \"$(dotenv -f .env list | sort | sed 's/^/export /')\"\n\n"
    )

    logger.debug("Pulling down docker volumes to allow rebuild.")
    run_command("docker-compose down --volumes")


def env_set(env, force=True, verbose=False):
    """
    Set up the environment by generating config and environment files.

    :param env: The environment to use.
    :param force: If True, force the operation.
    :param verbose: If True, enable verbose output.
    """
    env_generate(env, force=True, verbose=verbose)


# Docker management
def docker_build(env, verbose=False, nocache=False, service=None, cleanup=True):
    """
    Build Docker containers for the specified environment and apply tagging.
    Optionally cleans up dangling images after the build.

    :param env: The environment to use (e.g., development, staging, production).
    :param verbose: If True, enable verbose output.
    :param nocache: If True, disable Docker cache.
    :param service: Name of the service to build (None means all services).
    :param cleanup: If True, cleans up dangling images after the build.
    """
    # Fetch the project name and Google Artifact Registry details from environment variables
    project_name = os.getenv("PROJECT_NAME")
    namespace = os.getenv("NAMESPACE")
    google_namespace = os.getenv("GOOGLE_NAMESPACE")
    google_artifact_registry = os.getenv("GOOGLE_ARTIFACT_REGISTRY")
    google_project_id = os.getenv("GOOGLE_PROJECT_ID")

    # Define the default services if no specific service is provided
    all_services = [
        "api",
        "mongo",
        "redis",
    ]
    services = [service] if service else all_services

    compose_file = "docker-compose.yaml"

    # Docker Compose build command
    command_parts = ["docker", "compose", "-f", compose_file, "build"]

    if nocache:
        command_parts.append("--no-cache")

    # Add specific service to build command if provided, otherwise it will build all services
    if service:
        command_parts.append(service)

    command = " ".join(command_parts)

    # Build the images
    env_vars = {"ENV": env}
    run_command(command, 60, env_vars=env_vars, verbose=verbose)

    # Tagging the images
    for service in services:  # Now it loops over all services or the specified one
        # Determine the correct tag based on the environment
        if env == "development":
            # Local development tag structure: {namespace}-{project_name}-{service}:{env}
            tag = f"{namespace}-{project_name}-{service}:{env}"
        else:  # For staging and production
            if google_artifact_registry and google_project_id and google_namespace:
                # {google_artifact_registry}/{google_project_id}/{repository}/{service}:{env}
                tag = (
                    f"{google_artifact_registry}/{google_project_id}/"
                    f"{google_namespace}/{service}:{env}"
                )
            else:
                raise ValueError(
                    "Google Artifact Registry, project id, and a Google namespace are required for staging and production environments."
                )

        # Tag the image (assuming the built image follows default Docker Compose naming)
        original_image = f"{namespace}-{project_name}-{service.split('-')[-1]}:{env}"

        # Tag the image according to Google Artifact Registry naming conventions
        run_command(
            f"docker tag {original_image} {tag}", env_vars=env_vars, verbose=verbose
        )
        logger.info(f"Tagged {original_image} as {tag}")

        # Push the image to Google Artifact Registry if not in development
        if env != "development":
            run_command(f"docker push {tag}", env_vars=env_vars, verbose=verbose)

    # Clean up dangling images
    if cleanup:
        run_command("docker image prune -f", verbose=verbose)
        logger.info("Cleaned up dangling images")


def docker_rebuild(env, verbose=False, nocache=False):
    """
    Rebuild Docker containers for the specified environment.

    :param env: The environment to use.
    :param verbose: If True, enable verbose output.
    :param nocache: If True, disable Docker cache.
    """
    docker_down(verbose=verbose)
    docker_build(env, verbose=verbose, nocache=nocache)
    docker_up(env, verbose=verbose)


def docker_up(env, verbose=False):
    """
    Start Docker containers for the specified environment.

    :param env: The environment to use.
    :param verbose: If True, enable verbose output.
    """
    compose_file = "docker-compose.yaml"

    command_parts = ["docker", "compose"]

    command_parts.extend(["-f", compose_file])

    command_parts.extend(["up", "-d", "--no-build"])

    command = " ".join(command_parts)

    env_vars = {
        "ENV": env,
        "NAMESPACE": os.getenv("NAMESPACE"),
        "PROJECT_NAME": os.getenv("PROJECT_NAME"),
    }

    run_command(command, env_vars=env_vars, verbose=verbose)


def docker_down(verbose=False):
    """
    Stop Docker containers.

    :param verbose: If True, enable verbose output.
    """
    run_command("docker compose down", env_vars=None, verbose=verbose)


def docker_view_logs(verbose=False):
    """
    View Docker logs.

    :param verbose: If True, enable verbose output.
    """
    run_command("docker compose logs -f", env_vars=None, verbose=verbose)


def load_allowed_origins(env):
    config_file = Path(f"./config/{env}/app/ingress.yaml")
    with open(config_file, "r") as file:
        config = yaml.safe_load(file)
    allowed_origins = config.get("ingress", {}).get("allowed_origins", [])

    # Clean up and ensure uniqueness
    cleaned_origins = set()
    for origin in allowed_origins:
        parsed_uri = urlparse(origin)
        hostname = parsed_uri.hostname
        if hostname:
            cleaned_origins.add(hostname)

    return list(cleaned_origins)


def cert_generate(
    cert_dir,
    common_name,
    verbose=False,
    force=False,
    env=None,
):
    """
    Generate SSL certificate and key for the specified common name.

    :param cert_dir: Directory to store certificates.
    :param common_name: Common name for the certificate.
    :param verbose: If True, enable verbose output.
    :param force: If True, force the operation, overwriting existing files.
    :param env: Environment name for loading allowed origins (used only for 'api').
    """
    logger.info("Starting certificate generation process")

    if not env:
        warning_msg = "You must provide an environment to generate SSL certificates."
        logger.warning(warning_msg)
        return

    cert_dir = Path("./.ssl")

    ca_cert_path = cert_dir / "ca/ca.crt"
    ca_key_path = cert_dir / "ca/ca.key"
    server_key_path = cert_dir / f"{env}/{common_name}/{common_name}.key"
    server_cert_path = cert_dir / f"{env}/{common_name}/{common_name}.crt"
    server_pem_path = cert_dir / f"{env}/{common_name}/{common_name}.pem"

    mongo_host = os.getenv("MONGO_HOST")
    redis_host = os.getenv("REDIS_HOST")
    project_name = os.getenv("PROJECT_NAME")

    # Ensure all directories exist
    for path in [ca_cert_path.parent, server_key_path.parent]:
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory {path}")

    if (
        server_cert_path.exists()
        or server_key_path.exists()
        or server_pem_path.exists()
    ) and not force:
        warning_msg = f"SSL certificate or key already exists at {server_cert_path} or {server_key_path}. Generation skipped."
        logger.warning(warning_msg)
        return

    if not ca_cert_path.exists() or not ca_key_path.exists():
        # Generate CA key and certificate
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
        ca_subject = x509.Name(
            [
                x509.NameAttribute(
                    NameOID.COMMON_NAME, f"Living Content: {project_name} ({env}) CA"
                )
            ]
        )
        ca_cert = (
            x509.CertificateBuilder()
            .subject_name(ca_subject)
            .issuer_name(ca_subject)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3650))
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=None), critical=True
            )
            .add_extension(
                x509.KeyUsage(
                    key_cert_sign=True,
                    crl_sign=True,
                    digital_signature=False,
                    key_encipherment=False,
                    content_commitment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .sign(ca_key, hashes.SHA256())
        )

        with open(ca_key_path, "wb") as f:
            f.write(
                ca_key.private_bytes(
                    Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()
                )
            )
        with open(ca_cert_path, "wb") as f:
            f.write(ca_cert.public_bytes(Encoding.PEM))

        logger.debug(
            f"Generated CA certificate and key at {ca_cert_path} and {ca_key_path}"
        )
    else:
        # Load existing CA key and certificate
        with open(ca_key_path, "rb") as f:
            ca_key = serialization.load_pem_private_key(f.read(), password=None)
        with open(ca_cert_path, "rb") as f:
            ca_cert = x509.load_pem_x509_certificate(f.read())

        logger.debug(f"Loaded existing CA certificate from {ca_cert_path}")

    # Construct SAN (Subject Alternative Names)
    san_names = [
        x509.DNSName(common_name),  # Service name
    ]

    if common_name == "shared":
        san_names.extend(
            [
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                x509.DNSName(mongo_host),
                x509.DNSName(redis_host),
            ]
        )

    allowed_origins = load_allowed_origins(env)

    if isinstance(allowed_origins, str):
        allowed_origins = [allowed_origins]

    for origin in allowed_origins:
        san_names.append(x509.DNSName(origin))

    san = x509.SubjectAlternativeName(san_names)

    # Generate and sign the server certificate and key, and create combined file
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server_subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Los Angeles"),
            x509.NameAttribute(
                NameOID.ORGANIZATION_NAME, f"Living Content: {project_name}"
            ),
            x509.NameAttribute(
                NameOID.ORGANIZATIONAL_UNIT_NAME, f"{project_name}: {env}"
            ),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )
    server_cert = (
        x509.CertificateBuilder()
        .subject_name(server_subject)
        .issuer_name(ca_cert.subject)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                key_cert_sign=False,
                crl_sign=False,
                digital_signature=True,
                key_encipherment=True,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage(
                [
                    x509.ExtendedKeyUsageOID.SERVER_AUTH,
                    x509.ExtendedKeyUsageOID.CLIENT_AUTH,
                ]
            ),
            critical=True,
        )
        .add_extension(san, critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    with open(server_key_path, "wb") as f:
        f.write(
            server_key.private_bytes(
                Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()
            )
        )
    with open(server_cert_path, "wb") as f:
        f.write(server_cert.public_bytes(Encoding.PEM))
    with open(server_pem_path, "wb") as f:
        f.write(
            server_cert.public_bytes(Encoding.PEM)
            + server_key.private_bytes(
                Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()
            )
        )

    logger.debug(f"Generated server key at {server_key_path}")
    logger.debug(f"Generated server certificate at {server_cert_path}")
    logger.debug(f"Generated combined server certificate and key at {server_pem_path}")


def certs_generate_all(env=None, force=False, verbose=False):
    """
    Generate SSL certificates for all environments.

    :param env: Environment name for loading allowed origins (used only for 'api').
    :param force: If True, force the operation, overwriting existing files.
    :param verbose: If True, enable verbose output.
    """

    environments = ["development", "staging", "production"]

    if env == "all":
        selected_envs = environments
    else:
        selected_envs = [env] if env else environments

    for environment in selected_envs:
        cert_generate(
            Path(f"./.ssl/{environment}/api"),
            "api",
            force=force,
            verbose=verbose,
            env=environment,
        )
        cert_generate(
            Path(f"./.ssl/{environment}/shared"),
            "shared",
            force=force,
            verbose=verbose,
            env=environment,
        )

    instructions = """
To add the CA certificate to your trusted store, follow the instructions below:

macOS:
1. Open Keychain Access.
2. Drag and drop the CA certificate file into the "System" keychain under "Certificates".
3. Right-click the CA certificate and select "Get Info".
4. Expand the "Trust" section and set "When using this certificate" to "Always Trust".
5. Close the dialog. You may need to enter your password to confirm the changes.

Windows:
1. Press Win + R, type "mmc" and press Enter.
2. Go to File > Add/Remove Snap-in.
3. Select "Certificates" and click "Add".
4. Choose "Computer account" and click "Next", then "Finish".
5. In the MMC console, expand "Certificates (Local Computer)" and right-click "Trusted Root Certification Authorities".
6. Select "All Tasks" > "Import".
7. Follow the wizard to import the CA certificate file.
8. Complete the wizard to add the certificate to the trusted store.

Linux:
Refer to your distribution's documentation for adding trusted certificates.
"""
    print(instructions)


def secrets_generate(env, force=False, verbose=False):
    """
    Generate secrets files for the specified environment.

    :param env: The environment to use.
    :param force: If True, force the operation.
    :param verbose: If True, enable verbose output.
    """
    run_command(
        f"python ./scripts/system/secrets-generate.py --env={env}",
        env_vars={"ENV": env},
        verbose=verbose,
        force=force,
    )


# Initialize everything
def init_all(env, force=False, verbose=False):
    """
    Initialize the complete setup including dependencies, configurations, certificates, and Docker.

    :param env: The environment to use.
    :param verbose: If True, enable verbose output.
    :param nocache: If True, disable Docker cache.
    """
    install_dependencies(verbose=verbose)
    init_config("all", force=force, verbose=verbose)


# Log cleaning
def clean_log(verbose=False):
    """
    Clean up log file.

    :param verbose: If True, enable verbose output.
    """
    try:
        os.remove(LOG_FILE)
        logger.info(f"{LOG_FILE} removed successfully.")
    except FileNotFoundError:
        logger.info(f"{LOG_FILE} not found.")
    except Exception as e:
        logger.error(f"Error removing {LOG_FILE}: {e}")


# Main function
def main():
    """
    Main function to parse arguments and execute the corresponding commands.
    """
    parser = argparse.ArgumentParser(
        description="Manage various tasks for the project."
    )
    parser.add_argument("--log", action="store_true", help="Enable logging to a file")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--force", action="store_true", help="Force the operation")
    parser.add_argument("--nocache", action="store_true", help="Disable cache")
    parser.add_argument("--env", type=str, help="Environment to use (overrides .env)")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    subcommands = {
        "venv:create": venv_create,
        "install:dependencies": install_dependencies,
        "ssl:generate": certs_generate_all,
        "docker:build": docker_build,
        "docker:up": docker_up,
        "docker:down": docker_down,
        "docker:logs": docker_view_logs,
        "docker:rebuild": docker_rebuild,
        "env:generate": env_generate,
        "env:set": env_set,
        "init:all": init_all,
        "init:config": init_config,
        "init:deployment": init_deployment,
        "log:clean": clean_log,
        "secrets:generate": secrets_generate,
    }

    for cmd in subcommands:
        subparser = subparsers.add_parser(cmd, help=f"{cmd} command")
        subparser.add_argument(
            "--env", type=str, help="Environment to use (overrides .env)"
        )
        subparser.add_argument(
            "--force", action="store_true", help="Force the operation"
        )
        subparser.add_argument("--nocache", action="store_true", help="Disable cache")
        subparser.add_argument(
            "--verbose", action="store_true", help="Enable verbose output"
        )
        subparser.add_argument(
            "--log", action="store_true", help="Enable logging to a file"
        )

        # If the command is 'docker:build', add the '--service' argument
        if cmd == "docker:build":
            subparser.add_argument(
                "--service", type=str, help="Name of the service to build"
            )
            subparser.add_argument(
                "--project_name",
                type=str,
                help="Project name for tagging images (defaults to environment variable)",
            )
            subparser.add_argument(
                "--google_artifact_registry",
                type=str,
                help="Google Artifact Registry URL (defaults to environment variable)",
            )

    args = parser.parse_args()

    initialize_logging(args)

    # Load environment variables from the .env file in the current working directory
    load_environment()

    try:
        if args.command in subcommands:
            subcommand_func = subcommands[args.command]

            try:
                env = parse_env(args.env)
            except SystemExit:
                return  # Exit gracefully if parse_env fails

            kwargs = {
                "env": env,
                "force": args.force,
                "verbose": args.verbose,
                "nocache": args.nocache,
            }

            # Add 'service' if it's specified and the function accepts it
            if hasattr(args, "service") and args.service:
                kwargs["service"] = args.service

            # Filter out arguments that are not expected by the subcommand function
            filtered_kwargs = {
                k: v
                for k, v in kwargs.items()
                if k in subcommand_func.__code__.co_varnames
            }

            subcommand_func(**filtered_kwargs)
        else:
            print(f"Unknown command: {args.command}")
            parser.print_help()
            sys.exit(1)
    except subprocess.CalledProcessError as e:
        logger.error(f"Command '{e.cmd}' failed with return code {e.returncode}")
        print(f"Command '{e.cmd}' failed with return code {e.returncode}")
        sys.exit(e.returncode)


if __name__ == "__main__":
    main()
