# app/models/user.py

from pydantic import BaseModel, Field
from typing import Optional


class CreateUserRequest(BaseModel):
    """
    Represents a request to create a user with optional username and email fields.

    Attributes:
        user_id (str): The unique identifier for the user.
        username (Optional[str]): The username of the user.
        email (Optional[str]): The email address of the user.
    """

    user_id: str = Field(..., alias="userId")
    username: Optional[str] = None
    email: Optional[str] = None


class User(BaseModel):
    """
    Represents a user with optional username and email fields.

    Attributes:
        user_id (str): The unique identifier for the user.
        username (Optional[str]): The username of the user.
        email (Optional[str]): The email address of the user.
    """

    user_id: str = Field(..., alias="userId")
    username: Optional[str] = None
    email: Optional[str] = None
