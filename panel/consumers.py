import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils.timezone import now
from Auth.models import MarketUser
from Product.models import Product, Bid

class MarketplaceStatsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """Connect WebSocket and join the admin statistics group."""
        self.group_name = "marketplace_stats"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send initial statistics
        stats = await self.get_marketplace_statistics()
        await self.send(text_data=json.dumps({"type": "marketplace_stats", "data": stats}))

    async def disconnect(self, close_code):
        """Remove the client from the WebSocket group."""
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """Handle incoming messages (not needed for this use case)."""
        pass

    async def send_statistics_update(self, event):
        """Send updated statistics to the connected WebSocket clients."""
        await self.send(text_data=json.dumps({"type": "marketplace_stats", "data": event["data"]}))

    @database_sync_to_async
    def get_marketplace_statistics(self):
        """Fetch the latest marketplace statistics."""
        today = now().date()

        return {
            "active_users": MarketUser.objects.filter(profile__is_active=True).count(),
            "accepted_bids": Bid.objects.filter(status="accepted").count(),
            "active_products": Product.objects.filter(is_approved=True, sold=False).count(),
            "pending_products": Product.objects.filter(is_approved=False).count(),
            "pending_bids": Bid.objects.filter(status="pending").count(),
            "banned_users": MarketUser.objects.filter(is_banned=True).count(),
            "users_today": MarketUser.objects.filter(profile__date_joined__date=today).count(),
            "rejected_bids": Bid.objects.filter(status="rejected").count(),
        }
