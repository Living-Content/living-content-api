# app/routers/webhook.py
from fastapi import APIRouter, Depends
from app.lib.connection_manager import ConnectionManager
from app.lib.dependencies import get_http_connection_manager

router = APIRouter(tags=["Webhook"])


@router.post("/webhook")
async def handle_webhook(
    session_id: str,
    payload: dict,
    connection_manager: ConnectionManager = Depends(get_http_connection_manager),
):
    websocket_client = await connection_manager.get_websocket_client()
    await websocket_client.broadcast({session_id, payload})
    return {"message": "Payload sent to the specified session"}
