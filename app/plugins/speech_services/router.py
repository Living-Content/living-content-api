# app/plugins/speech_services/router.py

from fastapi import APIRouter, Depends
from .functions import SpeechServicesFunctions

router = APIRouter()


@router.post("/speech-services/process-audio")
async def process_audio(
    audio_stream: bytes, handler: SpeechServicesFunctions = Depends()
):
    async for chunk in handler.handle_audio_stream(audio_stream):
        yield chunk
