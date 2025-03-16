from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .models import PredefinedMessage, Ticket
from .serializers import PredefinedMessageSerializer, TicketSerializer
from rest_framework import  permissions
from Auth.models import MarketUser
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from decorators import admin_required
# ✅ Admin: Add predefined message
# ✅ Admin: Add a predefined message (Max 3 messages)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@admin_required
def add_predefined_message(request):
    if PredefinedMessage.objects.count() >= 3:
        return Response({'error': 'Cannot add more than 3 predefined messages.'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = PredefinedMessageSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ✅ Admin: Update a predefined message
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
@admin_required
def update_predefined_message(request, pk):
    try:
        message = PredefinedMessage.objects.get(pk=pk)
    except PredefinedMessage.DoesNotExist:
        return Response({'error': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)

    serializer = PredefinedMessageSerializer(message, data=request.data, partial=True)  # Partial allows updating only some fields
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ✅ Admin: Delete a predefined message
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@admin_required
def delete_predefined_message(request, pk):
    try:
        message = PredefinedMessage.objects.get(pk=pk)
        message.delete()
        return Response({'info': 'Deleted'}, status=status.HTTP_204_NO_CONTENT)
    except PredefinedMessage.DoesNotExist:
        return Response({'error': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([IsAuthenticated])# Anyone can fetch predefined messages
def get_predefined_messages(request):
    messages = PredefinedMessage.objects.all()
    serializer = PredefinedMessageSerializer(messages, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

# ✅ Get all tickets for the authenticated user (Admin/User)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_tickets(request):
    user = request.user.marketuser  # Get MarketUser from logged-in User
    
    # 🔍 Check if user is in the "Admin" group
    is_admin = request.user.groups.filter(name="Admin").exists()

    if is_admin:  
        tickets = Ticket.objects.all()  # Admin sees all tickets
    else:
        tickets = Ticket.objects.filter(user=user)  # Regular user sees only their own tickets

    serializer = TicketSerializer(tickets, many=True)
    return Response(serializer.data)


class TicketCreateView(generics.CreateAPIView):
    """Allows users to create a support ticket."""
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        print(self.request.user)
        user = MarketUser.objects.get(profile=self.request.user)
        ticket = serializer.save(user=user)

        # Broadcast the new ticket via WebSockets
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "admin_tickets",
            {
                "type": "ticket.created",  # Custom WebSocket event
                "ticket": {
                    "id": ticket.id,
                    "subject": ticket.subject,
                    "status": ticket.status,
                    "user": ticket.user.profile.username,
                    "created_at": ticket.created_at.strftime("%Y-%m-%d %H:%M"),
                }
            }
        )