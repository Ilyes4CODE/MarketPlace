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
import base64
import uuid
import json
from django.core.files.base import ContentFile
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

        # 🔹 Verify if the user is part of this conversation
        is_participant = await self.is_user_part_of_conversation(self.conversation_id, self.user.id)
        if not is_participant:
            await self.close()
            return

        # Add user to chat and notification groups
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.channel_layer.group_add(self.notification_group_name, self.channel_name)
        
        await self.accept()
        print(f"User {self.user.pk} is connected to conversation {self.conversation_id}")

        # Track active users in Redis 
        await self.add_user_to_chat(self.conversation_id, self.user.id)

        # 🔹 Load old messages and send them to the user
        old_messages = await self.get_old_messages(self.conversation_id)
        receiver_info = await self.get_receiver_info(self.conversation_id, self.user.id)

        await self.send(text_data=json.dumps({
            "type": "old_messages",
            "messages": old_messages,
            "receiver": receiver_info
        }))

    @sync_to_async
    def is_user_part_of_conversation(self, conversation_id, user_id):
        """Check if the user is either the buyer or seller in the conversation"""
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            return conversation.buyer.profile.id == user_id or conversation.seller.profile.id == user_id
        except Conversation.DoesNotExist:
            return False

    @sync_to_async
    def get_old_messages(self, conversation_id):
        """Fetch old messages for the conversation"""
        messages = Message.objects.filter(conversation_id=conversation_id).order_by("timestamp")
        return [
            {
                "sender": msg.sender.profile.pk,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "picture": f"https://marketplace-4m56.onrender.com{msg.picture.url}" if msg.picture else None  # Check if picture exists
            }
            for msg in messages
        ]

    @sync_to_async
    def get_receiver_info(self, conversation_id, current_user_id):
        """Get receiver details (name, picture)"""
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            receiver = conversation.seller if conversation.buyer.profile.id == current_user_id else conversation.buyer
            return {
                "id": receiver.profile.pk,
                "name": receiver.name,
                "profile_picture": f"https://marketplace-4m56.onrender.com{receiver.profile_picture.url}" if receiver.profile_picture else None
            }
        except Conversation.DoesNotExist:
            return {"error": "Conversation not found"}

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

        # Remove user from Redis tracking
        await self.remove_user_from_chat(self.conversation_id, self.user.id)

    async def receive(self, text_data):
        """Handle receiving messages via WebSocket."""
        data = json.loads(text_data)
        message_text = data.get("message")
        picture_data = data.get("picture")  # Expecting base64 encoded image

        if not message_text and not picture_data:
            return  # Ignore empty messages

        # ✅ Get the conversation
        conversation = await self.get_conversation(self.conversation_id)
        if not conversation:
            return  # Invalid conversation

        # ✅ Identify sender and recipient as MarketUser
        sender_marketuser = await self.get_market_user(self.user)  
        recipient_marketuser = await database_sync_to_async(lambda: (
            conversation.buyer if sender_marketuser == conversation.seller else conversation.seller
        ))()

        # ✅ Fetch sender and recipient details safely
        sender_data = await database_sync_to_async(lambda: {
            "id": sender_marketuser.profile.pk,
            "username": sender_marketuser.name,
            "profile_picture": f"https://marketplace-4m56.onrender.com{sender_marketuser.profile_picture.url}" if sender_marketuser.profile_picture else None
        })()

        recipient_data = await database_sync_to_async(lambda: {
            "id": recipient_marketuser.profile.pk,
            "username": recipient_marketuser.name,
            "profile_picture": f"https://marketplace-4m56.onrender.com{recipient_marketuser.profile_picture.url}" if recipient_marketuser.profile_picture else None
        })()

        # ✅ Ensure recipient profile exists
        recipient_profile_pk = await database_sync_to_async(lambda: recipient_marketuser.profile.pk)()

        # ✅ Handle Image Upload (Convert base64 to File)
        image_file = None
        if picture_data:
            image_file = await self.save_image(picture_data)  # ✅ Returns file

        # ✅ Save message with all fields
        message = await self.save_message(sender_marketuser, recipient_marketuser, message_text, image_file)

        if message:
            # ✅ Broadcast message to chat group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": message_text,
                    "sender": sender_data,
                    "recipient": recipient_data,
                    "picture": f"https://marketplace-4m56.onrender.com{message.picture.url}" if message.picture else None,  # ✅ Correct URL
                    "timestamp": str(message.timestamp),
                },
            )

            # ✅ Send a notification if recipient is offline
            if not await self.is_user_in_chat(recipient_profile_pk):
                await self.send_chat_notification(recipient_profile_pk, sender_data, message_text)
            
    async def save_image(self, picture_data):
        """Convert base64 image to Django File and return it (do not save message here)."""
        try:
            format, imgstr = picture_data.split(';base64,')  # Extract base64 string
            ext = format.split('/')[-1]  # Extract file extension

            # Create a unique filename
            filename = f"{uuid.uuid4()}.{ext}"
            data = ContentFile(base64.b64decode(imgstr), name=filename)

            return data  # Return the file (not saving Message here)
        except Exception as e:
            print("❌ Error saving image:", e)
            return None

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