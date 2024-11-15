# app/models/permissions_token.py

from pydantic import BaseModel
from typing import Optional


class PermissionsToken(BaseModel):
    """
    Model representing a permission token.

    Attributes:
        token (str): The permission token string.
        user_id (str): The ID of the user associated with the token.
        permissions (Optional[dict]): A dictionary of permissions.
        role (str): The role of the user. Defaults to 'user'.
        status (str): The status of the token. Defaults to 'unverified'.
        created_at (float): The creation time of the token.
    """
    permissions_token: str
    user_id: str
    permissions: Optional[dict] = None
    role: str = "user"
    status: str = "unverified"
    created_at: float
