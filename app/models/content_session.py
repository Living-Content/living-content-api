from typing import Any

from pydantic import BaseModel, Field


class UpdateContentSessionData(BaseModel):
    """
    Represents the payload for updating data in a content session.

    Attributes:
        new_data (Optional[Dict[str, Any]]): The new data to update in the content session. Default is None.
    """

    new_data: dict[str, Any] = Field(None, alias="newData")
