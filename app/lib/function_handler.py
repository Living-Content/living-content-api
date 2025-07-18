import importlib
import json
import logging
from asyncio import Lock as AsyncLock
from threading import Lock, RLock
from typing import Any

import eqty
from fastapi import HTTPException, status
from tenacity import (
    RetryError,
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.clients.openai_client import OpenAI_Client
from app.lib import save_asset
from app.models.query import Messages, QueryRequest


class FunctionHandler:
    """
    Thread-safe implementation of FunctionHandler for multi-worker environments.
    Implements singleton pattern with proper synchronization.
    """

    _instance = None
    _init_lock = Lock()
    _logger = logging.getLogger(__name__)

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._init_lock:
                if not cls._instance:
                    cls._instance = super(FunctionHandler, cls).__new__(cls)
                    cls._instance.initialized = False
        return cls._instance

    def __init__(
        self, config: dict, secrets: dict, content_session_manager, notification_manager
    ):
        """
        Thread-safe initialization with proper locking mechanisms.
        """
        with self._init_lock:
            if not getattr(self, "initialized", False):
                self._logger.debug("Initializing FunctionHandler")

                # Configuration and dependencies
                self.config = config
                self.secrets = secrets
                self.openai_client = OpenAI_Client(config, secrets)
                self.content_session_manager = content_session_manager
                self.redis_ops = self.content_session_manager.redis_ops
                self.notification_manager = notification_manager

                # Thread-safe collections and locks
                self._modules_lock = RLock()
                self._cache_lock = RLock()
                self._async_lock = AsyncLock()
                self.function_modules: dict[str, object] = {}
                self.function_cache: dict[str, tuple[object, str]] = {}
                self._enabled_functions_cache: list[dict] | None = None

                # Initialize function modules
                self.load_plugin_functions()
                self.load_internal_functions()
                self.initialized = True

    def load_plugin_functions(self) -> None:
        """Thread-safe loading of plugin functions."""
        temp_modules = {}

        for plugin, details in self.config.get("plugins", {}).items():
            if not details.get("enabled", False):
                continue

            try:
                module_name = f"app.plugins.{plugin}.functions"
                module = importlib.import_module(module_name)
                class_name = (
                    "".join(word.capitalize() for word in plugin.split("_"))
                    + "Functions"
                )
                class_ = getattr(module, class_name)

                # Initialize in temporary dict
                temp_modules[plugin] = class_(self)
                self._logger.info(f"Successfully loaded plugin: {plugin}")

            except ImportError as e:
                self._logger.error(
                    f"Module {module_name} could not be imported: {e!s}"
                )
            except AttributeError as e:
                self._logger.error(
                    f"Class {class_name} not found in module {module_name}: {e!s}"
                )
            except Exception as e:
                self._logger.error(f"Failed to load plugin {plugin}: {e!s}")

        # Atomic update of function modules
        with self._modules_lock:
            self.function_modules.update(temp_modules)

    def load_internal_functions(self) -> None:
        """Thread-safe loading of internal functions."""
        try:
            internal_module_name = "app.lib.internal_functions"
            internal_module = importlib.import_module(internal_module_name)
            internal_class = internal_module.InternalFunctions

            with self._modules_lock:
                self.function_modules["internal_functions"] = internal_class(self)
            self._logger.info("Internal functions loaded successfully")

        except Exception as e:
            self._logger.error(f"Failed to load internal functions: {e!s}")
            raise

    async def get_enabled_functions(
        self,
        user_id: str | None = None,
        access_token: str | None = None,
        function_id: str | None = None,
    ) -> list[dict]:
        """Thread-safe retrieval of enabled functions."""
        async with self._async_lock:
            # Check cache first
            if self._enabled_functions_cache is not None:
                return self._enabled_functions_cache[0]

            enabled_functions = []

            # Add plugin functions
            for plugin, details in self.config["plugins"].items():
                if details.get("enabled", False):
                    for func in details.get("functions", []):
                        func["associated_plugin"] = plugin
                        enabled_functions.append(func)

            # Add internal functions
            for func in self.config.get("internal_functions", []):
                func["associated_plugin"] = "internal_functions"
                enabled_functions.append(func)

            if not enabled_functions:
                self._logger.error("No available functions configured")
                return []

            # Atomic cache update
            with self._cache_lock:
                self._enabled_functions_cache = (enabled_functions, None)
                self._logger.debug(f"Cached {len(enabled_functions)} enabled functions")

            return enabled_functions

    def invalidate_function_cache(self) -> None:
        """Thread-safe cache invalidation."""
        with self._cache_lock:
            self._enabled_functions_cache = None
            self._logger.debug("Function cache invalidated")

    @staticmethod
    def filter_and_convert_messages(messages: list[Messages]) -> list[dict]:
        """
        Static method for message conversion (thread-safe by design).
        """
        return [
            {"role": message.role, "content": message.content}
            for message in messages
            if message.role != "system"
        ]

    async def should_stream(self, function_id: str) -> bool:
        """Thread-safe streaming check."""
        enabled_functions = await self.get_enabled_functions()
        function_config = next(
            (func for func in enabled_functions if func["function_id"] == function_id),
            None,
        )

        if function_config is None:
            self._logger.warning(
                f"Function {function_id} not found in enabled functions. Defaulting to non-streaming."
            )
            return False

        return function_config.get("stream", True)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception(Exception),
        reraise=True,
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
    )
    async def _make_request_and_parse(
        self, messages: list[dict[str, str]], enabled_functions: list[dict]
    ) -> dict[str, Any]:
        """Thread-safe request handling with retries."""
        try:
            response = await self.openai_client.client.chat.completions.create(
                model=self.config["clients"]["openai"]["models"]["function_selection"],
                messages=messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "request_function",
                        "description": "Handles a request for a specific function",
                        "schema": {
                            "type": "object",
                            "strict": True,
                            "properties": {
                                "function_id": {
                                    "type": "string",
                                    "description": "The ID of the function being requested",
                                },
                                "generated_data": {
                                    "type": "string",
                                    "description": "Optional generated data to be passed along with the function for context",
                                },
                            },
                            "required": ["function_id"],
                            "additionalProperties": False,
                        },
                    },
                },
                max_tokens=int(self.config["clients"]["openai"]["max_tokens"]),
                stream=False,
            )

            llm_response = response.choices[0].message.content.strip()
            parsed_response = await self._parse_llm_response(llm_response)

            self._logger.debug(f"Selected function: {parsed_response}")

            if not any(
                func["function_id"] == parsed_response["function_id"]
                for func in enabled_functions
            ):
                raise ValueError(
                    f"Selected function '{parsed_response['function_id']}' not in enabled functions"
                )

            return parsed_response

        except Exception as e:
            self._logger.error(f"Error in _make_request_and_parse: {e!s}")
            raise

    @staticmethod
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception(ValueError),
        reraise=True,
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
    )
    async def _parse_llm_response(llm_response: str) -> dict[str, Any]:
        """
        Parse LLM response with retry mechanism.

        Args:
            llm_response: Response string from LLM

        Returns:
            Parsed response dictionary with function_id and optional generated_data

        Raises:
            ValueError: If parsing fails or response is invalid
        """
        if not llm_response:
            raise ValueError("Received empty response from LLM")

        try:
            result = json.loads(llm_response)
        except json.JSONDecodeError as e:
            raise ValueError(f"Error decoding JSON: {e!s}")

        if "function_id" not in result:
            raise ValueError("Invalid LLM response: missing 'function_id'")

        # Normalize generated_data to string if present
        if "generated_data" in result:
            if isinstance(result["generated_data"], (dict, list)):
                result["generated_data"] = " ".join(
                    str(v)
                    for v in (
                        result["generated_data"].values()
                        if isinstance(result["generated_data"], dict)
                        else result["generated_data"]
                    )
                )
            elif not isinstance(result["generated_data"], str):
                result["generated_data"] = str(result["generated_data"])

        return result

    async def select_function(
        self,
        user_query: QueryRequest,
        content_session_id: str,
        function_id: str | None = None,
    ) -> tuple[eqty.Asset, eqty.Asset | None]:
        """Thread-safe function selection."""
        try:
            self._logger.debug(f"Selecting function for query: {user_query}")

            # Handle additional data and plugin data atomically
            async with self._async_lock:
                additional_data = user_query.additional_data
                plugin_data = user_query.plugin_data

                # Save additional data if present
                eqty_additional_data = None
                if additional_data:
                    eqty_additional_data = eqty.Asset(
                        additional_data,
                        name="Additional data",
                        data_type="Data",
                        blob_type=eqty.sdk.metadata.BlobType.FILE,
                        asset_type=eqty.sdk.asset.AssetType.DOCUMENT,
                        description=f"Additional data for function selection:\n{additional_data}",
                        project=content_session_id,
                    )
                    save_asset(eqty_additional_data)

                # Save plugin data if present
                eqty_plugin_data = None
                if plugin_data:
                    eqty_plugin_data = eqty.Asset(
                        plugin_data,
                        name="Plugin data",
                        data_type="Data",
                        blob_type=eqty.sdk.metadata.BlobType.FILE,
                        asset_type=eqty.sdk.asset.AssetType.DOCUMENT,
                        description=f"Plugin data for function selection:\n{plugin_data}",
                        project=content_session_id,
                    )
                    save_asset(eqty_plugin_data)

            # Direct function selection if function_id provided
            if function_id:
                enabled_functions = await self.get_enabled_functions()
                target_function = next(
                    (
                        func
                        for func in enabled_functions
                        if func["function_id"] == function_id
                    ),
                    None,
                )

                if not target_function:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Function '{function_id}' not found in enabled functions.",
                    )

                eqty_function_id = eqty.Asset(
                    function_id,
                    name="Approved function",
                    data_type="Data",
                    blob_type=eqty.sdk.metadata.BlobType.FILE,
                    asset_type=eqty.sdk.asset.AssetType.DOCUMENT,
                    description="Identifier of the approved function",
                    project=content_session_id,
                )
                save_asset(eqty_function_id)
                return eqty_function_id, None

            # Function selection based on user query
            latest_message = f"User message: {user_query.messages[-1].content if user_query.messages else 'No message content'}"
            enabled_functions = await self.get_enabled_functions()

            if not enabled_functions:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No enabled functions found.",
                )

            # Build system prompt and make request
            function_descriptions = "\n".join(
                f"- Function name: {func['function_id']}\n  Hint: {func['hint']}\n  Description: {func['description']}"
                for func in enabled_functions
            )

            system_prompt = (
                "You need to select the most appropriate function for the user's request based on the following options:\n"
                f"{function_descriptions}\n"
                "If the user asks a general question about the function, doesn't provide enough details,"
                "or their query is ambiguous, pass the query to the 'general_query' function."
                "Only select a specific function if the user meets the requirements as outlined in the function description."
            )

            if plugin_data:
                system_prompt += f"\n\nPlugin data: {plugin_data}"
            if additional_data:
                system_prompt += f"\n\nAdditional data: {additional_data}"

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": latest_message},
            ]

            try:
                parsed_response = await self._make_request_and_parse(
                    messages, enabled_functions
                )
            except RetryError as e:
                self._logger.error(f"All retries failed: {e!s}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to process the request after multiple attempts.",
                )

            function_id = parsed_response.get("function_id", "general_query")
            generated_data = parsed_response.get("generated_data")

            # Create and save assets atomically
            async with self._async_lock:
                eqty_function_id = eqty.Asset(
                    function_id,
                    name="Approved function",
                    data_type="Data",
                    blob_type=eqty.sdk.metadata.BlobType.FILE,
                    asset_type=eqty.sdk.asset.AssetType.DOCUMENT,
                    description="Identifier of the approved function",
                    project=content_session_id,
                )
                save_asset(eqty_function_id)

                eqty_generated_data = None
                if generated_data:
                    eqty_generated_data = eqty.Asset(
                        generated_data,
                        name="Generated data",
                        data_type="Data",
                        blob_type=eqty.sdk.metadata.BlobType.FILE,
                        asset_type=eqty.sdk.asset.AssetType.DOCUMENT,
                        description="Generated data to be passed to the function",
                        project=content_session_id,
                    )
                    save_asset(eqty_generated_data)

            return eqty_function_id, eqty_generated_data

        except HTTPException as e:
            self._logger.error(f"HTTP error in select_function: {e.detail}")
            raise
        except Exception as e:
            error_message = f"Unexpected error during function selection: {e!s}"
            self._logger.error(error_message)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_message,
            )

    async def load_function(
        self, function_id: eqty.Asset, query: QueryRequest
    ) -> tuple[bool, object, object]:
        """Thread-safe function loading."""
        try:
            enabled_functions = await self.get_enabled_functions()
            if not any(
                func["function_id"] == function_id.value for func in enabled_functions
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Function {function_id.value} is not allowed as per the configuration.",
                )

            # Check function cache with proper locking
            with self._cache_lock:
                if function_id.value in self.function_cache:
                    func, module_name = self.function_cache[function_id.value]
                    return (
                        await self.should_stream(function_id.value),
                        func,
                        self.function_modules[module_name],
                    )

            # If not in cache, find module name for the function
            module_name = None
            for plugin, details in self.config["plugins"].items():
                if any(
                    func["function_id"] == function_id.value
                    for func in details.get("functions", [])
                ):
                    module_name = plugin
                    break

            if module_name is None:
                module_name = "internal_functions"

            self._logger.debug(
                f"Using module {module_name} for function {function_id.value}"
            )

            # Thread-safe module access
            with self._modules_lock:
                if module_name not in self.function_modules:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Module for function {function_id.value} not found.",
                    )

                # Get function from module
                module = self.function_modules[module_name]
                func = getattr(module, function_id.value, None)

                if not func or not callable(func):
                    raise HTTPException(
                        status_code=404,
                        detail=f"Function {function_id.value} not found.",
                    )

                # Cache the function atomically
                with self._cache_lock:
                    self.function_cache[function_id.value] = (func, module_name)

                # Determine if function should stream
                should_stream = await self.should_stream(function_id.value)
                return should_stream, func, module

        except HTTPException as e:
            self._logger.error(
                f"HTTP Exception in load_function: {e.status_code}: {e.detail}"
            )
            raise
        except Exception as e:
            error_message = f"Error loading function: {e!s}"
            self._logger.error(error_message)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_message
            )
