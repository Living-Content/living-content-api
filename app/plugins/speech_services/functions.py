import asyncio
from typing import AsyncGenerator
from providers.openai.openai_realtime_client import OpenAiRealtimeClient


class RealtimeAPIHandler:
    def __init__(self, api_key: str):
        self.client = OpenAiRealtimeClient(api_key)

    async def handle_audio_stream(
        self, audio_stream: asyncio.StreamReader
    ) -> AsyncGenerator[bytes, None]:
        async for audio_chunk in self.client.send_audio_stream(audio_stream):
            yield audio_chunk
