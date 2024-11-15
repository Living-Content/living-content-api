# app/plugins/image_generator/apiframe_client.py

import httpx
import asyncio
import logging
from typing import Dict, Any
from httpx import Timeout, AsyncClient
from fastapi import HTTPException


class Apiframe_Client:
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Apiframe_Client, cls).__new__(cls)
        return cls._instance

    def __init__(
        self, base_url: str = "https://api.apiframe.pro", api_key: str = "YOUR_API_KEY"
    ):
        if not hasattr(self, "initialized"):
            self.base_url = base_url
            self.api_key = api_key
            self.client = None
            self.logger = logging.getLogger(__name__)
            self.initialized = True

    async def get_client(self):
        if self.client is None:
            self.client = AsyncClient(
                base_url=self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=Timeout(30.0),
            )
        return self.client

    async def close_client(self):
        if self.client:
            await self.client.aclose()
            self.client = None

    async def make_request(
        self, method: str, endpoint: str, data: Dict[str, Any] = None
    ):
        client = await self.get_client()

        try:
            self.logger.info(f"Making {method} request to {endpoint} with data: {data}")
            response = await client.request(method, endpoint, json=data)
            self.logger.info(f"Response status: {response.status_code}")
            response.raise_for_status()
            self.logger.info(f"Response content: {response.text}")
            return response.json()
        except httpx.HTTPStatusError as e:
            self.logger.error(
                f"HTTP error occurred: {e.response.status_code} {e.response.text}"
            )
            raise HTTPException(
                status_code=e.response.status_code,
                detail={
                    "message": "HTTP error occurred",
                    "data": e.response.text,
                    "details": str(e),
                },
            )
        except httpx.RequestError as e:
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
