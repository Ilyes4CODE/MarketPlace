import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import Ticket
from asgiref.sync import sync_to_async

class TicketChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.ticket_id = self.scope["url_route"]["kwargs"]["ticket_id"]
        self.room_group_name = f"ticket_{self.ticket_id}"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data["message"]
        sender = data["sender"]

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message,
                "sender": sender
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "message": event["message"],
            "sender": event["sender"]
        }))



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