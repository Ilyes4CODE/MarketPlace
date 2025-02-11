from django.urls import path,re_path
from . import consumers
websocket_routes = [
    path("ws/chat/<int:conversation_id>/", consumers.ChatConsumer.as_asgi()),
    re_path(r"ws/notifications/$", consumers.NotificationConsumer.as_asgi()),
]