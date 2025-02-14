from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from Product.models import Notificationbid
from .serializers import NotificationBidSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from Product.models import Bid, Notificationbid, MarketUser
from decorators import admin_required
from Auth.serializer import UserSerializer
from decorators import admin_required

class UserNotificationsView(ListAPIView):
    serializer_class = NotificationBidSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notificationbid.objects.filter(recipient=self.request.user.marketuser).order_by("-created_at")




@api_view(["POST"])
@permission_classes([IsAuthenticated])
@admin_required
def manage_bid(request, bid_id):
    bid = get_object_or_404(Bid, id=bid_id)
    action = request.data.get("action")  # "accept" or "reject"

    if action == "accept":
        bid.status = "accepted"
        message_seller = f"A new bid of {bid.amount} has been placed on your product: {bid.product.title}"
        message_buyer = f"Your bid of {bid.amount} has been accepted by the admin."
    elif action == "reject":
        bid.status = "rejected"
        message_buyer = f"Your bid of {bid.amount} has been rejected by the admin."
    else:
        return Response({"error": "Invalid action"}, status=400)

    bid.save()

    seller = MarketUser.objects.get(profile=bid.product.seller)  # Fetch seller as MarketUser
    Notificationbid.objects.create(user=seller, message=message_seller)

    Notificationbid.objects.create(user=bid.buyer, message=message_buyer)

    return Response({"message": f"Bid {action}ed successfully"})



@api_view(["GET"])
@permission_classes([IsAuthenticated])
@admin_required
def get_all_users(request):
    users = MarketUser.objects.all()
    serializer = UserSerializer(users, many=True)
    return Response(serializer.data)
    