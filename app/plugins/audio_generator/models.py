from app.models.query import QueryRequest
from pydantic import BaseModel, Field
from typing import Optional, Dict


class SongMetadata(BaseModel):
    src: str = Field(..., description="The URL to the song.")
    description: str = Field(..., description="A description of the song.")


class AudioGeneratorQueryRequest(QueryRequest):
    selected_songs: Optional[Dict[str, SongMetadata]] = Field(
        default=None,
        alias="selectedSongs",
        description="A dictionary of selected audio tracks to be used for audio generation, keyed by unique song IDs.",
    )
