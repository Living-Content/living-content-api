# app/plugins/speech_services/router.py

from fastapi import APIRouter, Depends
from .functions import SpeechServiceFunctions

router = APIRouter()


@router.post("/speech-services/process-audio")
async def process_audio(
    audio_stream: bytes, handler: SpeechServiceFunctions = Depends()
):
    async for chunk in handler.handle_audio_stream(audio_stream):
        yield chunk
