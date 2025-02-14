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
from firebase_admin import auth
from django.contrib.auth.models import User
import logging

def send_otp(phone):
    try:
        # Firebase Admin SDK sends the OTP and returns a verification_id
        appVerifier = auth.RecaptchaVerifier('recaptcha-container', size='invisible')
        confirmation_result = auth.sign_in_with_phone_number(phone, appVerifier)
        verification_id = confirmation_result.verification_id
        
        # Store the verification_id in cache with a 5-minute expiry
        cache.set(f"verification_id_{phone}", verification_id, timeout=300)
        return True
    except Exception as e:
        print(f"Error sending OTP: {e}")
        return False

phone_schema = openapi.Schema(type=openapi.TYPE_STRING, description="Phone number of the user")
email_schema = openapi.Schema(type=openapi.TYPE_STRING, description="Email of the user")
name_schema = openapi.Schema(type=openapi.TYPE_STRING, description="Name of the user")
password_schema = openapi.Schema(type=openapi.TYPE_STRING, description="Password for the user (should be stored securely)")

phone_schema2 = openapi.Schema(type=openapi.TYPE_STRING, description="Phone number of the user")
otp_schema = openapi.Schema(type=openapi.TYPE_STRING, description="One-Time Password (OTP) sent to the user's phone")
verification_id_schema = openapi.Schema(type=openapi.TYPE_STRING, description="Verification ID from Firebase")

@swagger_auto_schema(
    method='post',
    operation_description="Registers a new user and sends an OTP to the provided phone number. User data is temporarily stored in cache for OTP verification.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'phone': phone_schema,
            'email': email_schema,
            'name': name_schema,
            'password': password_schema,
        },
        required=['phone', 'email', 'name', 'password']
    ),
    responses={
        200: openapi.Response(
            description="OTP sent to the phone number. Please verify.",
            examples={
                "application/json": {
                    "message": "OTP sent to your phone number. Please verify."
                }
            }
        ),
        400: openapi.Response(
            description="Bad request. Missing required parameters.",
            examples={
                "application/json": {
                    "error": "Phone, email, name, and password are required."
                }
            }
        )
    }
)
@api_view(['POST'])
def register_market_user(request):
    # Get user data from the request
    phone = request.data.get('phone')
    email = request.data.get('email')
    name = request.data.get('name')
    password = request.data.get('password')

    if not phone or not email or not name or not password:
        return Response({"error": "Phone, email, name, and password are required."}, status=status.HTTP_400_BAD_REQUEST)

    # Save user data temporarily in cache before OTP verification
    user_data = {
        'phone': phone,
        'email': email,
        'name': name,
        'password': password
    }

    # Cache the user data with an expiration time (e.g., 5 minutes)
    cache.set(f"user_data_{phone}", user_data, timeout=300)

    # Optionally, you can also store the verification ID in cache if you need to use it during the OTP verification step
    return Response({"message": "OTP sent to your phone number. Please verify."}, status=status.HTTP_200_OK)


logger = logging.getLogger(__name__)


@swagger_auto_schema(
    method='post',
    operation_description="Verifies OTP and registers a new user.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'phone': phone_schema2,
            'otp': otp_schema,
            'verification_id': verification_id_schema
        },
        required=['phone', 'otp', 'verification_id']
    ),
    responses={
        201: openapi.Response(
            description="User successfully registered",
            examples={
                "application/json": {
                    "message": "User registered successfully!",
                    "user": {
                        "id": 1,
                        "name": "John Doe",
                        "email": "john.doe@example.com",
                        "phone": "1234567890"
                    },
                    "tokens": {
                        "refresh": "refresh_token_here",
                        "access": "access_token_here"
                    }
                }
            }
        ),
        400: openapi.Response(
            description="Bad request. Missing or invalid parameters.",
            examples={
                "application/json": {
                    "error": "Phone number, OTP, and verification_id are required."
                }
            }
        ),
        500: openapi.Response(
            description="Server error.",
            examples={
                "application/json": {
                    "error": "An error occurred during verification."
                }
            }
        )
    }
)
@api_view(['POST'])
def verify_otp(request):
    phone = request.data.get('phone')
    otp = request.data.get('otp')
    verification_id = request.data.get('verification_id')

    # Validate input
    if not otp or not phone or not verification_id:
        return Response({"error": "Phone number, OTP, and verification_id are required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Verify OTP with Firebase
        phone_credential = auth.PhoneAuthProvider.credential(verification_id, otp)
        user = auth.sign_in_with_credential(phone_credential)

        # Retrieve user data from cache
        user_data = cache.get(f"user_data_{phone}")
        if not user_data:
            return Response({"error": "No user data found."}, status=status.HTTP_400_BAD_REQUEST)

        # Create Django user
        django_user = User.objects.create_user(
            username=user_data['email'],  # Use email as username
            email=user_data['email'],
            password=user_data['password']
        )

        # Create MarketUser profile
        market_user = MarketUser.objects.create(
            profile=django_user,
            name=user_data['name'],
            phone=phone,
            email=user_data['email'],
            is_verified = True
        )

        # Generate JWT tokens
        refresh = RefreshToken.for_user(django_user)
        access = refresh.access_token

        # Clean up the cached data
        cache.delete(f"verification_id_{phone}")
        cache.delete(f"user_data_{phone}")

        # Return response with user info and tokens
        return Response({
            "message": "User registered successfully!",
            "user": {
                "id": market_user.id,
                "name": market_user.name,
                "email": market_user.email,
                "phone": market_user.phone
            },
            "tokens": {
                "refresh": str(refresh),
                "access": str(access)
            }
        }, status=status.HTTP_201_CREATED)

    except auth.FirebaseError as e:
        logger.error(f"Firebase OTP verification failed: {str(e)}")
        return Response({"error": f"OTP verification failed: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error during user verification: {str(e)}")
        return Response({"error": "An error occurred during verification."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




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


