import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import Message, Conversation
from .serializer import MessageSerializer
from django.utils import timezone
from channels.db import database_sync_to_async

class ConversationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        conversation_id = self.scope['url_route']['kwargs']['id']
        self.conversation = await self.get_conversation(conversation_id)
        if self.conversation.seller == self.scope['user'].marketuser or self.conversation.buyer == self.scope['user'].marketuser:
            self.room_group_name = f'conversation_{conversation_id}'
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            await self.accept()
        else:
            await self.close()

    async def disconnect(self, close_code):
        # Leave the room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        # Receive message from WebSocket
        text_data_json = json.loads(text_data)
        message_content = text_data_json['message']

        # Save the message to the database
        message = await self.save_message(message_content)

        # Send message to WebSocket group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message_content,
                'sender': str(self.scope['user']),
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        )

    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender'],
            'timestamp': event['timestamp']
        }))

    async def get_conversation(self, conversation_id):
        try:
            return await database_sync_to_async(Conversation.objects.get)(id=conversation_id)
        except Conversation.DoesNotExist:
            return None

    async def save_message(self, message_content):
        user = self.scope['user'].marketuser
        message = Message.objects.create(
            conversation=self.conversation,
            sender=user,
            content=message_content
        )
        return message
