from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Conversation, Message, Notification
from .serializer import ConversationSerializer, MessageSerializer, NotificationSerializer
from Product.models import Product
from rest_framework import status

@swagger_auto_schema(
    method="post",
    operation_description="Mark all messages in a conversation as seen by the user.",
    responses={200: openapi.Response("Messages marked as seen")}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_messages_as_seen(request, conversation_id):
    user = request.user.marketuser

    Message.objects.filter(
        conversation_id=conversation_id,
        conversation__buyer=user 
    ).update(seen=True)

    Message.objects.filter(
        conversation_id=conversation_id,
        conversation__seller=user 
    ).update(seen=True)

    return Response({"message": "Messages marked as seen"}, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method="get",
    operation_description="Retrieve a list of conversations involving the authenticated user.",
    responses={200: ConversationSerializer(many=True)}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_conversations(request):
    user = request.user.marketuser
    conversations = Conversation.objects.filter(seller=user) | Conversation.objects.filter(buyer=user)
    serializer = ConversationSerializer(conversations, many=True)
    return Response(serializer.data)


@swagger_auto_schema(
    method="get",
    operation_description="Retrieve all messages from a specific conversation.",
    responses={
        200: MessageSerializer(many=True),
        404: openapi.Response("Conversation not found")
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_messages(request, conversation_id):
    try:
        conversation = Conversation.objects.get(id=conversation_id)
    except Conversation.DoesNotExist:
        return Response({"error": "Conversation not found"}, status=404)

    messages = conversation.messages.all()
    serializer = MessageSerializer(messages, many=True)
    return Response(serializer.data)


@swagger_auto_schema(
    method="get",
    operation_description="Retrieve a list of unread notifications for the authenticated user.",
    responses={200: NotificationSerializer(many=True)}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_notifications(request):
    user = request.user.marketuser
    notifications = Notification.objects.filter(user=user, is_read=False)  # Fetch unread notifications
    serializer = NotificationSerializer(notifications, many=True)
    return Response(serializer.data)


@swagger_auto_schema(
    method="post",
    operation_description="Start a conversation between the authenticated buyer and a product's seller.",
    responses={
        201: ConversationSerializer(),
        200: ConversationSerializer(),
        404: openapi.Response("Product not found")
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_conversation(request, product_id):
    """
    Start a new conversation between the authenticated user (buyer) and a seller
    for a specific product. If a conversation already exists, return it.
    """
    buyer = request.user.marketuser  # The authenticated user is the buyer

    try:
        product = Product.objects.get(id=product_id)
        seller = product.seller  # The product owner is the seller
    except Product.DoesNotExist:
        return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)

    # Check if the conversation already exists or create a new one
    conversation, created = Conversation.objects.get_or_create(
        seller=seller,
        buyer=buyer,
        product=product
    )

    serializer = ConversationSerializer(conversation)

    return Response({
        "conversation": serializer.data,
    }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
