# app/routers/user.py

import logging
import traceback
from fastapi import APIRouter, HTTPException, Request, Depends, Header
from fastapi.responses import JSONResponse
from uuid import uuid4
from app.lib.user_manager import UserManager
from app.lib.dependencies import get_user_manager

router = APIRouter(tags=["User"])


@router.post("/user/create")
async def create_user(
    user_manager: UserManager = Depends(get_user_manager),
    authorization: str = Header(alias="Authorization"),
):
    try:
        if authorization and authorization.startswith("Bearer "):
            access_token = authorization.split(" ")[1]
        else:
            raise HTTPException(status_code=403, detail="Access token not found")

        user_creation_token_data = await user_manager.validate_user_creation_token(
            access_token
        )
        user_id = user_creation_token_data["userId"]

        # Pass the validated access token to the create_user method to store it in the database
        created_user_id = await user_manager.create_user(user_id, access_token)
        await user_manager.delete_user_creation_token(access_token)

        return JSONResponse(content={"userId": created_user_id}, status_code=201)
    except HTTPException as e:
        logging.warning(f"HTTP exception: {e.detail}")
        raise e
    except Exception as e:
        logging.error(f"Error creating user: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/user/")
async def get_user(
    request: Request, user_manager: UserManager = Depends(get_user_manager)
):
    try:
        user_data = await user_manager.get_user_data(request.state.user_id)
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        return JSONResponse(content=user_data, status_code=200)
    except HTTPException as e:
        logging.warning(f"HTTP exception: {e.detail}")
        raise e
    except Exception as e:
        logging.error(f"Error retrieving user: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/user/validate")
async def validate_user(
    request: Request,
    authorization: str = Header(alias="Authorization"),
    user_manager: UserManager = Depends(get_user_manager),
):
    try:
        user_data = await user_manager.get_user_data(request.state.user_id)
        if not user_data:
            return {"valid": False, "verified": False}

        is_verified = user_data.get("verified", False)
        if is_verified:
            return {"valid": False, "verified": True}

        if authorization and authorization.startswith("Bearer "):
            access_token = authorization.split(" ")[1]
        else:
            raise HTTPException(
                status_code=403, detail="Missing or invalid Authorization header"
            )

        if access_token == user_data.get("accessToken"):
            return {"valid": True, "verified": False}

        return {"valid": False, "verified": False}
    except HTTPException as e:
        logging.warning(f"HTTP exception: {e.detail}")
        raise e
    except Exception as e:
        logging.error(f"Internal Server Error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/user/auth")
async def authenticate_user(
    user_manager: UserManager = Depends(get_user_manager),
    auth_provider: str = Header(alias="X-Auth-Provider"),
    auth_user_id: str = Header(alias="X-Auth-User-ID"),
):
    try:
        # Get user data by auth_provider and auth_user_id
        user_data = await user_manager.get_user_data_by_auth_provider(
            auth_provider, auth_user_id
        )
        if not user_data:
            access_token = str(uuid4())  # Generate a new access token
            # Create user if not found
            created_user_id = await user_manager.create_user_with_auth_provider(
                auth_provider, auth_user_id, access_token
            )
            # Return new user response
            return JSONResponse(
                content={
                    "userId": created_user_id,
                    "accessToken": access_token,
                    "isNewUser": True,
                },
                status_code=201,
            )

        # Return existing user response
        return JSONResponse(
            content={
                **user_data,
                "isNewUser": False,
            },
            status_code=200,
        )
    except HTTPException as e:
        logging.warning(f"HTTP exception: {e.detail}")
        raise e
    except Exception as e:
        logging.error(f"Error authenticating user: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
