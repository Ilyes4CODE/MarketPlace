import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.shortcuts import get_object_or_404
from .models import Notificationbid
from Auth.models import MarketUser

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """Authenticate and connect only if the user is logged in."""
        if self.scope["user"].is_authenticated:
            # Ensure self.user is a MarketUser instance
            self.user = await self.get_market_user(self.scope["user"].id)  
            
            if self.user:
                self.group_name = f"user_{self.user.id}"
                
                # Join user's WebSocket group
                await self.channel_layer.group_add(self.group_name, self.channel_name)
                await self.accept()

                # Send unread notifications to the user upon connection
                unread_notifications = await self.get_unread_notifications()
                await self.send(text_data=json.dumps({"notifications": unread_notifications}))
            else:
                await self.close()
        else:
            await self.close()

    async def disconnect(self, close_code):
        """Remove the user from the WebSocket group on disconnect."""
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """Handle incoming messages (not needed for notifications)."""
        pass

    async def send_notification(self, event):
        """Send a real-time notification to the user."""
        await self.send(text_data=json.dumps({
            "type": "notification",
            "message": event["message"],
            "created_at": event["created_at"]  # Ensure datetime is formatted before sending
        }))

    @database_sync_to_async
    def get_market_user(self, user_id):
        """Ensure the user is an instance of MarketUser."""
        return get_object_or_404(MarketUser, profile_id=user_id)  # ✅ Use profile_id correctly

    @database_sync_to_async
    def get_unread_notifications(self):
        """Fetch unread notifications for the authenticated user."""
        return [
            {
                "id": notification["id"],
                "message": notification["message"],
                "created_at": notification["created_at"].strftime("%Y-%m-%d %H:%M:%S")  # ✅ Convert datetime to string
            }
            for notification in Notificationbid.objects.filter(recipient=self.user, is_read=False).values("id", "message", "created_at")
        ]
