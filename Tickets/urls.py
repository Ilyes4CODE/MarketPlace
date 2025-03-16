from django.urls import path
from .views import add_predefined_message, delete_predefined_message, get_user_tickets,TicketCreateView
from . import views
urlpatterns = [
    path('predefined-messages/add/', add_predefined_message, name='add_predefined_message'),
    path('predefined-messages/delete/<int:pk>/', delete_predefined_message, name='delete_predefined_message'),
    path('predefined-messages/Update/<int:pk>/',views.update_predefined_message),
    path('predefined-messages/Get/',views.get_predefined_messages),
    path('tickets/', get_user_tickets, name='get_user_tickets'),
    path('create/', TicketCreateView.as_view(), name='ticket-create'),
]
