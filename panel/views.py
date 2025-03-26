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
from Product.serializer import BidSerializer
from django.utils import timezone

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
    product = bid.product

    if action == "accept":
        bid.status = "accepted"
        bid.save()

        # Check if the bid amount meets or exceeds the buy now price
        if product.buy_now_price and bid.amount >= product.buy_now_price:
            product.closed = True
            product.closed_at = timezone.now()
            product.save()

            # Start a conversation between buyer and seller
            start_conversation(seller, buyer, product)

            # Send notifications
            send_real_time_notification(
                seller, f"تم بيع منتجك '{product.title}' بمبلغ {bid.amount} {product.currency}."
            )
            send_real_time_notification(
                buyer, f"تهانينا! لقد فزت بالمزاد على '{product.title}' بمبلغ {bid.amount} {product.currency}."
            )

        else:
            # Send normal acceptance notifications
            send_real_time_notification(
                seller, f"تم قبول المزايدة بقيمة {bid.amount} على منتجك: {product.title}."
            )
            send_real_time_notification(
                buyer, f"تهانينا! تم قبول مزايدتك على '{product.title}' بقيمة {bid.amount}."
            )

    elif action == "reject":
        bid.status = "rejected"
        bid.save()

        # Send rejection notification
        send_real_time_notification(
            buyer, f"عذرًا، تم رفض مزايدتك على '{product.title}' بقيمة {bid.amount}."
        )

    else:
        return Response({"error": "إجراء غير صالح"}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"message": f"تم { 'قبول' if action == 'accept' else 'رفض' } المزايدة بنجاح"})


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
def toggle_product_approval(request, product_id):
    try:
        product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist:
        return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

    product.is_approved = not product.is_approved
    product.save()

    if product.is_approved:
        send_real_time_notification(product.seller, "لقد تم قبول منتوجك بنجاح")
        message = "Product approved successfully!"
    else:
        send_real_time_notification(product.seller, "تم إلغاء الموافقة على منتوجك")
        message = "Product approval revoked!"

    return Response({'info': message}, status=status.HTTP_202_ACCEPTED)

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
    

@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
@admin_required
def delete_user(request, pk):

    try:
        market_user = MarketUser.objects.get(id=pk)
        user = market_user.profile  # Get the associated Django User

        # Prevent deleting admin users
        if user.groups.filter(name="Admin").exists():
            return Response({"error": "You cannot delete an admin user."}, status=status.HTTP_403_FORBIDDEN)

        user.delete()  # Deleting User will cascade-delete MarketUser
        return Response({"message": "User deleted successfully."}, status=status.HTTP_200_OK)

    except MarketUser.DoesNotExist:
        return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

@api_view(["GET"])
@permission_classes([IsAuthenticated])  # Require authentication
def get_bids(request):
    buyer_name = request.GET.get("buyer_name", "").strip()
    product_id = request.GET.get("product_id", "").strip()
    status_filter = request.GET.get("status", "").strip().lower()
    date_order = request.GET.get("date_order", "desc").strip().lower()  # Default: newest to oldest

    # Base query
    bids = Bid.objects.all()

    # Filter by buyer name (case-insensitive search)
    if buyer_name:
        bids = bids.filter(buyer__name__icontains=buyer_name)

    # Filter by product ID
    if product_id.isdigit():  # Ensure product_id is a valid number
        bids = bids.filter(product_id=product_id)

    # Filter by bid status
    if status_filter in ["pending", "accepted", "rejected"]:
        bids = bids.filter(status=status_filter)

    # Sorting by date (default: newest to oldest)
    if date_order == "asc":
        bids = bids.order_by("created_at")  # Oldest to newest
    else:
        bids = bids.order_by("-created_at")  # Newest to oldest (default)

    # Always keep "pending" bids at the top
    bids = sorted(bids, key=lambda x: x.status != "pending")

    # Serialize and return the response
    serializer = BidSerializer(bids, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)



