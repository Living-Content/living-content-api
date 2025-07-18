# app/plugins/query/models.py
from typing import Any

import eqty
from pydantic import BaseModel, Field


class Messages(BaseModel):
    """Describes a single message with a role and content."""

    role: str = Field(
        ..., description="The role of the message sender (e.g., user, assistant)."
    )
    content: str = Field(..., description="The content of the message.")
    message_id: str | None = Field(
        default=None,
        description="The unique identifier of the message.",
        alias="messageId",
    )
    created_at: str | None = Field(
        default=None,
        description="The timestamp of the message creation.",
        alias="createdAt",
    )


class QueryRequest(BaseModel):
    """Describes the request for a query, optionally including a model and a list of messages."""

    model: str | None = Field(
        default=None,
        example="gpt-4o",
        description="The model to use for processing the query, defaults to None.",
    )
    system_prompt: str | None = Field(
        default=None,
        alias="systemPrompt",
        example="You are a friendly assistant.",
        description="An overrride for the system prompt to use for the query.",
    )
    function_id: str | None = Field(
        default=None,
        alias="functionId",
        example="generate_a_song_prompt",
        description="A specific function to call.",
    )
    response_schema: dict[str, Any] | None = Field(
        default=None,
        alias="responseSchema",
        example={
            "name": "dynamic_function_response",
            "description": "Dynamically generated schema for function response",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Example string value for 'name'",
                    },
                    "weather": {
                        "type": "string",
                        "description": "Describe the weather for the mentioned city. also mention the city.",
                    },
                    "city": {"type": "string", "description": "the city described"},
                },
                "required": ["name", "somethingElse"],
                "additionalProperties": False,
            },
        },
        description="A JSON schema request for a specific response object.",
    )
    messages: list[Messages] | None = Field(
        default=None,
        description="A list of messages that make up the conversation or query context.",
    )
    additional_data: Any | None = Field(
        default=None,
        alias="additionalData",
        description="Additional data to be passed to the model for processing, can be any type.",
    )
    plugin_data: Any | None = Field(
        default=None,
        alias="pluginData",
        description="Plugin data to be passed to the model for processing, can be any type.",
    )

    @staticmethod
    def to_eqty_asset(query: "QueryRequest", content_session_id: str):
        asset = eqty.Asset(
            query,
            name="User prompt",
            data_type="Data",
            blob_type=eqty.sdk.metadata.BlobType.FILE,
            asset_type=eqty.sdk.asset.AssetType.DOCUMENT,
            description="Prompt data provided by the user",
            project=content_session_id,
        )
        return asset

    def serialize_for_hashing(self):
        return self.model_dump_json(by_alias=True).encode("utf-8")


class GetQueriesRequest(BaseModel):
    """Describes the request for getting all queries."""

    contentSessionId: str = Field(
        ...,
        example="12345",
        description="The ID of the content session to retrieve the query history for.",
    )
