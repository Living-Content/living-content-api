import asyncio
import json
import logging
import uuid
from typing import Any

from redis.exceptions import ConnectionError as RedisConnectionError


class WebSocketClient:
    def __init__(self, redis_client, worker_id):
        self.redis = redis_client
        self.active_connections: dict[str, dict[str, Any]] = (
            {}
        )  # user_id -> {client_id -> {websocket, last_sequence}}
        self._logger = logging.getLogger(__name__)
        self.pubsubs = {}  # Dictionary to hold pubsub objects per user
        self.user_listen_tasks = {}  # Dictionary to hold tasks per user
        self.max_buffer_size = 100
        self.worker_id = worker_id
        self.worker_channel = f"worker_channel:{worker_id}"

    async def initialize(self):
        asyncio.create_task(self.worker_heartbeat())
        asyncio.create_task(self.periodic_connection_check())
        asyncio.create_task(self.listen_worker_channel())

    async def listen_worker_channel(self):
        """Listen for worker-specific messages like force disconnect commands"""
        try:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe(self.worker_channel)

            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        if data["type"] == "force_disconnect":
                            user_id = data["user_id"]
                            client_id = data.get(
                                "client_id"
                            )  # Optional - specific client
                            self._logger.info(
                                f"Received force disconnect for user {user_id} client {client_id or 'all'}"
                            )
                            await self.handle_force_disconnect(user_id, client_id)
                    except Exception as e:
                        self._logger.error(
                            f"Error processing worker channel message: {e}"
                        )
                await asyncio.sleep(0.01)

        except Exception as e:
            self._logger.error(f"Error in worker channel listener: {e}")
            await asyncio.sleep(5)
            asyncio.create_task(self.listen_worker_channel())

    async def worker_heartbeat(self, interval: int = 5):
        """Periodically update the worker's heartbeat in Redis."""
        while True:
            await self.redis.set(f"worker_active:{self.worker_id}", 1, ex=10)
            await asyncio.sleep(interval)

    async def listen_for_user_messages(self, user_id):
        try:
            while True:
                try:
                    pubsub = self.redis.pubsub()
                    await pubsub.subscribe(f"user_channel:{user_id}")
                    self.pubsubs[user_id] = pubsub

                    async for message in pubsub.listen():
                        if message["type"] == "message":
                            try:
                                data = json.loads(message["data"])
                                msg_sequence = data.get("sequence")

                                # Check if any client needs this message
                                if user_id in self.active_connections:
                                    min_sequence = min(
                                        client_info["last_sequence"]
                                        for client_info in self.active_connections[
                                            user_id
                                        ].values()
                                    )

                                    if msg_sequence > min_sequence:
                                        self._logger.debug(
                                            f"[User {user_id}] New message with sequence {msg_sequence}"
                                        )
                                        await self._send_message_to_user(user_id, data)

                            except Exception as e:
                                self._logger.error(
                                    f"Error processing message for user {user_id}: {e}"
                                )
                        await asyncio.sleep(0.01)

                except RedisConnectionError as e:
                    self._logger.error(
                        f"Redis connection error for user {user_id}: {e}"
                    )
                    await asyncio.sleep(5)
                except Exception as e:
                    self._logger.error(f"Unexpected error for user {user_id}: {e}")
                    break
        except asyncio.CancelledError:
            self._logger.info(
                f"listen_for_user_messages task for user {user_id} was cancelled."
            )
            return

    async def get_next_sequence(self, user_id: str):
        return await self.redis.incr(f"message_sequence:{user_id}")

    async def send_message(self, user_id: str, message: dict):
        # Assign sequence number and buffer the message
        sequence = await self.get_next_sequence(user_id)
        message["sequence"] = sequence

        # Buffer the message
        await self.buffer_message(user_id, sequence, message)

        # Publish the message to the user's channel
        await self.redis.publish(f"user_channel:{user_id}", json.dumps(message))

    async def _send_message_to_user(
        self, user_id: str, message: dict, new_message=True
    ):
        """Send message to all clients of a user"""
        if user_id not in self.active_connections:
            self._logger.warning(f"No active connections for user {user_id}")
            return

        for client_id, client_info in self.active_connections[user_id].items():
            if message["sequence"] > client_info["last_sequence"]:
                await self._send_message_to_client(user_id, client_id, message)

    async def _send_message_to_client(
        self, user_id: str, client_id: str, message: dict
    ):
        """Send message to a specific client"""
        try:
            client_info = self.active_connections[user_id][client_id]
            websocket = client_info["websocket"]
            await websocket.send_json(message)
            self._logger.info(
                f"Sent message (seq: {message.get('sequence')}) to user {user_id} client {client_id}"
            )
        except Exception as e:
            self._logger.error(
                f"Error sending to client {client_id} of user {user_id}: {e}"
            )
            await self.disconnect(user_id, client_id)

    async def buffer_message(self, user_id: str, sequence: int, message: dict):
        """Buffer messages in Redis."""
        buffer_key = f"user_message_buffer:{user_id}"
        await self.redis.lpush(buffer_key, json.dumps(message))
        await self.redis.ltrim(buffer_key, 0, self.max_buffer_size - 1)

    async def retrieve_buffered_messages(self, user_id):
        messages = await self.redis.lrange(f"user_message_buffer:{user_id}", 0, -1)
        return messages

    async def handle_message_acknowledgement(
        self, user_id: str, sequence: int, client_id: str
    ):
        """Handle message acknowledgment from a specific client"""
        if (
            user_id not in self.active_connections
            or client_id not in self.active_connections[user_id]
        ):
            return

        # First check if this client already acknowledged this sequence
        client_ack_key = f"client_ack:{user_id}:{client_id}:{sequence}"
        if await self.redis.exists(client_ack_key):
            self._logger.debug(
                f"Duplicate ack from client {client_id} for sequence {sequence}"
            )
            return

        # Set client acknowledgment with short TTL
        await self.redis.setex(client_ack_key, 60, 1)  # 60 second TTL

        completion_lock_key = f"completion_lock:{user_id}:{sequence}"

        try:
            # Update client's last seen sequence
            self.active_connections[user_id][client_id]["last_sequence"] = sequence

            # Log the initial acknowledgment
            self._logger.info(
                f"Received acknowledgment from user {user_id} client {client_id} for message {sequence}"
            )

            # Check if we need to process completion
            current_min_sequence = await self.redis.get(f"min_sequence:{user_id}")
            if current_min_sequence and int(current_min_sequence) >= sequence:
                return  # This sequence has already been fully processed

            # Check if all clients have acknowledged this message
            min_sequence = min(
                client["last_sequence"]
                for client in self.active_connections[user_id].values()
            )

            if min_sequence >= sequence:
                # Try to acquire completion lock
                if await self.redis.set(completion_lock_key, 1, ex=5, nx=True):
                    try:
                        # Store the new minimum sequence
                        await self.redis.set(f"min_sequence:{user_id}", min_sequence)
                        await self.redis.set(f"last_ack:{user_id}", sequence)

                        # Clean up the message from buffer
                        await self._remove_acknowledged_message(user_id, sequence)

                        self._logger.info(
                            f"Message {sequence} fully acknowledged by all clients of user {user_id}"
                        )
                    finally:
                        await self.redis.delete(completion_lock_key)

        except Exception as e:
            self._logger.error(f"Error processing acknowledgment: {e}")
            raise

    async def _remove_acknowledged_message(self, user_id: str, sequence: int):
        """Remove an acknowledged message from the buffer"""
        buffer_key = f"user_message_buffer:{user_id}"
        buffered_messages = await self.retrieve_buffered_messages(user_id)

        for message_str in buffered_messages:
            msg = json.loads(message_str)
            if msg.get("sequence") == sequence:
                await self.redis.lrem(buffer_key, 1, message_str)
                break

    async def connect(self, websocket: Any, user_id: str) -> str:
        """Connect a new client and return its client_id"""
        client_id = str(uuid.uuid4())

        # Initialize user's connection dictionary if not exists
        if user_id not in self.active_connections:
            self.active_connections[user_id] = {}
            # Start listening for messages only if this is the first client
            task = asyncio.create_task(self.listen_for_user_messages(user_id))
            self.user_listen_tasks[user_id] = task

        # Get last acknowledged sequence for user
        last_ack = await self.redis.get(f"last_ack:{user_id}")
        last_ack = int(last_ack) if last_ack else 0

        # Add the new client connection
        self.active_connections[user_id][client_id] = {
            "websocket": websocket,
            "last_sequence": last_ack,
        }

        # Update Redis with connection info
        connection_key = f"user_connections:{user_id}"
        current_connections = await self.redis.get(connection_key)
        connections = []

        if current_connections:
            connections = json.loads(current_connections)
            if isinstance(connections, str):  # Handle legacy format
                connections = [{"worker_id": connections, "client_id": "legacy"}]

        connections.append(
            {
                "worker_id": self.worker_id,
                "client_id": client_id,
                "connected_at": asyncio.get_event_loop().time(),
            }
        )

        await self.redis.set(connection_key, json.dumps(connections))

        # Handle buffered messages for new client
        await self._send_missed_messages(user_id, client_id)

        self._logger.info(f"Client {client_id} connected for user {user_id}")
        return client_id

    async def _send_missed_messages(self, user_id: str, client_id: str):
        """Send missed messages to a newly connected client"""
        buffered_messages = await self.retrieve_buffered_messages(user_id)
        client_info = self.active_connections[user_id][client_id]

        messages_to_send = []
        for message_str in buffered_messages:
            msg = json.loads(message_str)
            if msg["sequence"] > client_info["last_sequence"]:
                messages_to_send.append(msg)

        # Sort by sequence and send
        messages_to_send.sort(key=lambda x: x["sequence"])
        for msg in messages_to_send:
            await self._send_message_to_client(user_id, client_id, msg)

    async def disconnect(self, user_id: str, client_id: str = None):
        """Disconnect a specific client or all clients of a user"""
        if user_id not in self.active_connections:
            return

        if client_id:
            # Remove specific client
            self.active_connections[user_id].pop(client_id, None)

            # Update Redis connections
            connection_key = f"user_connections:{user_id}"
            current_connections = await self.redis.get(connection_key)
            if current_connections:
                connections = json.loads(current_connections)
                connections = [
                    conn
                    for conn in connections
                    if not (
                        conn["worker_id"] == self.worker_id
                        and conn["client_id"] == client_id
                    )
                ]
                if connections:
                    await self.redis.set(connection_key, json.dumps(connections))
                else:
                    await self.redis.delete(connection_key)

            self._logger.info(f"Client {client_id} disconnected for user {user_id}")

            # If no more clients for this user
            if not self.active_connections[user_id]:
                await self._cleanup_user_resources(user_id)
        else:
            # Disconnect all clients for this user
            await self._cleanup_user_resources(user_id)

    async def _cleanup_user_resources(self, user_id: str):
        """Clean up all resources for a user"""
        # Cancel listen task
        task = self.user_listen_tasks.pop(user_id, None)
        if task:
            task.cancel()

        # Close pubsub
        pubsub = self.pubsubs.pop(user_id, None)
        if pubsub:
            await pubsub.unsubscribe(f"user_channel:{user_id}")
            await pubsub.close()

        # Remove from active connections
        self.active_connections.pop(user_id, None)

        # Clean up Redis
        await self.redis.delete(f"user_connections:{user_id}")
        self._logger.info(f"Cleaned up all resources for user {user_id}")

    async def handle_force_disconnect(self, user_id: str, client_id: str = None):
        """Handle force disconnect command from another worker"""
        if user_id in self.active_connections:
            if client_id and client_id in self.active_connections[user_id]:
                # Disconnect specific client
                websocket = self.active_connections[user_id][client_id]["websocket"]
                await websocket.close()
                await self.disconnect(user_id, client_id)
            else:
                # Disconnect all clients for this user
                for client_info in self.active_connections[user_id].values():
                    await client_info["websocket"].close()
                await self.disconnect(user_id)

    async def periodic_connection_check(self, interval: int = 30):
        """Periodically check connections and clean up stale ones"""
        while True:
            await asyncio.sleep(interval)
            for user_id in list(self.active_connections.keys()):
                for client_id, client_info in list(
                    self.active_connections[user_id].items()
                ):
                    try:
                        websocket = client_info["websocket"]
                        await websocket.send_json({"type": "ping"})
                    except Exception as e:
                        self._logger.info(
                            f"Client {client_id} for user {user_id} appears disconnected: {e}"
                        )
                        await self.disconnect(user_id, client_id)

            # Clean up user_connections pointing to inactive workers
            connected_users = await self.redis.keys("user_connections:*")
            for redis_key in connected_users:
                user_id = redis_key.split(":")[-1]
                connections_data = await self.redis.get(redis_key)
                if not connections_data:
                    continue

                try:
                    connections = json.loads(connections_data)
                    if isinstance(connections, str):  # Handle legacy format
                        worker_id = connections
                        worker_active = await self.redis.exists(
                            f"worker_active:{worker_id}"
                        )
                        if not worker_active:
                            await self.redis.delete(redis_key)
                    else:
                        # Remove connections for inactive workers
                        active_connections = []
                        for conn in connections:
                            worker_id = conn["worker_id"]
                            worker_active = await self.redis.exists(
                                f"worker_active:{worker_id}"
                            )
                            if worker_active:
                                active_connections.append(conn)

                        if active_connections:
                            await self.redis.set(
                                redis_key, json.dumps(active_connections)
                            )
                        else:
                            await self.redis.delete(redis_key)
                except Exception as e:
                    self._logger.error(
                        f"Error cleaning up connections for {user_id}: {e}"
                    )

    async def close(self):
        """Gracefully close WebSocketClient."""
        # Cancel all active tasks
        for task in self.user_listen_tasks.values():
            try:
                task.cancel()
                await task  # Ensure tasks are fully cancelled
            except asyncio.CancelledError:
                pass

        # Unsubscribe and close pubsub connections
        for pubsub in self.pubsubs.values():
            try:
                await pubsub.close()
            except Exception as e:
                self._logger.error(f"Error closing pubsub: {e}")

        # Clear active connections and internal states
        active_connections_count = len(self.active_connections)
        user_listen_tasks_count = len(self.user_listen_tasks)
        pubsubs_count = len(self.pubsubs)

        self.active_connections.clear()
        self.user_listen_tasks.clear()
        self.pubsubs.clear()

        self._logger.info(
            f"WebSocketClient closed successfully. Cleared {active_connections_count} active connections, "
            f"{user_listen_tasks_count} tasks, and {pubsubs_count} pubsubs."
        )
