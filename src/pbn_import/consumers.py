"""WebSocket consumers for PBN import real-time updates"""

import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import ImportLog, ImportSession


class ImportProgressConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time import progress updates"""

    async def connect(self):
        """Handle WebSocket connection"""
        self.session_id = self.scope["url_route"]["kwargs"].get("session_id")
        self.room_group_name = f"import_{self.session_id}"

        # Check if user has permission to view this session
        if await self.has_permission():
            # Join room group
            await self.channel_layer.group_add(self.room_group_name, self.channel_name)

            await self.accept()

            # Send initial connection confirmation
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "connection",
                        "message": f"Connected to import session {self.session_id}",
                        "session_id": self.session_id,
                    }
                )
            )

            # Send current session status
            await self.send_current_status()
        else:
            await self.close()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        # Leave room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        """Handle messages from WebSocket"""
        data = json.loads(text_data)
        message_type = data.get("type")

        if message_type == "ping":
            # Respond to ping with pong
            await self.send(
                text_data=json.dumps(
                    {"type": "pong", "timestamp": data.get("timestamp")}
                )
            )
        elif message_type == "request_status":
            # Send current status
            await self.send_current_status()
        elif message_type == "request_logs":
            # Send recent logs
            await self.send_recent_logs()

    # Receive message from room group
    async def import_update(self, event):
        """Handle import update from channel layer"""
        # Send message to WebSocket
        await self.send(
            text_data=json.dumps({"type": "import_update", "data": event["data"]})
        )

    async def progress_update(self, event):
        """Handle progress update from channel layer"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "progress_update",
                    "progress": event["progress"],
                    "current_step": event.get("current_step", ""),
                    "message": event.get("message", ""),
                }
            )
        )

    async def log_entry(self, event):
        """Handle new log entry from channel layer"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "log_entry",
                    "log": {
                        "timestamp": event["timestamp"],
                        "level": event["level"],
                        "step": event["step"],
                        "message": event["message"],
                    },
                }
            )
        )

    async def status_change(self, event):
        """Handle status change from channel layer"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "status_change",
                    "old_status": event["old_status"],
                    "new_status": event["new_status"],
                    "message": event.get("message", ""),
                }
            )
        )

    async def statistics_update(self, event):
        """Handle statistics update from channel layer"""
        await self.send(
            text_data=json.dumps(
                {"type": "statistics_update", "statistics": event["statistics"]}
            )
        )

    async def completion_notification(self, event):
        """Send completion notification"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "completion",
                    "success": event["success"],
                    "message": event["message"],
                }
            )
        )

    @database_sync_to_async
    def has_permission(self):
        """Check if user has permission to view this session"""
        if not self.scope["user"].is_authenticated:
            return False

        try:
            session = ImportSession.objects.get(pk=self.session_id)
            # User can view their own sessions or if they're staff
            return (
                session.user == self.scope["user"]
                or self.scope["user"].is_staff
                or self.scope["user"].is_superuser
            )
        except ImportSession.DoesNotExist:
            return False

    @database_sync_to_async
    def get_session_status(self):
        """Get current session status"""
        try:
            session = ImportSession.objects.get(pk=self.session_id)
            return {
                "status": session.status,
                "current_step": session.current_step,
                "progress": session.overall_progress,
                "completed_steps": session.completed_steps,
                "total_steps": session.total_steps,
                "duration": str(session.duration) if session.duration else None,
            }
        except ImportSession.DoesNotExist:
            return None

    @database_sync_to_async
    def get_recent_logs(self, limit=20):
        """Get recent log entries"""
        logs = ImportLog.objects.filter(session_id=self.session_id).order_by(
            "-timestamp"
        )[:limit]

        return [
            {
                "timestamp": log.timestamp.isoformat(),
                "level": log.level,
                "step": log.step,
                "message": log.message,
            }
            for log in reversed(logs)
        ]

    async def send_current_status(self):
        """Send current session status to client"""
        status = await self.get_session_status()
        if status:
            await self.send(
                text_data=json.dumps({"type": "status_update", "status": status})
            )

    async def send_recent_logs(self):
        """Send recent logs to client"""
        logs = await self.get_recent_logs()
        await self.send(text_data=json.dumps({"type": "logs_batch", "logs": logs}))
