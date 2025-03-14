from django.urls import path
from rest_framework_simplejwt.views import  TokenRefreshView
from . import views
urlpatterns = [
    path('token/', views.CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', views.register_market_user, name='register'),
    path('profile/', views.get_user_profile, name='profile'),
    path('profile/update/', views.update_user_profile, name='update_profile'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path("info/", views.user_info, name="user-info"),
    path('request_update_phone/',views.request_phone_update),
    path('update_phone/',views.confirm_phone_update),
    path('update_profile_pic/',views.update_profile_picture),
    path('request_delete_account/',views.request_account_deletion),
    path('confirm_delete_account/',views.confirm_account_deletion),
    path('update-password/', views.update_password, name='update-password'),
]
