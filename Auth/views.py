from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from .serializer import MarketUserSerializer, UserSerializer,UpdateUserSerializer,CustomTokenObtainPairSerializer,UpdateProfilePictureSerializer,UpdatePhoneNumberSerializer,ConfirmPhoneUpdateSerializer
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import MarketUser,DeletedAccounts
from drf_yasg import openapi
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.cache import cache
import logging
from django.contrib.auth.models import Group
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
import re
from rest_framework_simplejwt.views import TokenObtainPairView
from Product.utils import send_real_time_notification

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
    phone = request.data.get('phone')
    email = request.data.get('email')
    name = request.data.get('name')
    password = request.data.get('password')
    if not all([phone, email, name, password]):
        return Response({"error": "رقم الهاتف، البريد الإلكتروني، الاسم، وكلمة المرور مطلوبة."}, status=status.HTTP_400_BAD_REQUEST)

    if not re.match(r'^\+\d{7,15}$', phone):
        return Response({"error": "تنسيق رقم الهاتف غير صحيح. يجب أن يبدأ بـ + متبوعًا بـ 7 إلى 15 رقمًا."}, status=status.HTTP_400_BAD_REQUEST)
    if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
        return Response({"error": "تنسيق البريد الإلكتروني غير صالح."}, status=status.HTTP_400_BAD_REQUEST)

    if len(password) != 6:
        return Response({"error": "يجب أن تتكون كلمة المرور من 6 أحرف بالضبط."}, status=status.HTTP_400_BAD_REQUEST)
    if MarketUser.objects.filter(phone=phone).exists():
        return Response({"error": "رقم الهاتف مسجل بالفعل."}, status=status.HTTP_302_FOUND)
    if MarketUser.objects.filter(email=email).exists():
        return Response({"error": "البريد الإلكتروني مسجل بالفعل."}, status=status.HTTP_302_FOUND)

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
    user_data = serializer.data
    user_data["id"] = user.id  # Replace MarketUser ID with User ID

    return Response(user_data)


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
        "is_admin": is_admin,
        "profile_picture" : market_user.profile_picture.url
    })
    

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


