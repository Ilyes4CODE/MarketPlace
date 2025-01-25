from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from .serializer import MarketUserSerializer, UserSerializer,UpdateUserSerializer
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import MarketUser

@swagger_auto_schema(method='post',operation_description="Register a new user in the market place.", request_body=MarketUserSerializer,responses={status.HTTP_201_CREATED: "User registered successfully!", status.HTTP_400_BAD_REQUEST: "Bad request"})
@api_view(['POST'])
def register_market_user(request):
    if request.method == 'POST':
        serializer = MarketUserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "User registered successfully!"}, status=status.HTTP_201_CREATED)
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

