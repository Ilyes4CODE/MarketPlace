from django.urls import path
from .views import add_predefined_message, delete_predefined_message, get_user_tickets,TicketCreateView

urlpatterns = [
    path('predefined-messages/add/', add_predefined_message, name='add_predefined_message'),
    path('predefined-messages/delete/<int:pk>/', delete_predefined_message, name='delete_predefined_message'),
    path('tickets/', get_user_tickets, name='get_user_tickets'),
    path('create/', TicketCreateView.as_view(), name='ticket-create'),
]
