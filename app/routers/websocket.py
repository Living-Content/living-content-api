# app/routers/websocket.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.lib.dependencies import get_ws_connection_manager, get_websocket_manager
from app.lib.websocket_manager import WebSocketManager
from app.lib.connection_manager import ConnectionManager
import logging
import json
from starlette.websockets import WebSocketState

router = APIRouter(tags=["Websocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    connection_manager: ConnectionManager = Depends(get_ws_connection_manager),
    websocket_manager: WebSocketManager = Depends(get_websocket_manager),
):
    user_id = None
    websocket_client = None
    client_id = None

    try:
        await websocket.accept()
        websocket_client = await connection_manager.get_websocket_client()

        # Authenticate user and get user_id
        is_authenticated, user_id = await websocket_manager.authenticate_user(
            websocket, await connection_manager.get_mongo_client()
        )

        if not is_authenticated:
            await websocket.close(code=1008, reason="Authentication failed")
            return

        # Connect and get client_id
        client_id = await websocket_client.connect(websocket, user_id)

        while websocket.client_state == WebSocketState.CONNECTED:
            try:
                if websocket.client_state != WebSocketState.CONNECTED:
                    break

                data = await websocket.receive_json()
                await websocket_manager.handle_incoming_websocket_message(
                    user_id, data.get("type"), data, client_id
                )
            except WebSocketDisconnect:
                logging.info(
                    f"WebSocket disconnected for user {user_id} client {client_id}"
                )
                break
            except RuntimeError as e:
                if "disconnect message has been received" in str(e):
                    logging.info(
                        f"Disconnect message received for user {user_id} client {client_id}"
                    )
                    break
                logging.error(
                    f"Runtime error for user {user_id} client {client_id}: {e}"
                )
                break
            except Exception as e:
                logging.error(
                    f"Error handling message from user {user_id} client {client_id}: {e}"
                )
                break

    except Exception as e:
        logging.error(f"Unexpected error in WebSocket connection: {e}")
    finally:
        if user_id and websocket_client:
            try:
                await websocket_client.disconnect(user_id, client_id)
                logging.info(
                    f"Cleaned up connection for user {user_id} client {client_id}"
                )
            except Exception as e:
                logging.error(
                    f"Error during cleanup for user {user_id} client {client_id}: {e}"
                )
