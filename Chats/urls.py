from django.urls import path
from . import views

urlpatterns = [
    path('conversations/', views.list_conversations, name='list_conversations'),
    path('conversations/<int:conversation_id>/messages/', views.list_messages, name='list_messages'),
]