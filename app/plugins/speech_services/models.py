# app/plugins/speech_services/models.py


from pydantic import BaseModel


class TTSRequest(BaseModel):
    text: str
