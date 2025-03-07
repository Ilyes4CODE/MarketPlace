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

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # Add user to Redis chat tracking
        self.add_user_to_chat(self.conversation_id, self.user.id)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

        # Remove user from Redis tracking
        self.remove_user_from_chat(self.conversation_id, self.user.id)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_text = data.get("message")
        recipient_id = data.get("recipient_id")
        picture = data.get("picture")  # Optional

        if not message_text and not picture:
            return  # Ignore empty messages

        recipient = await self.get_user_by_id(recipient_id)
        if not recipient:
            return  # Ignore invalid recipient

        # Ensure recipient is part of the conversation
        if not self.is_user_in_chat(recipient.id):
            self.add_user_to_chat(self.conversation_id, recipient.id)

        message = await self.save_message(self.user, recipient, message_text, picture)
        if message:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": message_text,
                    "sender_id": self.user.id,
                    "recipient_id": recipient.id,
                    "picture": picture,
                    "timestamp": str(message.timestamp),
                },
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    @sync_to_async
    def get_user_by_id(self, user_id):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

    @sync_to_async
    def save_message(self, sender, recipient, message_text, picture=None):
        sender_marketuser = MarketUser.objects.get(profile=sender)
        recipient_marketuser = MarketUser.objects.get(profile=recipient)

        seller = sender_marketuser if sender_marketuser.is_seller else recipient_marketuser
        buyer = recipient_marketuser if sender_marketuser.is_seller else sender_marketuser

        conversation, created = Conversation.objects.get_or_create(
            seller=seller, buyer=buyer,
            defaults={"product": self.get_product_for_conversation(seller, buyer)}
        )

        if not conversation.product:
            return None  # Ensure product exists

        message = Message.objects.create(
            sender=sender_marketuser,
            recipient=recipient_marketuser,
            conversation=conversation,
            content=message_text,
            picture=picture
        )

        return message

    @sync_to_async
    def get_product_for_conversation(self, seller, buyer):
        return Product.objects.filter(seller=seller, conversation__buyer=buyer).first()

    def add_user_to_chat(self, conversation_id, user_id):
        redis_client.sadd(f"chat_users:{conversation_id}", user_id)

    def remove_user_from_chat(self, conversation_id, user_id):
        redis_client.srem(f"chat_users:{conversation_id}", user_id)

    def is_user_in_chat(self, user_id):
        user_ids = redis_client.smembers(f"chat_users:{self.conversation_id}")
        if str(user_id) in user_ids:
            return True
        return Conversation.objects.filter(id=self.conversation_id).filter(
            Q(seller__profile__id=user_id) | Q(buyer__profile__id=user_id)
        ).exists()

        
        
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