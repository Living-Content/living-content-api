
from pydantic import BaseModel, Field

from app.models.query import QueryRequest


class SongMetadata(BaseModel):
    src: str = Field(..., description="The URL to the song.")
    description: str = Field(..., description="A description of the song.")


class AudioGeneratorQueryRequest(QueryRequest):
    selected_songs: dict[str, SongMetadata] | None = Field(
        default=None,
        alias="selectedSongs",
        description="A dictionary of selected audio tracks to be used for audio generation, keyed by unique song IDs.",
    )
