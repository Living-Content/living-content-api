import asyncio
import aiohttp


class OpenAiRealtimeClient:
    def __init__(
        self, api_key: str, base_url: str = "https://api.openai.com/v1/audio/stream"
    ):
        self.api_key = api_key
        self.base_url = base_url

    async def send_audio_stream(self, audio_stream: asyncio.StreamReader):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "audio/wav",  # Adjust based on the format
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.base_url, headers=headers, data=audio_stream
            ) as response:
                if response.status != 200:
                    raise Exception(f"Realtime API error: {await response.text()}")

                async for chunk in response.content.iter_chunked(1024):
                    yield chunk
