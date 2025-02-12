from django.urls import path
from . import views
from . import consumers
urlpatterns = [
    path('conversations/', views.list_conversations, name='list_conversations'),
    path('conversations/<int:conversation_id>/messages/', views.list_messages, name='list_messages'),
    path('start_conversation/<int:product_id>/', views.start_conversation, name='start_conversation'),
    path('conversations/<int:conversation_id>/mark_seen/', views.mark_messages_as_seen, name='mark_messages_as_seen'),
    path('notifications/', views.list_notifications, name='list_notifications'),

]   
