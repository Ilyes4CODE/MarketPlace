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
from django.core.cache import cache
import logging
from django.contrib.auth.models import Group
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
import re

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
def register_market_user(request):
    # Get user data from the request
    phone = request.data.get('phone')
    email = request.data.get('email')
    name = request.data.get('name')
    password = request.data.get('password')

    # Basic validation
    if not all([phone, email, name, password]):
        return Response({"error": "رقم الهاتف، البريد الإلكتروني، الاسم، وكلمة المرور مطلوبة."}, status=status.HTTP_400_BAD_REQUEST)

    # Validate phone number format (supports international numbers starting with +)
    if not re.match(r'^\+\d{7,15}$', phone):
        return Response({"error": "تنسيق رقم الهاتف غير صحيح. يجب أن يبدأ بـ + متبوعًا بـ 7 إلى 15 رقمًا."}, status=status.HTTP_400_BAD_REQUEST)

    # Validate email format
    if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
        return Response({"error": "تنسيق البريد الإلكتروني غير صالح."}, status=status.HTTP_400_BAD_REQUEST)

    # Validate password length (exactly 6 characters)
    if len(password) != 6:
        return Response({"error": "يجب أن تتكون كلمة المرور من 6 أحرف بالضبط."}, status=status.HTTP_400_BAD_REQUEST)

    # Check if phone number already exists
    if MarketUser.objects.filter(phone=phone).exists():
        return Response({"error": "رقم الهاتف مسجل بالفعل."}, status=status.HTTP_302_FOUND)

    # Check if email already exists
    if MarketUser.objects.filter(email=email).exists():
        return Response({"error": "البريد الإلكتروني مسجل بالفعل."}, status=status.HTTP_302_FOUND)

    # Save user data temporarily in cache before OTP verification
    user_data = {
        'phone': phone,
        'email': email,
        'name': name,
        'password': password
    }

    cache.set(f"user_data_{phone}", user_data, timeout=300)

    return Response({"message": "تم إرسال رمز التحقق إلى رقم هاتفك. يرجى التحقق."}, status=status.HTTP_200_OK)


logger = logging.getLogger(__name__)
@swagger_auto_schema(
    method='post',
    operation_description="تحقق من حالة رقم الهاتف وإنشاء حساب مستخدم في النظام.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['status', 'phone'],
        properties={
            'status': openapi.Schema(
                type=openapi.TYPE_BOOLEAN,
                description="حالة التحقق من OTP. يجب أن يكون 'True' في حالة النجاح."
            ),
            'phone': openapi.Schema(
                type=openapi.TYPE_STRING,
                description="رقم الهاتف الخاص بالمستخدم."
            )
        }
    ),
    responses={
        201: openapi.Response(
            description="تم تسجيل المستخدم بنجاح.",
            examples={
                "application/json": {
                    "status": True,
                    "message": "تم تسجيل المستخدم بنجاح!",
                    "user": {
                        "id": 1,
                        "name": "محمد أحمد",
                        "email": "user@example.com",
                        "phone": "+201234567890"
                    },
                    "tokens": {
                        "refresh": "eyJhbGciOiJIUzI1NiIsIn...",
                        "access": "eyJhbGciOiJIUzI1NiIsIn..."
                    }
                }
            }
        ),
        400: openapi.Response(
            description="خطأ في الطلب. تحقق من القيم المرسلة.",
            examples={
                "application/json": {
                    "status": False,
                    "error": "لم يتم العثور على بيانات المستخدم."
                }
            }
        ),
        500: openapi.Response(
            description="خطأ داخلي في الخادم.",
            examples={
                "application/json": {
                    "status": False,
                    "error": "حدث خطأ أثناء معالجة الطلب."
                }
            }
        ),
    }
)
@api_view(['POST'])
def verify_otp(request):
    status_flag = request.data.get('status')  # ✅ Frontend sends 'status' (true/false)
    phone = request.data.get('phone')  # ✅ Phone is still required to fetch user data

    if status_flag is None or phone is None:
        return Response({"status": False, "error": "يجب إرسال الحالة ورقم الهاتف."}, status=status.HTTP_400_BAD_REQUEST)

    if not isinstance(status_flag, bool):
        return Response({"status": False, "error": "القيمة المرسلة للحالة غير صحيحة."}, status=status.HTTP_400_BAD_REQUEST)

    if not status_flag:
        return Response({"status": False, "error": "فشل التحقق من رقم الهاتف."}, status=status.HTTP_400_BAD_REQUEST)

    # ✅ Fetch user data from cache
    user_data = cache.get(f"user_data_{phone}")
    if not user_data:
        return Response({"status": False, "error": "لم يتم العثور على بيانات المستخدم."}, status=status.HTTP_400_BAD_REQUEST)

    # ✅ Validate and create user using MarketUserSerializer
    serializer = MarketUserSerializer(data=user_data)
    if not serializer.is_valid():
        return Response({"status": False, "error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    market_user = serializer.save()
    
    refresh = RefreshToken.for_user(market_user.profile)
    access = refresh.access_token
    cache.delete(f"user_data_{phone}")

    return Response({
        "status": True,
        "message": "تم تسجيل المستخدم بنجاح!",
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



@api_view(['GET'])
@login_required
def user_info(request):
    """Returns authenticated user details, including group membership."""
    user = request.user
    market_user = MarketUser.objects.get(profile=user)

    # Check if the user is in the admin group
    is_admin = user.groups.filter(name="Admin").exists()
    return Response({
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_admin": is_admin
    })
    

