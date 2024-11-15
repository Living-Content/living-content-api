from fastapi import APIRouter, Depends, HTTPException, Request
from app.models.function import GetEnabledFunctionListRequest
from app.lib.function_handler import FunctionHandler
from app.lib.dependencies import get_function_handler

router = APIRouter(tags=["Functions"])


@router.post("/functions/get-enabled")
async def get_function_list(
    request: Request,
    get_function_list_request: GetEnabledFunctionListRequest,
    handler: FunctionHandler = Depends(get_function_handler),
):
    try:
        # Access normalized user_id and access_token from request.state
        user_id = request.state.user_id
        access_token = request.state.access_token

        if not user_id or not access_token:
            raise HTTPException(status_code=403, detail="Unauthorized access")

        # Retrieve enabled functions using the provided function type
        functions = await handler.get_enabled_functions(
            user_id, access_token, get_function_list_request.function_type
        )

        # Format the function list for response
        function_list = [
            {
                "functionId": func["function_id"],
                "hint": func.get("hint"),
                "query": func.get("query"),
                "associatedPlugin": func.get("associated_plugin"),
            }
            for func in functions
        ]

        return {
            "status": "success",
            "data": function_list,
            "message": "Available functions returned successfully.",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
