from fastapi import APIRouter, Depends
from functions import RealtimeAPIHandler

router = APIRouter()


@router.post("/speech-services/process-audio")
async def process_audio(audio_stream: bytes, handler: RealtimeAPIHandler = Depends()):
    async for chunk in handler.handle_audio_stream(audio_stream):
        yield chunk
