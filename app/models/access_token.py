# app/models/access_token.py

from pydantic import BaseModel, Field


class AccessToken(BaseModel):
    """
    Model representing an access token.

    Attributes:
        access_token (str): The access token string.
    """
    access_token: str = Field(..., alias='accessToken')


class UserCreationTokenResponse(BaseModel):
    """
    Model representing the response for user creation.

    Attributes:
        access_token (AccessToken): The generated access token.
        user_id (str): The unique identifier for the user.
    """
    access_token: AccessToken
    user_id: str = Field(..., alias='userId')

    class Config:
        populate_by_name = True
