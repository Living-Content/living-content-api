from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import aiohttp
from typing import AsyncGenerator

router = APIRouter(tags=["Content Session"])

API_KEY = "YOUR_OPENAI_API_KEY"  # Replace with your OpenAI API key
API_URL = "https://api.openai.com/v1/audio/speech"


@router.get("/tts/stream")
async def tts_stream_async(
    text: str = "Hello, this is a test of streaming text to speech.",
    voice: str = "alloy",
    model: str = "tts-1",
    response_format: str = "mp3",
    speed: float = 1.0,
):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": response_format,
        "speed": speed,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL, headers=headers, json=data) as response:
            if response.status != 200:
                error_text = await response.text()
                raise HTTPException(status_code=response.status, detail=error_text)

            async def async_stream_audio() -> AsyncGenerator[bytes, None]:
                async for chunk in response.content.iter_chunked(1024):
                    yield chunk

    media_type = (
        f"audio/{response_format}" if response_format != "mp3" else "audio/mpeg"
    )

    return StreamingResponse(async_stream_audio(), media_type=media_type)
