from fastapi import APIRouter, Depends, HTTPException, Header, Request
from app.models.query import QueryRequest, GetQueriesRequest
from app.lib.query_handler import QueryHandler
from app.lib.dependencies import get_secrets, get_query_handler, get_user_manager
from app.lib import save_asset
import logging
import traceback
import eqty

router = APIRouter(tags=["Query"])


@router.post("/query/submit")
async def receive_query_request(
    request: Request,
    query_request: QueryRequest,
    handler: QueryHandler = Depends(get_query_handler),
    secrets: dict = Depends(get_secrets),
):
    try:
        # Retrieve the user ID and access token set by the middleware
        user_id = request.state.user_id
        access_token = request.state.access_token
        content_session_id = request.headers.get("X-Content-Session-ID")

        if not user_id or not access_token:
            raise HTTPException(status_code=403, detail="Unauthorized access")

        # Validate the API key if functionId is provided in the request
        api_key = request.headers.get("X-API-Key")
        if "functionId" in query_request and (
            not api_key or api_key != secrets.get("living-content_api_key")
        ):
            raise HTTPException(
                status_code=403, detail="Valid API key required with data"
            )

        # Ensure content session ID is provided
        if not content_session_id:
            raise HTTPException(status_code=403, detail="Content session ID not found")

        # Proceed with asset creation and query submission
        user_asset = create_query_asset(user_id, content_session_id)
        user_query = QueryRequest.to_eqty_asset(query_request, content_session_id)
        save_asset(user_query)

        return await handler.submit_query_request(
            user_query, user_asset, content_session_id
        )

    except HTTPException as e:
        logging.error(f"HTTP Exception in endpoint: {e.status_code}: {e.detail}")
        raise e
    except Exception as e:
        logging.error("Unexpected error submitting query:")
        logging.error(traceback.format_exc())  # Log the full traceback
        raise HTTPException(status_code=500, detail="An internal error occurred.")


@router.post("/query/get-history")
async def get_query_history(
    request: Request,
    query_request: GetQueriesRequest,
    handler: QueryHandler = Depends(get_query_handler),
    secrets: dict = Depends(get_secrets),
):
    """Get the history of queries in a content session; content session is included in the request body"""
    try:
        # Access user ID and access token from request state
        user_id = request.state.user_id
        access_token = request.state.access_token

        if not user_id or not access_token:
            raise HTTPException(status_code=403, detail="Unauthorized access")

        # Validate API key if present
        api_key = request.headers.get("X-API-Key")
        if api_key and api_key != secrets["api_key"]:
            raise HTTPException(status_code=403, detail="Invalid API key")

        # Retrieve query history
        return await handler.get_query_history(query_request, user_id, access_token)

    except ValueError as e:
        logging.error(f"Error retrieving query history: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as e:
        logging.error(f"HTTP Exception in endpoint: {e.status_code}: {e.detail}")
        raise e
    except Exception as e:
        logging.error(f"Unexpected error retrieving query history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def create_query_asset(user_id: str, content_session_id: str):
    user = eqty.Asset(
        user_id,
        name="User ID",
        data_type="Data",
        blob_type=eqty.sdk.metadata.BlobType.FILE,
        asset_type=eqty.sdk.asset.AssetType.DOCUMENT,
        description="Identifier of the user",
        project=content_session_id,
    )
    save_asset(user)
    return user
