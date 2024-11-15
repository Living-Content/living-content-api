import aiohttp
import asyncio
import logging
from typing import Dict, Any
from aiohttp import ClientTimeout
from fastapi import HTTPException


class Jenai_Client:
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Jenai_Client, cls).__new__(cls)
        return cls._instance

    def __init__(
        self,
        base_url: str = "https://jen-staging.futureverseai.com",
        api_key: str = "YOUR_API_KEY",
    ):
        if not hasattr(self, "initialized"):
            self.base_url = base_url
            self.api_key = api_key
            self.client = None
            self.logger = logging.getLogger(__name__)
            self.initialized = True

    async def get_client(self):
        if self.client is None:
            timeout = ClientTimeout(total=30.0)
            self.client = aiohttp.ClientSession(
                base_url=self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=timeout,
            )
        return self.client

    async def close_client(self):
        if self.client:
            await self.client.close()
            self.client = None

    async def make_request(
        self, method: str, endpoint: str, data: Dict[str, Any] = None
    ):
        client = await self.get_client()

        try:
            self.logger.error(
                f"Making {method} request to {endpoint} with data: {data}"
            )

            async with client.request(method, endpoint, json=data) as response:
                self.logger.info(f"Response status: {response.status}")
                if response.status >= 400:
                    self.logger.error(f"HTTP error: {response.status}")
                    raise HTTPException(
                        status_code=response.status,
                        detail={
                            "message": "HTTP error occurred",
                            "data": await response.text(),
                            "details": response.reason,
                        },
                    )

                response_json = await response.json()
                self.logger.info(f"Response content: {response_json}")
                return response_json

        except aiohttp.ClientError as e:
            self.logger.error(f"Network error occurred: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Network error occurred",
                    "data": "network_error",
                    "details": str(e),
                },
            )
        except Exception as e:
            self.logger.error(f"Unexpected error occurred: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Internal server error",
                    "data": "internal_server_error",
                    "details": str(e),
                },
            )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_client()
