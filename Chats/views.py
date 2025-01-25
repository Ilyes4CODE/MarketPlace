from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Conversation
from .serializer import ConversationSerializer, MessageSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_conversations(request):
    user = request.user.marketuser
    conversations = Conversation.objects.filter(seller=user) | Conversation.objects.filter(buyer=user)
    serializer = ConversationSerializer(conversations, many=True)
    return Response(serializer.data)


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

