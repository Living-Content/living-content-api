import json
import logging
import os

import eqty
from pydantic import BaseModel


def save_asset(asset: eqty.Asset):
    content_session_id = getattr(
        asset, "_project", "default_project"
    )  # Fallback project name
    asset_dir = os.path.join(
        eqty.sdk.config.Config().config_dir, content_session_id, "assets"
    )

    os.makedirs(asset_dir, exist_ok=True)
    asset_filename = os.path.join(
        asset_dir, getattr(asset, "cid", f"default_{asset.name}")
    )

    # Try to get the value attribute, with a fallback to an empty string if missing or None
    asset_value = getattr(asset, "value", "")

    try:
        # Determine how to handle the asset's value
        if isinstance(asset_value, str):
            data_to_write = asset_value
        elif isinstance(asset_value, BaseModel):
            data_to_write = asset_value.model_dump_json(by_alias=True)
        elif hasattr(asset_value, "to_json"):
            data_to_write = json.dumps(asset_value.to_json())
        elif asset_value is None:
            data_to_write = ""
        else:
            # Attempt to serialize to JSON, or raise an error if incompatible
            try:
                data_to_write = json.dumps(asset_value)
            except (TypeError, ValueError):
                logging.warning(
                    f"Unable to serialize asset '{asset.name}' as JSON; using empty string as fallback."
                )
                data_to_write = ""

        # Write data to the asset file
        with open(asset_filename, "w", encoding="utf-8") as file:
            file.write(data_to_write)
        logging.info(f"Asset '{asset.name}' saved successfully to '{asset_filename}'.")

    except Exception as e:
        logging.error(f"Failed to save asset '{asset.name}': {e}")
        raise Exception("Unable to save asset.", asset.name) from e
