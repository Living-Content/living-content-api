# app/lib/internal_functions.py

import logging
import traceback
import eqty
from datetime import datetime, timezone
from fastapi import HTTPException, status
from app.models.query import Messages


class InternalFunctions:
    def __init__(self, function_handler):
        self.function_handler = function_handler
        self.config = function_handler.config
        self._logger = logging.getLogger(__name__)

    # Helper functions

    def _handle_exception(self, e):
        if isinstance(e, HTTPException):
            self._logger.error(
                f"HTTP error during processing: {e.detail}\n{traceback.format_exc()}"
            )
            raise e
        elif isinstance(e, ValueError):
            self._logger.error(f"ValueError: {e}\n{traceback.format_exc()}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Bad request",
                    "data": "bad_request",
                    "details": str(e),
                    "traceback": traceback.format_exc(),
                },
            )
        else:
            self._logger.error(f"Error during streaming: {e}\n{traceback.format_exc()}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "message": "Internal server error (this is bad)",
                    "data": "internal_server_error",
                    "details": str(e),
                    "traceback": traceback.format_exc(),
                },
            )

    # Internal functions

    async def general_query(
        self,
        user_query: eqty.Asset,
        user_id: eqty.Asset,
        content_session_id: str,
        request_message_id: eqty.Asset,
        response_message_id: eqty.Asset,
        generated_data: eqty.Asset,
        asset: eqty.Asset,
    ):
        try:
            # Validate config
            required_persona_aspects = ["help", "guardrails", "personality"]
            missing_aspects = [
                aspect
                for aspect in required_persona_aspects
                if aspect not in self.config["persona"]
            ]
            if missing_aspects:
                raise ValueError(
                    f"Missing required prompts in self.config['persona']: {', '.join(missing_aspects)}"
                )

            # Get past content session data
            past_content_session_data = await self.function_handler.content_session_manager.get_content_session_data(
                user_id.value,
                content_session_id,
            )

            # Process past messages
            past_messages = []
            queries = past_content_session_data.get("query", {}).get("queries", [])
            for query in queries:
                if isinstance(query, list):
                    for item in query:
                        if isinstance(item, str):
                            message = Messages(role="user", content=item)
                        elif isinstance(item, dict):
                            message = Messages(
                                message_id=item.get("messageId"),
                                created_at=item.get("createdAt"),
                                role=item.get("role"),
                                content=item.get("content"),
                            )
                        else:
                            message = None
                        if message:
                            past_messages.append(message)
                else:
                    if isinstance(query, str):
                        message = Messages(role="user", content=query)
                    elif isinstance(query, dict):
                        message = Messages(
                            message_id=query.get("messageId"),
                            created_at=query.get("createdAt"),
                            role=query.get("role"),
                            content=query.get("content"),
                        )
                    else:
                        message = None
                    if message:
                        past_messages.append(message)

            # Create system prompt
            enabled_functions = await self.function_handler.get_enabled_functions()

            # Define the fallback notice for when only 'general_query' is enabled
            no_functions_notice = "No functions are available other than chat. Let them know up front that you are here to help them with their queries, and any other features covered below will be back online again soon."

            # Determine the functions message based on enabled functions
            functions_message = (
                no_functions_notice
                if len(enabled_functions) == 1
                and enabled_functions[0]["function_id"] == "general_query"
                else f"Assist the user with these functions: {enabled_functions}"
            )

            # Construct the system_prompt with the updated functions_message
            system_prompt = (
                f"Function status: {functions_message}\n"
                f"Your goal: {self.config['persona']['help']}\n"
                f"Your guardrails: {self.config['persona']['guardrails']}\n"
                f"Your personality: {self.config['persona']['personality']}\n"
                f"Example prompt responses: {self.config['persona']['example_prompt_responses']}\n"
                f"Generated data to help guide your response: {generated_data}\n"
            )

            # Prepare query messages
            # Add system prompt to the beginning of the messages
            user_query.messages = past_messages + (user_query.messages or [])
            user_query.messages.insert(
                0, Messages(role="system", content=system_prompt)
            )

            collected_messages = []
            response = await self.function_handler.openai_client.client.chat.completions.create(
                model=self.config["clients"]["openai"]["model"],
                messages=user_query.messages,
                max_tokens=int(self.config["clients"]["openai"]["max_tokens"]),
                stream=True,
            )

            async for chunk in response:
                if chunk.choices:
                    content = chunk.choices[0].delta.content
                    if content:
                        collected_messages.append(content)
                        yield f"data: {content}\n\n"
            yield "data: [DONE]\n\n"

            # Update content session
            last_user_message = next(
                (msg for msg in reversed(user_query.messages) if msg.role == "user"),
                None,
            )
            if last_user_message:
                last_query = [
                    {
                        "messageId": request_message_id.value,
                        "createdAt": datetime.now(timezone.utc).isoformat(),
                        "role": last_user_message.role,
                        "content": last_user_message.content,
                    },
                    {
                        "messageId": response_message_id.value,
                        "createdAt": datetime.now(timezone.utc).isoformat(),
                        "role": "assistant",
                        "content": "".join(collected_messages),
                    },
                ]
                await self.function_handler.content_session_manager.update_content_session(
                    user_id.value,
                    content_session_id,
                    {"query": {"queries": [last_query]}},
                )

        except Exception as e:
            self._handle_exception(e)
