from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from .models import TTSRequest
from .providers.openai.openai_tts_handler import OpenAiTtsHandler

router = APIRouter()


@router.post("/speech-services/stream-tts")
async def stream_tts(
    request: TTSRequest,
    handler: OpenAiTtsHandler = Depends(),
):
    """
    Endpoint for streaming text-to-speech using OpenAI TTS
    """
    try:

        async def audio_stream():
            async for audio_chunk in handler.stream_openai_tts(request.text):
                yield audio_chunk

        return StreamingResponse(
            audio_stream(),
            media_type="audio/mpeg",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
