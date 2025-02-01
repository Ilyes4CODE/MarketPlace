# Chats/consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.core.exceptions import ObjectDoesNotExist
from Chats.models import Conversation, Message
from Auth.models import MarketUser

# Dictionary to store active WebSocket connections
active_connections = {}

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f"chat_{self.conversation_id}"

        # Add the connection to the active connections
        if self.conversation_id not in active_connections:
            active_connections[self.conversation_id] = set()
        active_connections[self.conversation_id].add(self)

        # Accept the connection
        await self.accept()
        print(f"✅ Client connected to chat {self.conversation_id}")

    async def disconnect(self, close_code):
        # Remove the connection from active connections
        if self.conversation_id in active_connections:
            active_connections[self.conversation_id].discard(self)
            if not active_connections[self.conversation_id]:
                del active_connections[self.conversation_id]
        print(f"🚪 Client disconnected from chat {self.conversation_id}")

    async def receive(self, text_data):
        # Parse the incoming message
        data = json.loads(text_data)
        sender_id = data.get("sender_id")
        content = data.get("content")

        # Fetch conversation and users
        conversation, seller, buyer, sender = await self.get_conversation_and_users(self.conversation_id, sender_id)

        if not conversation:
            await self.send(json.dumps({"error": "Conversation not found"}))
            return

        if not sender:
            await self.send(json.dumps({"error": "Invalid sender"}))
            return

        # Ensure sender is either the seller or the buyer
        if sender not in [seller, buyer]:
            await self.send(json.dumps({"error": "Unauthorized"}))
            return

        # Save the message
        new_message = await self.save_message(conversation, sender, content)

        # Broadcast the message to all connected clients
        response = {
            "sender": sender.profile.username,
            "content": content,
            "timestamp": str(new_message.timestamp)
        }

        for conn in active_connections.get(self.conversation_id, set()):
            await conn.send(json.dumps(response))

    @sync_to_async
    def get_conversation_and_users(self, conversation_id, sender_id):
        """
        Fetches the conversation, seller, buyer, and sender from the database.
        """
        try:
            conversation = Conversation.objects.select_related("seller", "buyer").get(id=conversation_id)
            seller = conversation.seller
            buyer = conversation.buyer
            sender = MarketUser.objects.select_related('profile').get(id=sender_id)
            return conversation, seller, buyer, sender
        except ObjectDoesNotExist:
            return None, None, None, None

    @sync_to_async
    def save_message(self, conversation, sender, content):
        """
        Saves a new message to the database.
        """
        return Message.objects.create(
            conversation=conversation,
            sender=sender,
            content=content
        )