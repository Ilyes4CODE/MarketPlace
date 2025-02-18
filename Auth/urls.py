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
]
