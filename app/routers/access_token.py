# app/routers/access_token.py

import logging
import traceback
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from app.models.access_token import UserCreationTokenResponse
from app.lib.user_manager import UserManager
from app.lib.dependencies import get_user_manager, get_secrets

router = APIRouter(tags=["Access Token"])


@router.post(
    "/access-token/user-creation-token/create", response_model=UserCreationTokenResponse
)
async def create_user_creation_token(
    user_manager: UserManager = Depends(get_user_manager),
):
    """
    Creates a unique access token and a corresponding user ID as a user creation token.

    Returns:
        JSONResponse: The generated user creation token containing access_token and user_id.
    """
    try:
        access_token = str(uuid4())
        result = await user_manager.create_user_creation_token(access_token)
        return JSONResponse(content=result, status_code=201)
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(
            f"Error creating user creation token: {e}\n{traceback.format_exc()}"
        )
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/access-token/auth/regenerate")
async def regenerate_access_token(
    user_id: str = Header(None, alias="X-User-ID"),
    auth_provider: str = Header(None, alias="X-Auth-Provider"),
    auth_user_id: str = Header(None, alias="X-Auth-User-ID"),
    authorization: str = Header(None, alias="Authorization"),
    user_manager: UserManager = Depends(get_user_manager),
):
    """
    Regenerates the access token for the specified user by user ID or auth provider.

    Args:
        user_id (str): The user ID for direct access token regeneration.
        auth_provider (str): The authentication provider (optional).
        auth_user_id (str): The auth provider's user ID (optional).

    Returns:
        JSONResponse: The new access token for the user.
    """
    try:
        if not user_id and not (auth_provider and auth_user_id):
            raise HTTPException(
                status_code=400,
                detail="Either User ID or both auth_provider and auth_user_id are required",
            )

        secrets = get_secrets()
        auth_provider_secret = authorization.split(" ")[1]
        auth_provider_key = f"auth-providers_{auth_provider}"

        if secrets.get(auth_provider_key) != auth_provider_secret:
            raise HTTPException(status_code=401, detail="Invalid auth provider key")

        # Call the regenerate_access_token method in UserManager
        result = await user_manager.regenerate_access_token(
            user_id=user_id, auth_provider=auth_provider, auth_user_id=auth_user_id
        )

        return JSONResponse(content=result, status_code=200)

    except HTTPException as e:
        logging.warning(f"HTTP exception: {e.detail}")
        raise e
    except Exception as e:
        logging.error(f"Error regenerating access token: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
