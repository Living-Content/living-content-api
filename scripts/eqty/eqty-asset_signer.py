"""
This script processs the artists approval (assets and functions) and creates signed attestations of those approvals.
It iterates over all the json files in the ./authorizations directory to create the statements.
These statments are then copied during application runtime if the corresponding CID is used by the code,
so that they appear in the generated manifest.
"""

import json
import os

import eqty.sdk.core


def create_function_statements(cid: str, metadata: str):
    eqty.sdk.core.add_data_statement([cid], True, cid)
    eqty.sdk.core.add_metadata_statement(cid, metadata, True, cid)


def create_asset_statements(cid: str, metadata: str):
    eqty.sdk.core.add_data_statement([cid], True, cid)
    eqty.sdk.core.add_metadata_statement(cid, metadata, True, cid)


def load_auth(file: str, project: str, type_: str):
    asset = json.load(file)
    cid = asset.pop("cid")
    asset["namespace"] = project

    if type_ == "assets":
        asset["type"] = "Data"
        asset["assetType"] = "Document"
        asset["blob_type"] = "File"
        metadata = json.dumps(asset)
        create_asset_statements(cid, metadata)

    elif type_ == "functions":
        asset["type"] = "Computation"
        asset["assetType"] = "Code"
        asset["blob_type"] = "File"
        metadata = json.dumps(asset)
        create_function_statements(cid, metadata)

    else:
        raise Exception("Unknown approval type", type_)


def process_authorizations(project: str, auth_dir: str, type_: str):
    dir = os.path.join(auth_dir, type_)
    if os.path.exists(dir):
        for filename in os.listdir(dir):
            file_path = os.path.join(dir, filename)
            if file_path.endswith(".json"):
                with open(file_path) as file:
                    load_auth(file, project, type_)
    else:
        raise Exception(f"Approved {type_} directory not found", dir)


current_dir = os.path.dirname(os.path.abspath(__file__))

# init sdk to save to correct folder
project = "PROJECT_ID"
output_dir = os.path.join(current_dir, "signed-statements")
eqty.init(project=project, custom_dir=output_dir)

auth_dir = os.path.join(current_dir, "authorizations")

process_authorizations(project, auth_dir, "assets")
process_authorizations(project, auth_dir, "functions")
