#!/usr/bin/env python3
"""Main entry point for lco-api CLI."""

import logging
import sys
from pathlib import Path

import click
import clicycle as cc

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.commands import config, docker, init, setup
from cli.utils.error_handling import handle_cli_error

logger = logging.getLogger(__name__)


@click.group()
@click.option("--debug", "-d", is_flag=True, help="Enable debug output")
@click.pass_context
def cli(ctx, debug):
    """Living Content API management CLI."""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    
    if debug:
        logging.basicConfig(level=logging.DEBUG, format="DEBUG: %(name)s - %(message)s")
        logger.debug("Debug mode enabled")


# Add command groups
cli.add_command(init.init_group)
cli.add_command(config.config_group)
cli.add_command(setup.setup_group)
cli.add_command(docker.docker_group)


def main():
    """Main entry point."""
    try:
        cli()
    except Exception as e:
        handle_cli_error(e)
        sys.exit(1)


if __name__ == "__main__":
    main()