
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from Chats.routing import websocket_urlpatterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MarketPlace.settings')

# ProtocolTypeRouter manages the type of protocol (HTTP or WebSocket)
application = ProtocolTypeRouter({
    "http": get_asgi_application(),  # HTTP protocol
    "websocket": AuthMiddlewareStack(  # WebSocket with authentication
        URLRouter(
            websocket_urlpatterns  
        )
    ),
})

