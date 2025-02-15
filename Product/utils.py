from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Notificationbid

def send_real_time_notification(user, message):
    """
    Sends a real-time notification to a specific user via WebSockets and saves it in the database.
    """
    # Save notification to the database
    Notificationbid.objects.create(
        recipient=user,
        message=message,
        bid=None
    )

    # Send real-time notification via WebSockets
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{user.id}",
        {
            "type": "send_notification",
            "message": message
        }
    )