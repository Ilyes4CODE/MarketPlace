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
from Product.models import Product
from rest_framework import status
from Product.utils import send_real_time_notification,start_conversation

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
    seller = bid.product.seller
    buyer = bid.buyer

    if action == "accept":
        bid.status = "accepted"

        # 🚀 **Check if this bid meets/exceeds `buy_now_price`**
        if bid.amount >= bid.product.buy_now_price:
            bid.product.closed = True
            bid.product.sold = True
            bid.product.save()

            # Mark this bid as the winner and reject all others
            Bid.objects.filter(product=bid.product).update(status="rejected", winner=False)
            bid.winner = True
            bid.save()

            # 🔔 Now send notifications (delayed until admin approval)
            send_real_time_notification(seller, f"Your product '{bid.product.title}' has been sold for {bid.amount} {bid.product.currency}!")
            send_real_time_notification(buyer, f"Congratulations! You won the bid for '{bid.product.title}' at {bid.amount} {bid.product.currency}.")
            
            # Start the conversation between seller & buyer
            start_conversation(seller, buyer, bid.product)
        
        else:
            # Notify only about bid acceptance
            send_real_time_notification(seller, f"A new bid of {bid.amount} has been placed on your product: {bid.product.title}.")
            send_real_time_notification(buyer, f"Your bid of {bid.amount} has been accepted by the admin.")

    elif action == "reject":
        bid.status = "rejected"
        send_real_time_notification(buyer, f"Your bid of {bid.amount} has been rejected by the admin.")
    else:
        return Response({"error": "Invalid action"}, status=400)

    bid.save()
    return Response({"message": f"Bid {action}ed successfully"})



@api_view(["GET"])
@permission_classes([IsAuthenticated])
@admin_required
def get_all_users(request):
    """
    استرجاع جميع المستخدمين مع إمكانية البحث بالاسم
    """
    search_query = request.GET.get("search", "").strip()
    
    users = MarketUser.objects.exclude(profile__groups__name="Admin")

    if search_query:
        users = users.filter(name__icontains=search_query)

    serializer = UserSerializer(users, many=True)
    return Response(serializer.data)
    
@api_view(["POST"])
@permission_classes([IsAuthenticated])
# @admin_required
def approve_products(request,product_id):
    product = Product.objects.get(pk=product_id)
    if product.is_approved :
        return Response({'info':'already approved'},status=status.HTTP_404_NOT_FOUND)
    product.is_approved = True
    product.save()
    return Response({'info':'product approved successfully ! '},status=status.HTTP_202_ACCEPTED)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
@admin_required
def ban_and_unban_users(request,pk):
    try:
        user = MarketUser.objects.get(pk=pk)
        if user.is_banned == True:
            user.is_banned = False
            user.save()
            return Response({'info':'user unbaned successfully !'},status=status.HTTP_200_OK)
        elif user.is_banned == False:
            user.is_banned = True
            user.save()
            return Response({'info':'user banned successfully ! '},status=status.HTTP_200_OK)
    except MarketUser.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

