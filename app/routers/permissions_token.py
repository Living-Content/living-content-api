# app/routers/permissions_token.py

from fastapi import APIRouter, Depends, HTTPException, Request

from app.lib.dependencies import get_permissions_token_manager
from app.lib.permissions_token_manager import PermissionsTokenManager

router = APIRouter(tags=["Permissions Token"])


@router.post("/permission-token/generate")
async def generate_permission_token(
    request: Request,
    permissions_token_manager: PermissionsTokenManager = Depends(
        get_permissions_token_manager
    ),
):
    """
    Generates a new permission token for a user.

    Args:
        request (Request): The request object containing the access token.

    Returns:
        dict: The generated permission token.
    """
    user_id = request.state.user_id
    token = permissions_token_manager.generate_permission_token(user_id)
    return {"token": token}


@router.get("/permission-token/validate/")
async def validate_permission_token(
    token: str,
    permissions_token_manager: PermissionsTokenManager = Depends(
        get_permissions_token_manager
    ),
):
    """
    Validates a permission token.

    Args:
        request (Request): The request object containing the access token.
        token (str): The permission token to validate.

    Returns:
        dict: The status of the validation.
    """
    token_data = permissions_token_manager.get_permission_token_data(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"status": "valid", "token_data": token_data}


@router.post("/permission-token/revoke")
async def revoke_permission_token(
    request: Request,
    token: str,
    permissions_token_manager: PermissionsTokenManager = Depends(
        get_permissions_token_manager
    ),
):
    """
    Revokes a permission token.

    Args:
        request (Request): The request object containing the access token.
        token (str): The permission token to revoke.

    Returns:
        dict: The status of the revocation.
    """
    admin_user_id = request.state.user_id
    permissions_token_manager.revoke_permission_token(token, admin_user_id)
    return {"status": "revoked"}
