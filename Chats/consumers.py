import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.core.exceptions import ObjectDoesNotExist
from Chats.models import Conversation, Message, Notification
from Auth.models import MarketUser
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q
from channels.db import database_sync_to_async
import logging
from django.utils.dateformat import format

# Store active WebSocket connections for chats and notifications
active_chat_connections = {}
active_notification_connections = {}
logger = logging.getLogger(__name__)

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """Handles new WebSocket connections for chat and marks messages as seen when user enters."""
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.room_group_name = f"chat_{self.conversation_id}"
        
        # ✅ Check if user is authenticated
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.close()
            return

        # ✅ Add the user to the chat group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        
        print(f"✅ {self.user.username} connected to chat {self.conversation_id}")

        # ✅ Mark all unread messages as seen when the user enters the conversation
        await self.mark_messages_as_seen(self.conversation_id, self.user.id)

        # ✅ Notify the chat that messages were seen
        response = {
            "action": "messages_seen",
            "user_id": self.user.id,
        }
        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "chat_message", "message": response},
        )

    async def disconnect(self, close_code):
        """Handles WebSocket disconnections for chat."""
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        print(f"🚪 {self.user.username} disconnected from chat {self.conversation_id}")

    async def receive(self, text_data):
        """Handles incoming chat messages and marks messages as seen when appropriate."""
        data = json.loads(text_data)

        # ✅ If there's "content", it's a new message
        if "content" in data:
            content = data["content"]
            picture = data.get("picture", None)

            conversation, seller, buyer = await self.get_conversation_and_users(self.conversation_id)

            if not conversation:
                await self.send(json.dumps({"error": "Conversation not found"}))
                return

            # if self.user not in [seller, buyer]:
            #     print(seller)
            #     print(buyer)
            #     print(self.user)
            #     await self.send(json.dumps({"error": "Unauthorized"}))
            #     return

            # ✅ Save the message
            new_message = await self.save_message(conversation, self.user, content, picture)

            # ✅ Identify recipient
            recipient = buyer if self.user == seller else seller

            # ✅ Create notification for recipient
            await self.create_notification(recipient, new_message)

            # ✅ Broadcast message to all users in this chat
            response = {
                "action": "new_message",
                "sender": self.user.username,
                "content": content,
                "picture": picture,
                "timestamp": str(new_message.timestamp),
                "seen": new_message.seen,
            }
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "chat_message", "message": response},
            )

        # ✅ If user is in the chat, mark messages as seen
        if self.user in [seller, buyer]:
            await self.mark_messages_as_seen(self.conversation_id, self.user.id)

            seen_response = {
                "action": "messages_seen",
                "user_id": self.user.id,
            }
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "chat_message", "message": seen_response},
            )


    async def chat_message(self, event):
        """Sends messages to all users in the chat."""
        await self.send(json.dumps(event["message"]))

    @sync_to_async(thread_sensitive=True)
    def get_conversation_and_users(self, conversation_id):
        """Fetches the conversation, seller, and buyer from the database."""
        try:
            conversation = Conversation.objects.select_related("seller", "buyer").get(id=conversation_id)
            return conversation, conversation.seller, conversation.buyer
        except ObjectDoesNotExist:
            return None, None, None

    @sync_to_async(thread_sensitive=True)
    def save_message(self, conversation, sender, content, picture):
        """Saves a new message to the database."""
        # Ensure sender is a MarketUser instance
        market_user = MarketUser.objects.get(profile=sender)  # Adjust based on your model relation
        
        return Message.objects.create(
            conversation=conversation,
            sender=market_user,  # Use MarketUser instead of User
            content=content,
            picture=picture,
        )

    @sync_to_async(thread_sensitive=True)
    def mark_messages_as_seen(self, conversation_id, user_id):
            """Marks messages as seen (updates messages from the other user)."""
            Message.objects.filter(
                ~Q(sender_id=user_id),  # ✅ Place Q object first
                conversation_id=conversation_id,
                seen=False
            ).update(seen=True)

    @sync_to_async(thread_sensitive=True)
    def create_notification(self, user, message):
        """Creates a notification for the recipient when a message is sent."""
        return Notification.objects.create(
            user=user,
            message=message,
        )
    

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