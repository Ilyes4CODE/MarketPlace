from django.urls import path
from . import consumers
websocket_routes = [
    path("ws/chat/<int:conversation_id>/", consumers.ChatConsumer.as_asgi()),
]