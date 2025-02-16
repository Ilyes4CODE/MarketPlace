from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .consumers import MarketplaceStatsConsumer
from Auth.models import MarketUser
from Product.models import Product, Bid
from django.utils.timezone import now

def send_marketplace_statistics_update():
    """Fetch latest statistics and send updates to WebSocket clients."""
    channel_layer = get_channel_layer()
    stats = {
        "active_users": MarketUser.objects.filter(profile__is_active=True).count(),
        "accepted_bids": Bid.objects.filter(status="accepted").count(),
        "active_products": Product.objects.filter(is_approved=True, sold=False).count(),
        "pending_products": Product.objects.filter(is_approved=False).count(),
        "pending_bids": Bid.objects.filter(status="pending").count(),
        "banned_users": MarketUser.objects.filter(is_banned=True).count(),
        "users_today": MarketUser.objects.filter(profile__date_joined__date=now().date()).count(),
        "rejected_bids": Bid.objects.filter(status="rejected").count(),
    }
    
    async_to_sync(channel_layer.group_send)(
        "marketplace_stats", {"type": "send_statistics_update", "data": stats}
    )

# Connect signals to relevant models
@receiver(post_save, sender=MarketUser)
@receiver(post_save, sender=Product)
@receiver(post_save, sender=Bid)
@receiver(post_delete, sender=MarketUser)
@receiver(post_delete, sender=Product)
@receiver(post_delete, sender=Bid)
def update_statistics(sender, instance, **kwargs):
    """Trigger a WebSocket update when relevant data changes."""
    send_marketplace_statistics_update()
