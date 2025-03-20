import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import Ticket, Message
from asgiref.sync import sync_to_async
from django.utils.timezone import localtime
from django.core.exceptions import ObjectDoesNotExist
from channels.db import database_sync_to_async
from Auth.models import MarketUser
import base64
import uuid
from django.core.files.base import ContentFile

class TicketChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.ticket_id = self.scope["url_route"]["kwargs"]["ticket_id"]
        self.room_group_name = f"ticket_{self.ticket_id}"

        # Validate ticket existence and ownership
        # ticket = await self.get_ticket_with_profile()
        # print(f"debug : {ticket.user.pk} == {self.user.pk} ")
        # if not ticket:
        #     await self.send_error("Ticket not found.")
        #     await self.close()
        #     return

        # # Fix: Ensure safe access to the user's profile
        # user_profile_id = ticket.user.profile.id if ticket.user.profile else None
        # if user_profile_id != self.user.id:
        #     await self.send_error("You are not authorized to access this ticket.")
        #     await self.close()
        #     return

        # Join WebSocket group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        print(self.user.id)
        # Send old messages
        old_messages = await self.get_old_messages()
        await self.send(text_data=json.dumps({
            "type": "old_messages",
            "messages": old_messages
        }))


    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_content = data.get("message", "").strip()
            image_data = data.get("picture")  # Expecting base64 image

            if not message_content and not image_data:
                await self.send_error("Message cannot be empty unless an image is provided.")
                return

            # Save image if provided
            image_path = None
            if image_data:
                image_path = await self.save_image(image_data)

            # Save the message
            user_data = await self.get_user_data(self.user.id)
            message = await self.save_message(user_data["id"], message_content, image_path)

            # Broadcast message to the group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": {
                        "id": message.id,
                        "content": message.content,
                        "timestamp": localtime(message.timestamp).isoformat(),
                        "sender_id": self.user.id,
                        "sender_name": user_data["name"],
                        "sender_picture": user_data["picture"],
                        "picture": f"https://marketplace-4m56.onrender.com/{message.image}" if message.image else None,
                    }
                }
            )
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format.")
        except Exception as e:
            await self.send_error(f"An error occurred: {str(e)}")



    @sync_to_async(thread_sensitive=True)
    def get_ticket_with_profile(self):
        """Fetch the ticket with related user profile."""
        try:
            return Ticket.objects.select_related("user__profile").get(id=self.ticket_id)
        except Ticket.DoesNotExist:
            return None
    async def chat_message(self, event):
        """Send a new message to the WebSocket client."""
        await self.send(text_data=json.dumps({
            "type": "new_message",
            "message": event["message"]
        }))
    async def get_user_data(self, user_id):
        """Fetch user name and profile picture from MarketUser."""
        from django.db.models import Prefetch
        from django.contrib.auth import get_user_model
        

        User = get_user_model()

        try:
            # Fetch MarketUser linked to this User ID
            market_user = await database_sync_to_async(MarketUser.objects.get)(profile__id=user_id)

            return {
                "id" : market_user.pk,
                "name": market_user.name,  # Get MarketUser's name
                "picture": market_user.profile_picture.url if market_user.profile_picture else None
            }
        except MarketUser.DoesNotExist:
            return {
                "name": "Unknown",
                "picture": None
            }
    async def send_error(self, error_message):
        """Send an error message to the client."""
        await self.send(text_data=json.dumps({"type": "error", "message": error_message}))

    @sync_to_async(thread_sensitive=True)
    def get_ticket(self):
        """Fetch the ticket from the database."""
        try:
            return Ticket.objects.select_related("user").get(id=self.ticket_id)
        except ObjectDoesNotExist:
            return None

    @sync_to_async
    def get_old_messages(self):
        """Fetch old messages from the database."""
        messages = Message.objects.filter(ticket_id=self.ticket_id).order_by("timestamp")
        return [
            {
                "id": msg.id,
                "content": msg.content,
                "timestamp": localtime(msg.timestamp).isoformat(),
                "sender_id": msg.sender.profile.pk,
                "sender": msg.sender.name,
                "sender_picture": msg.sender.profile_picture.url if msg.sender.profile_picture else None,
                "picture": f"https://marketplace-4m56.onrender.com/{msg.image}" if msg.image else None,
            }
            for msg in messages
        ]
    @sync_to_async
    def save_message(self, sender_id, content, image):
        """Save a new message to the database."""
        return Message.objects.create(ticket_id=self.ticket_id, sender_id=sender_id, content=content, image=image)

    @sync_to_async
    def save_image(self, image_data):
        """Save base64 image and return file path."""
        format, imgstr = image_data.split(";base64,")
        ext = format.split("/")[-1]
        image_name = f"messages/{uuid.uuid4()}.{ext}"

        image = ContentFile(base64.b64decode(imgstr), name=image_name)
        return image

class AdminTicketConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = "admin_tickets"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # ✅ FIX: Await `send_tickets()`
        await self.send_tickets()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """Handle filtering logic from frontend"""
        data = json.loads(text_data)
        filter_status = data.get("status", None)
        filter_user = data.get("user", None)

        tickets = await self.get_filtered_tickets(filter_status, filter_user)

        await self.send(text_data=json.dumps({"tickets": tickets}))

    async def ticket_updated(self, event):
        """✅ FIX: Await `send_tickets()` to send updates when a ticket is modified"""
        await self.send_tickets()

    async def ticket_created(self, event):
        """✅ FIX: Handle new ticket event"""
        await self.send(text_data=json.dumps({"new_ticket": event["ticket"]}))

    @sync_to_async
    def get_all_tickets(self):
        """Fetch all tickets from DB"""
        return [
            {
                "id": ticket.id,
                "subject": ticket.subject,
                "status": ticket.status,
                "user": ticket.user.profile.username,
                "created_at": ticket.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for ticket in Ticket.objects.all()
        ]

    async def send_tickets(self):
        """✅ FIX: This function is async, so it must be awaited"""
        tickets = await self.get_all_tickets()
        await self.send(text_data=json.dumps({"tickets": tickets}))

    @sync_to_async
    def get_filtered_tickets(self, status, user):
        """Fetch tickets with filtering"""
        tickets = Ticket.objects.all()
        if status:
            tickets = tickets.filter(status=status)
        if user:
            tickets = tickets.filter(user__profile__username__icontains=user)

        return [
            {
                "id": ticket.id,
                "subject": ticket.subject,
                "status": ticket.status,
                "user": ticket.user.profile.username,
                "created_at": ticket.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for ticket in tickets
        ]