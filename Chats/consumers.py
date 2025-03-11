import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.core.exceptions import ObjectDoesNotExist
from Chats.models import Conversation, Message, Notification,ChatNotification
from Auth.models import MarketUser
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q
from channels.db import database_sync_to_async
import logging
from django.utils.dateformat import format
from django.contrib.auth import get_user_model
from django.conf import settings
import redis
import os
from Product.models import Product
from django.utils.timezone import now
# Store active WebSocket connections for chats and notifications
REDIS_URL = os.getenv("REDIS_URL")
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
active_chat_connections = {}
active_notification_connections = {}
logger = logging.getLogger(__name__)
User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close()
            return

        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.room_group_name = f"chat_{self.conversation_id}"
        self.notification_group_name = f"notifications_{self.user.id}"

        # Add user to their chat group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        # Add user to their notification group
        await self.channel_layer.group_add(self.notification_group_name, self.channel_name)

        await self.accept()

        # Track active users in Redis
        await self.add_user_to_chat(self.conversation_id, self.user.id)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

        # Remove user from Redis tracking
        await self.remove_user_from_chat(self.conversation_id, self.user.id)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_text = data.get("message")
        picture = data.get("picture")  # Optional

        if not message_text and not picture:
            return  # Ignore empty messages

        # Get the conversation
        conversation = await self.get_conversation(self.conversation_id)
        if not conversation:
            return  # Invalid conversation

        # Identify sender and recipient as MarketUser
        sender_marketuser = await self.get_market_user(self.user)  # Ensure it's MarketUser
        recipient_marketuser = await database_sync_to_async(lambda: (
            conversation.buyer if sender_marketuser == conversation.seller else conversation.seller
        ))()

        # Fetch sender and recipient details safely
        sender_data = await database_sync_to_async(lambda: {
            "id": sender_marketuser.pk,
            "username": sender_marketuser.name,
            "profile_picture": sender_marketuser.profile_picture.url if sender_marketuser.profile_picture else None
        })()

        recipient_data = await database_sync_to_async(lambda: {
            "id": recipient_marketuser.pk,
            "username": recipient_marketuser.name,
            "profile_picture": recipient_marketuser.profile_picture.url if recipient_marketuser.profile_picture else None
        })()

        # ✅ Fix: Access `profile.pk` inside a sync-to-async wrapper
        recipient_profile_pk = await database_sync_to_async(lambda: recipient_marketuser.profile.pk)()

        print('✅ Recipient Profile PK:', recipient_profile_pk)

        # Save message
        message = await self.save_message(sender_marketuser, recipient_marketuser, message_text, picture)
        if message:
            # Broadcast message to chat group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": message_text,
                    "sender": sender_data,
                    "recipient": recipient_data,
                    "picture": picture,
                    "timestamp": str(message.timestamp),
                },
            )

            # Send a notification to recipient if they are not online
            if not await self.is_user_in_chat(recipient_profile_pk):
                await self.send_chat_notification(recipient_profile_pk, sender_data, message_text)

    async def chat_message(self, event):
        """Handles chat messages and sends them to the frontend."""
        await self.send(text_data=json.dumps(event))

    async def chat_notification(self, event):
        """Handles chat notifications and sends them to the frontend."""
        await self.send(text_data=json.dumps({
            "type": "chat_notification",
            "message": event["message"],
            "recipient_id": event["recipient_id"],
            "sender": event["sender"],
            "timestamp": event["timestamp"],
        }))

    @database_sync_to_async
    def get_conversation(self, conversation_id):
        try:
            return Conversation.objects.select_related("seller", "buyer").get(pk=conversation_id)
        except Conversation.DoesNotExist:
            return None

    @database_sync_to_async
    def get_market_user(self, user):
        try:
            return MarketUser.objects.select_related("profile").get(profile=user)
        except MarketUser.DoesNotExist:
            return None

    @database_sync_to_async
    def save_message(self, sender, recipient, message_text, picture=None):
        return Message.objects.create(
            sender=sender,
            recipient=recipient,
            conversation_id=self.conversation_id,
            content=message_text,
            picture=picture,
            timestamp=now()
        )

    async def add_user_to_chat(self, conversation_id, user_id):
        await database_sync_to_async(redis_client.sadd)(f"chat_users:{conversation_id}", user_id)

    async def remove_user_from_chat(self, conversation_id, user_id):
        await database_sync_to_async(redis_client.srem)(f"chat_users:{conversation_id}", user_id)

    async def is_user_in_chat(self, user_id):
        user_ids = await database_sync_to_async(redis_client.smembers)(f"chat_users:{self.conversation_id}")
        return str(user_id) in user_ids

    async def send_chat_notification(self, recipient_id, sender_data, message_text):
        """Sends a notification to the recipient if they are offline."""
        event_data = {
            "type": "chat_notification",
            "message": message_text,
            "recipient_id": recipient_id,
            "sender": sender_data,
            "timestamp": str(now()),
        }

        print(f"📢 Sending chat notification to {recipient_id}: {event_data}")

        await self.channel_layer.group_send(
            f"notifications_{recipient_id}",  # Ensure recipient's notification group is used
            event_data
        )
    @database_sync_to_async
    def get_current_timestamp(self):
        return now()


class ChatNotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close()
            return

        self.notification_group_name = f"notifications_{self.user.id}"
        print(f"🟢 Subscribing user {self.user.id} to {self.notification_group_name}")

        await self.channel_layer.group_add(self.notification_group_name, self.channel_name)
        await self.accept()

        print(f"✅ User {self.user.id} connected to notifications.")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.notification_group_name, self.channel_name)

    async def chat_notification(self, event):
        """🔹 Fix for 'No handler for message type chat_notification'"""
        await self.send(text_data=json.dumps({
            "type": "chat_notification",
            "message": event["message"],
            "recipient_id": event["recipient_id"],
            "sender": event["sender"],
            # "sender_profile_pic": event["sender_profile_pic"],
            "timestamp": event["timestamp"],
        }))
    

       
        
class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """Handles WebSocket connection and registers user for notifications."""
        user = self.scope.get("user", AnonymousUser())

        if user.is_anonymous:
            logger.warning("🔒 Unauthorized WebSocket connection attempt.")
            await self.close()
            return

        self.user_id = user.id

        # Register user for real-time notifications
        if self.user_id not in active_notification_connections:
            active_notification_connections[self.user_id] = set()
        active_notification_connections[self.user_id].add(self)

        await self.accept()
        print(f"🔔 WebSocket connected for user {self.user_id}")

        # Send unread chat notifications immediately upon connection
        await self.send_unread_chat_notifications()

    async def disconnect(self, close_code):
        """Handles WebSocket disconnection and removes user from tracking."""
        if self.user_id in active_notification_connections:
            active_notification_connections[self.user_id].discard(self)
            if not active_notification_connections[self.user_id]:
                del active_notification_connections[self.user_id]

        logger.info(f"🔕 WebSocket disconnected (User ID: {self.user_id})")

    @sync_to_async
    def get_unread_chat_notifications(self):
        """Fetches unread chat notifications (new messages) ONLY for the logged-in user."""
        notifications = Notification.objects.filter(
            user_id=self.user_id, is_read=False, message__isnull=False  # ✅ Only messages
        ).select_related("message", "message__sender__profile") \
         .values("id", "message__content", "message__sender__profile__username", "message__timestamp")

        # Convert datetime to string
        for notification in notifications:
            notification["message__timestamp"] = notification["message__timestamp"].strftime("%Y-%m-%d %H:%M:%S")  # ✅ Fix

        return list(notifications)

    async def send_unread_chat_notifications(self):
        """Fetches and sends unread chat notifications to the user."""
        try:
            notifications = await self.get_unread_chat_notifications()
            await self.send(json.dumps({"action": "chat_notifications", "notifications": notifications}))
        except Exception as e:
            logger.error(f"❌ Error sending unread chat notifications: {e}")
            await self.send(json.dumps({"error": "Failed to load chat notifications"}))

    @sync_to_async
    def mark_chat_notifications_as_read(self):
        """Marks chat notifications as read when the user enters the conversation."""
        Notification.objects.filter(user_id=self.user_id, is_read=False, message__isnull=False).update(is_read=True)

    async def receive(self, text_data):
        """Handles incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            action = data.get("action")

            if action == "mark_as_read":
                await self.mark_chat_notifications_as_read()
                await self.send(json.dumps({"action": "chat_notifications_marked_as_read"}))
        except json.JSONDecodeError:
            logger.warning("⚠️ Invalid JSON received")

    @classmethod
    async def send_new_notification(cls, user_id, notification_data):
        """Sends a new chat notification to the user's WebSocket in real-time."""
        if user_id in active_notification_connections and "message__content" in notification_data:
            message = json.dumps({"action": "new_chat_notification", "notification": notification_data})
            for connection in active_notification_connections[user_id]:
                await connection.send(message)