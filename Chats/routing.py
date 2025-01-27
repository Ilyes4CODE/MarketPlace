from django.urls import re_path,path
from .consumers import ConversationConsumer

websocket_urlpatterns = [
    path('conversation/<int:id>/', ConversationConsumer.as_asgi()),
]