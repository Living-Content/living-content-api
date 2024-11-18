from fastapi import WebSocket
from functions import RealtimeAPIHandler


class RealtimeWebSocketHandler:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.handler = RealtimeAPIHandler(api_key)

    async def handle_audio_stream(self, websocket: WebSocket):
        """Handle incoming audio stream from the WebSocket."""
        try:
            while True:
                # Read audio data from the WebSocket
                data = await websocket.receive_bytes()

                # Process it using the Realtime API
                async for audio_chunk in self.handler.handle_audio_stream(data):
                    # Send processed audio back to the WebSocket
                    await websocket.send_bytes(audio_chunk)
        except Exception as e:
            # Handle errors or disconnection
            print(f"Error in RealtimeWebSocketHandler: {e}")
            await websocket.close()
