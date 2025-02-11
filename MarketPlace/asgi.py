# MarketPlace/asgi.py

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path
  # Import your WebSocket consumer
from channels.security.websocket import AllowedHostsOriginValidator
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MarketPlace.settings')
django_asgi_app = get_asgi_application()

from Chats import routing

application = ProtocolTypeRouter({
    "http": django_asgi_app,  # HTTP requests
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                routing.websocket_routes
            )
        )
    ),
})