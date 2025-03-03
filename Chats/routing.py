from django.urls import path,re_path
from . import consumers
from Product.consumers import NotificationConsumer
from panel.consumers import MarketplaceStatsConsumer
from Tickets.consumers import TicketChatConsumer,AdminTicketConsumer
websocket_routes = [
    path("ws/chat/<int:conversation_id>/", consumers.ChatConsumer.as_asgi()),
    path("ws/notifications/", consumers.NotificationConsumer.as_asgi()),
    path("ws/user_notifications/", NotificationConsumer.as_asgi()),
    path("ws/Stats/",MarketplaceStatsConsumer.as_asgi()),
    re_path(r'ws/ticket/(?P<ticket_id>\d+)/$', TicketChatConsumer.as_asgi()),
    re_path(r'ws/admin/tickets/$', AdminTicketConsumer.as_asgi()),
]