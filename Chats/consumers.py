import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.core.exceptions import ObjectDoesNotExist
from Chats.models import Conversation, Message, Notification
from Auth.models import MarketUser

# Store active WebSocket connections for chats and notifications
active_chat_connections = {}
active_notification_connections = {}


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """Handles new WebSocket connections for chat."""
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.room_group_name = f"chat_{self.conversation_id}"
        
        # ✅ Check if user is authenticated
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.close()
            return

        # Track active connections for this chat
        if self.conversation_id not in active_chat_connections:
            active_chat_connections[self.conversation_id] = set()
        active_chat_connections[self.conversation_id].add(self)

        await self.accept()
        print(f"✅ {self.user.username} connected to chat {self.conversation_id}")

    async def disconnect(self, close_code):
        """Handles WebSocket disconnections for chat."""
        if self.conversation_id in active_chat_connections:
            active_chat_connections[self.conversation_id].discard(self)
            if not active_chat_connections[self.conversation_id]:
                del active_chat_connections[self.conversation_id]

        print(f"🚪 {self.user.username} disconnected from chat {self.conversation_id}")

    async def receive(self, text_data):
        """Handles incoming chat messages."""
        data = json.loads(text_data)
        action = data.get("action")

        if action == "send_message":
            content = data.get("content")
            picture = data.get("picture")

            conversation, seller, buyer = await self.get_conversation_and_users(self.conversation_id)

            if not conversation:
                await self.send(json.dumps({"error": "Conversation not found"}))
                return

            if self.user not in [seller, buyer]:
                await self.send(json.dumps({"error": "Unauthorized"}))
                return

            # Save the message
            new_message = await self.save_message(conversation, self.user, content, picture)

            # Send notification to the recipient
            recipient = buyer if self.user == seller else seller
            await self.create_notification(recipient, new_message)

            # Send the message to all active chat connections
            response = {
                "action": "new_message",
                "sender": self.user.profile.username,
                "content": content,
                "picture": picture,
                "timestamp": str(new_message.timestamp),
                "seen": new_message.seen,
            }

            for conn in active_chat_connections.get(self.conversation_id, set()):
                await conn.send(json.dumps(response))

        elif action == "mark_as_seen":
            await self.mark_messages_as_seen(self.conversation_id, self.user.id)

            response = {
                "action": "messages_seen",
                "user_id": self.user.id,
            }

            for conn in active_chat_connections.get(self.conversation_id, set()):
                await conn.send(json.dumps(response))

    @sync_to_async
    def get_conversation_and_users(self, conversation_id):
        """Fetches the conversation, seller, and buyer from the database."""
        try:
            conversation = Conversation.objects.select_related("seller", "buyer").get(id=conversation_id)
            return conversation, conversation.seller, conversation.buyer
        except ObjectDoesNotExist:
            return None, None, None

    @sync_to_async
    def save_message(self, conversation, sender, content, picture):
        """Saves a new message to the database."""
        return Message.objects.create(
            conversation=conversation,
            sender=sender,
            content=content,
            picture=picture,
        )

    @sync_to_async
    def mark_messages_as_seen(self, conversation_id, user_id):
        """Marks all messages in the conversation as seen."""
        Message.objects.filter(
            conversation_id=conversation_id,
            sender_id=user_id,
        ).update(seen=True)

    @sync_to_async
    def create_notification(self, user, message):
        """Creates a notification for the recipient when a message is sent."""
        return Notification.objects.create(
            user=user,
            message=message,
        )

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """Handles new WebSocket connections for notifications."""
        self.user_id = self.scope["user"].id
        if not self.user_id:
            await self.close()
            return

        # Track active notification connections
        if self.user_id not in active_notification_connections:
            active_notification_connections[self.user_id] = set()
        active_notification_connections[self.user_id].add(self)

        await self.accept()
        print(f"🔔 Client connected for notifications (User ID: {self.user_id})")

        # Send unread notifications on connect
        await self.send_unread_notifications()

    async def disconnect(self, close_code):
        """Handles WebSocket disconnections for notifications."""
        if self.user_id in active_notification_connections:
            active_notification_connections[self.user_id].discard(self)
            if not active_notification_connections[self.user_id]:
                del active_notification_connections[self.user_id]

        print(f"🔕 Client disconnected from notifications (User ID: {self.user_id})")

    async def receive(self, text_data):
        """Handles incoming WebSocket messages for notifications."""
        data = json.loads(text_data)
        action = data.get("action")

        if action == "mark_notifications_seen":
            await self.mark_notifications_as_seen()

    @sync_to_async
    def get_unread_notifications(self):
        """Fetches unread notifications for the user."""
        return list(Notification.objects.filter(user_id=self.user_id, seen=False).values(
            "id", "message__content", "message__sender__profile__username", "message__timestamp"
        ))

    async def send_unread_notifications(self):
        """Sends unread notifications to the user."""
        notifications = await self.get_unread_notifications()
        await self.send(json.dumps({"action": "unread_notifications", "notifications": notifications}))

    @sync_to_async
    def mark_notifications_as_seen(self):
        """Marks all notifications as seen for the user."""
        Notification.objects.filter(user_id=self.user_id, seen=False).update(seen=True)