@swagger_auto_schema(
    method='post',
    operation_summary="تحديث صورة الملف الشخصي",
    operation_description="يتيح هذا الطلب للمستخدم تحديث صورة الملف الشخصي.",
    request_body=UpdateProfilePictureSerializer,
    responses={
        200: openapi.Response(
            description="تم تحديث صورة الملف الشخصي بنجاح",
            examples={"application/json": {"message": "تم تحديث صورة الملف الشخصي بنجاح."}}
        ),
        400: openapi.Response(
            description="خطأ في البيانات",
            examples={"application/json": {"error": "البيانات غير صحيحة."}}
        ),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_profile_picture(request):
    """
    تحديث صورة الملف الشخصي
    """
    user = request.user.marketuser
    serializer = UpdateProfilePictureSerializer(user, data=request.data, partial=True)

    if serializer.is_valid():
        serializer.save()
        return Response({"message": "تم تحديث صورة الملف الشخصي بنجاح."}, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    operation_summary="طلب تحديث رقم الهاتف",
    operation_description="يرسل هذا الطلب رقم الهاتف الجديد إلى الواجهة الأمامية للتحقق.",
    request_body=UpdatePhoneNumberSerializer,
    responses={
        200: openapi.Response(
            description="تم إرسال رقم الهاتف للتحقق",
            examples={"application/json": {"message": "تم إرسال رقم الهاتف الجديد للتحقق.", "phone": "+213123456789"}}
        ),
        400: openapi.Response(
            description="خطأ في البيانات",
            examples={"application/json": {"error": "رقم الهاتف مطلوب."}}
        ),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_phone_update(request):
    """
    طلب تحديث رقم الهاتف (إرسال للتحقق)
    """
    serializer = UpdatePhoneNumberSerializer(data=request.data)
    
    if serializer.is_valid():
        new_phone = serializer.validated_data['phone']
        
        # 👇 Send this phone number to the frontend for confirmation
        return Response({
            "message": "تم إرسال رقم الهاتف الجديد للتحقق.",
            "phone": new_phone
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='post',
    operation_summary="تأكيد تحديث رقم الهاتف",
    operation_description="يقوم هذا الطلب بتحديث رقم الهاتف في حالة الموافقة.",
    request_body=ConfirmPhoneUpdateSerializer,
    responses={
        200: openapi.Response(
            description="تم تحديث رقم الهاتف بنجاح",
            examples={"application/json": {"message": "تم تحديث رقم الهاتف بنجاح."}}
        ),
        400: openapi.Response(
            description="فشل التحقق",
            examples={"application/json": {"error": "لم يتم تأكيد رقم الهاتف الجديد."}}
        ),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirm_phone_update(request):
    user = request.user.marketuser
    serializer = ConfirmPhoneUpdateSerializer(data=request.data)

    if serializer.is_valid():
        if serializer.validated_data['status']:
            user.phone = serializer.validated_data['phone']
            user.save()
            return Response({"message": "تم تحديث رقم الهاتف بنجاح."}, status=status.HTTP_200_OK)
        else:
            return Response({"error": "لم يتم تأكيد رقم الهاتف الجديد."}, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='post',
    operation_summary="طلب حذف الحساب",
    operation_description="يرسل هذا الطلب إشعارًا يطلب تأكيد حذف الحساب.",
    responses={
        200: openapi.Response(
            description="تم إرسال طلب حذف الحساب بنجاح",
            examples={"application/json": {"message": "هل أنت متأكد أنك تريد حذف حسابك؟"}}
        ),
        400: openapi.Response(
            description="المستخدم غير مسجل الدخول",
            examples={"application/json": {"error": "يجب أن تكون مسجلاً للدخول لحذف حسابك."}}
        ),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_account_deletion(request):
    """
    طلب حذف الحساب (يجب التأكيد أولاً)
    """
    return Response({"message": "هل أنت متأكد أنك تريد حذف حسابك؟"}, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='post',
    operation_summary="تأكيد حذف الحساب",
    operation_description="يقوم هذا الطلب بحذف الحساب بشكل نهائي إذا تم التأكيد.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'confirm': openapi.Schema(type=openapi.TYPE_BOOLEAN, description="يجب أن يكون True لحذف الحساب")
        },
        required=['confirm']
    ),
    responses={
        200: openapi.Response(
            description="تم حذف الحساب بنجاح",
            examples={"application/json": {"message": "تم حذف حسابك بنجاح."}}
        ),
        400: openapi.Response(
            description="فشل تأكيد الحذف",
            examples={"application/json": {"error": "يجب تأكيد الحذف لإتمام العملية."}}
        ),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirm_account_deletion(request):
    """
    تأكيد حذف الحساب (يتم الحذف نهائيًا)
    """
    user = request.user
    market_user = user.marketuser

    if request.data.get("confirm") is True:
        # 🔔 Notify admins that this user has deleted their account
        admin_users = MarketUser.objects.filter(profile__groups__name="Admin")
        for admin in admin_users:
            send_real_time_notification(
                admin, 
                f"⚠️ تم حذف حساب المستخدم '{market_user.name}' ({user.username})"
            )
        DeletedAccounts.objects.create(email = market_user.email)
        user.delete()
        return Response({"message": "تم حذف حسابك بنجاح."}, status=status.HTTP_200_OK)
    
    return Response({"error": "يجب تأكيد الحذف لإتمام العملية."}, status=status.HTTP_400_BAD_REQUEST)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_password(request):
    """
    تحديث كلمة المرور بعد التحقق من كلمة المرور القديمة
    """
    user = request.user.marketuser  # يفترض أن MarketUser مرتبط بالمستخدم الحالي
    
    old_password = request.data.get("old_password")
    new_password = request.data.get("new_password")
    confirm_password = request.data.get("confirm_password")

    if not old_password or not new_password or not confirm_password:
        return Response({"error": "جميع الحقول مطلوبة"}, status=status.HTTP_400_BAD_REQUEST)

    if new_password != confirm_password:
        return Response({"error": "كلمتا المرور الجديدتان غير متطابقتين"}, status=status.HTTP_400_BAD_REQUEST)

    # التحقق من صحة كلمة المرور القديمة
    if not user.profile.check_password(old_password):
        return Response({"error": "كلمة المرور القديمة غير صحيحة"}, status=status.HTTP_400_BAD_REQUEST)

    # تحديث كلمة المرور الجديدة
    user.profile.set_password(new_password)
    user.profile.save()

    return Response({"message": "تم تحديث كلمة المرور بنجاح"}, status=status.HTTP_200_OK)