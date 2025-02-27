from django.urls import path
from . import views

urlpatterns = [
    path('Notifications/', views.UserNotificationsView.as_view(), name='user-notifications'),
    path('manage_bid/<int:bid_id>/', views.manage_bid, name='manage-bid'),
    path('get_all_users/', views.get_all_users, name='get-all-users'),
    path('Accepte_product/<int:product_id>/',views.approve_products),
    path('delete_user/<int:pk>/',views.delete_user),
    path('ban_user/<int:pk>/',views.ban_and_unban_users)
]
