from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from .serializer import MarketUserSerializer, UserSerializer,UpdateUserSerializer
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import MarketUser
from drf_yasg import openapi
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from twilio.rest import Client
import random
from django.core.cache import cache

@swagger_auto_schema(
    method='post',
    operation_description="Register a new user in the marketplace.",
    request_body=MarketUserSerializer,
    responses={
        status.HTTP_201_CREATED: openapi.Response(
            description="User registered successfully!",
            examples={
                "application/json": {
                    "message": "User registered successfully!",
                    "user": {
                        "id": 1,
                        "name": "John Doe",
                        "email": "johndoe@example.com",
                        "phone": "+123456789"
                    },
                    "tokens": {
                        "refresh": "your_refresh_token",
                        "access": "your_access_token"
                    }
                }
            }
        ),
        status.HTTP_400_BAD_REQUEST: openapi.Response(
            description="Bad request - Validation errors",
            examples={
                "application/json": {
                    "email": ["A user with this email already exists."],
                    "password": ["Ensure this field has at most 6 characters."]
                }
            }
        ),
    }
)
@api_view(['POST'])
def register_market_user(request):
    otp = request.data.get('otp')
    phone = request.data.get('phone')

    if not otp or not phone:
        return Response({"error": "Phone number and OTP are required."}, status=status.HTTP_400_BAD_REQUEST)

    # Retrieve OTP from cache
    stored_otp = cache.get(f"otp_{phone}")

    if stored_otp is None:
        return Response({"error": "OTP expired or not requested."}, status=status.HTTP_400_BAD_REQUEST)

    if stored_otp != otp:
        return Response({"error": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

    # OTP verified, proceed with registration
    serializer = MarketUserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user.profile)
        access = refresh.access_token

        # Delete OTP from cache after successful verification
        cache.delete(f"otp_{phone}")

        return Response({
            "message": "User registered successfully!",
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "phone": user.phone
            },
            "tokens": {
                "refresh": str(refresh),
                "access": str(access)
            }
        }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

@swagger_auto_schema(method='get',operation_description="get user profile", responses={status.HTTP_200_OK: "User profile retrieved successfully!"})
@permission_classes([IsAuthenticated])
@api_view(['GET'])
def get_user_profile(request):
    user = request.user
    try:
        market_user = MarketUser.objects.get(profile=user) 
    except MarketUser.DoesNotExist:
        return Response({"error": "MarketUser profile not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = UserSerializer(market_user)
    return Response(serializer.data)


@swagger_auto_schema(method='patch',operation_description="Updating User Profile", request_body=UpdateUserSerializer)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_user_profile(request):
    user = request.user
    try:
        market_user = MarketUser.objects.get(profile=user)  # Get the MarketUser instance
    except MarketUser.DoesNotExist:
        return Response({"error": "MarketUser profile not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = UpdateUserSerializer(market_user, data=request.data, partial=True)  # Allow partial updates
    if serializer.is_valid():
        serializer.save()  # Save the updated profile
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def send_otp(request):
    phone = request.data.get('phone')

    if not phone:
        return Response({"error": "Phone number is required."}, status=status.HTTP_400_BAD_REQUEST)
    otp = str(random.randint(100000, 999999))

    # Store OTP in cache with an expiration time (e.g., 5 minutes)
    cache.set(f"otp_{phone}", otp, timeout=300)  # 300 seconds = 5 minutes

    # Send OTP via Twilio
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=f"Your verification code is: {otp}",
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone
        )

        return Response({"message": "OTP sent successfully!"}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)