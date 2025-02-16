from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Notificationbid
from Chats.models import Conversation
def send_real_time_notification(user, message):
    notification = Notificationbid.objects.create(
        recipient=user,
        message=message,
        bid=None
    )
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{user.id}",
        {
            "type": "send_notification",
            "message": message,
            "created_at": notification.created_at.strftime("%Y-%m-%d %H:%M:%S")  # ✅ Format timestamp
        }
    )


def start_conversation(seller,buyer,product):
    Conversation.objects.create(
        seller = seller,
        buyer = buyer,
        product = product
    )