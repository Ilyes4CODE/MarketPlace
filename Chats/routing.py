from django.urls import path,re_path
from . import consumers
from Product.consumers import NotificationConsumer
websocket_routes = [
    path("ws/chat/<int:conversation_id>/", consumers.ChatConsumer.as_asgi()),
    path("ws/notifications/", consumers.NotificationConsumer.as_asgi()),
    path("ws/user_notifications/", NotificationConsumer.as_asgi()),
]