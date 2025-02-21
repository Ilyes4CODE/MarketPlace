from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from .models import Product, ProductPhoto, Bid,Notificationbid,Listing
from .serializer import ProductSerializer, ProductPhotoSerializer, BidSerializer
from django.shortcuts import get_object_or_404
from decorators import verified_user_required ,not_banned_user_required
from .utils import send_real_time_notification,start_conversation
from datetime import timedelta  
from django.utils import timezone  
from .models import Category
from django.db.models import Max
from Auth.models import MarketUser
@swagger_auto_schema(
    method='post',
    operation_description="Create a new bid product",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['title', 'description', 'starting_price', 'buy_now_price', 'duration', 'condition', 'location', 'currency'],
        properties={
            'title': openapi.Schema(type=openapi.TYPE_STRING, description="Name of the product"),
            'description': openapi.Schema(type=openapi.TYPE_STRING, description="Detailed description of the product"),
            'starting_price': openapi.Schema(type=openapi.TYPE_NUMBER, format=openapi.FORMAT_DECIMAL, description="Initial bidding price"),
            'buy_now_price': openapi.Schema(type=openapi.TYPE_NUMBER, format=openapi.FORMAT_DECIMAL, description="Price to buy instantly"),
            'duration': openapi.Schema(type=openapi.TYPE_INTEGER, description="Duration of the bid in hours"),
            'condition': openapi.Schema(type=openapi.TYPE_STRING, enum=['new', 'used'], description="Product condition"),
            'location': openapi.Schema(type=openapi.TYPE_STRING, description="Product location"),
            'currency': openapi.Schema(type=openapi.TYPE_STRING, enum=['USD', 'LBP'], description="Currency (USD or LBP)"),
            'photos': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_STRING, format=openapi.FORMAT_BINARY), description="Product photos"),
        },
    ),
    responses={
        201: openapi.Response("Product created successfully", ProductSerializer),
        400: "Bad Request - Missing or invalid fields",
        401: "Unauthorized - User not authenticated",
        403: "Forbidden - User not verified or banned",
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@verified_user_required
@not_banned_user_required
def create_bid_product(request):
    seller = request.user.marketuser
    data = request.data

    # Ensure this is a bid
    data['sale_type'] = 'bid'

    # Validate required fields for a bid
    required_fields = ['starting_price', 'duration']
    for field in required_fields:
        if field not in data or not data[field]:
            return Response({field: "This field is required for bid products."}, status=status.HTTP_400_BAD_REQUEST)

    product_serializer = ProductSerializer(data=data, context={'seller': seller})
    if product_serializer.is_valid():
        product = product_serializer.save(seller=seller)
        product.bid_end_time = timezone.now() + timedelta(hours=int(data['duration']))
        product.save()

        # Save uploaded photos
        photos = request.FILES.getlist('photos')
        for photo in photos:
            ProductPhoto.objects.create(product=product, photo=photo)

        return Response(product_serializer.data, status=status.HTTP_201_CREATED)

    return Response(product_serializer.errors, status=status.HTTP_400_BAD_REQUEST)





@swagger_auto_schema(
    method='post',
    operation_description="Create a new simple product (non-bidding product).",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['title', 'description', 'price', 'condition', 'location', 'currency', 'category'],
        properties={
            'title': openapi.Schema(type=openapi.TYPE_STRING, description="Name of the product"),
            'description': openapi.Schema(type=openapi.TYPE_STRING, description="Detailed description of the product"),
            'price': openapi.Schema(type=openapi.TYPE_NUMBER, format=openapi.FORMAT_DECIMAL, description="Price of the product"),
            'condition': openapi.Schema(type=openapi.TYPE_STRING, enum=['new', 'used'], description="Product condition"),
            'location': openapi.Schema(type=openapi.TYPE_STRING, description="Product location"),
            'currency': openapi.Schema(type=openapi.TYPE_STRING, enum=['USD', 'LBP'], description="Currency (USD or LBP)"),
            'category': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID of the product category"),
            'photos': openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Items(type=openapi.TYPE_STRING, format=openapi.FORMAT_BINARY),
                description="Array of product photos (optional)"
            ),
        },
    ),
    responses={
        201: openapi.Response("Product created successfully", ProductSerializer),
        400: "Bad Request - Missing or invalid fields",
        401: "Unauthorized - User not authenticated",
        403: "Forbidden - User not verified or banned",
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@verified_user_required
@not_banned_user_required
def create_simple_product(request):
    seller = request.user.marketuser
    data = request.data.copy()  # Create a mutable copy of request.data

    data['sale_type'] = 'simple'
    
    try:
        category = Category.objects.get(pk=data['category'])
    except Category.DoesNotExist:
        return Response({"category": "Invalid category ID."}, status=status.HTTP_400_BAD_REQUEST)

    if 'price' not in data or not data['price']:
        return Response({"price": "Price is required for simple products."}, status=status.HTTP_400_BAD_REQUEST)

    product_serializer = ProductSerializer(data=data, context={'seller': seller, 'category': category})

    if product_serializer.is_valid():
        product = product_serializer.save(seller=seller)
        photos = request.FILES.getlist('photos')

        for photo in photos:
            ProductPhoto.objects.create(product=product, photo=photo)

        return Response(product_serializer.data, status=status.HTTP_201_CREATED)

    return Response(product_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@verified_user_required
@not_banned_user_required
def place_bid(request, product_id):
    # Get the product and ensure it’s a bid product
    product = Product.objects.filter(id=product_id, sale_type='bid', is_approved=True).first()
    if not product:
        return Response({"error": "Product not available for bidding."}, status=status.HTTP_404_NOT_FOUND)

    # Prevent the seller from bidding on their own product
    if product.seller == request.user.marketuser:
        return Response({"error": "You cannot bid on your own product."}, status=status.HTTP_400_BAD_REQUEST)

    # Check if bidding has ended
    if product.closed or (product.bid_end_time and timezone.now() >= product.bid_end_time):
        product.closed = True
        product.save()
        return Response({"error": "Bidding for this product has ended."}, status=status.HTTP_400_BAD_REQUEST)

    # Get the bid amount
    bid_amount = request.data.get("amount")
    if not bid_amount:
        return Response({"error": "Bid amount is required."}, status=status.HTTP_400_BAD_REQUEST)

    bid_amount = float(bid_amount)

    # Get the highest accepted bid (or starting price if no bids exist)
    highest_bid = Bid.objects.filter(product=product, status="accepted").aggregate(Max('amount'))['amount__max'] or product.starting_price
    if bid_amount <= highest_bid:
        return Response({"error": f"Your bid must be higher than {highest_bid} {product.currency}."}, status=status.HTTP_400_BAD_REQUEST)

    # Create the new bid with `pending` status (Admin will approve)
    bid = Bid.objects.create(
        product=product,
        buyer=request.user.marketuser,
        amount=bid_amount,
        status="pending"  # Pending approval
    )

    # Notify admins for bid approval
    admin_users = MarketUser.objects.filter(profile__groups__name="Admin")
    for admin in admin_users:
        send_real_time_notification(admin, f"New bid of {bid_amount} {product.currency} placed on '{product.title}'. Please review and approve.")

    return Response({"message": "Bid placed successfully and is pending admin approval.", "bid": BidSerializer(bid).data}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@verified_user_required
@not_banned_user_required
def end_bid(request, product_id, bid_id):
    seller = request.user.marketuser

    try:
        # Ensure the product exists and belongs to the seller
        product = Product.objects.get(id=product_id, seller=seller, sale_type='bid')
    except Product.DoesNotExist:
        return Response({"error": "Product not found or you do not have permission to end the bid."}, status=status.HTTP_404_NOT_FOUND)

    if not bid_id:
        return Response({"error": "No bid_id provided. Please select a bid to end the auction."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Retrieve the selected bid and ensure it's an approved bid
        selected_bid = Bid.objects.get(id=bid_id, product=product, status="accepted")
    except Bid.DoesNotExist:
        return Response({"error": "Selected bid not found, not approved, or does not belong to this product."}, status=status.HTTP_404_NOT_FOUND)

    # Mark the selected bid as the winner
    selected_bid.winner = True
    selected_bid.save()

    # Mark the product as sold and closed
    product.sold = True
    product.closed = True
    product.save()

    # Reject all other bids for this product
    Bid.objects.filter(product=product).exclude(id=selected_bid.id).update(status="rejected", winner=False)

    # 🔔 Notify the winner
    send_real_time_notification(
        selected_bid.buyer, 
        f"🎉 Congratulations! Your bid of {selected_bid.amount} {product.currency} on '{product.title}' has won."
    )

    # 🔔 Notify the seller
    send_real_time_notification(
        product.seller, 
        f"✅ You have successfully sold '{product.title}' for {selected_bid.amount} {product.currency}."
    )

    # 💬 Start a conversation between the seller and the winner
    start_conversation(product.seller, selected_bid.buyer, product)

    # 🔍 Find all admin users
    admin_users = MarketUser.objects.filter(user__groups__name="Admin")

    # 🔔 Notify admins that the bid has ended
    for admin in admin_users:
        send_real_time_notification(
            admin, 
            f"📢 Auction for '{product.title}' has ended. Winning bid: {selected_bid.amount} {product.currency}."
        )

    return Response({
        "message": "Bidding ended successfully.",
        "winning_bid": BidSerializer(selected_bid).data
    }, status=status.HTTP_200_OK)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
@verified_user_required
@not_banned_user_required
def seller_products_history(request):
    """
    Retrieve all products listed by the authenticated seller.
    """
    seller = request.user.marketuser
    products = Product.objects.filter(seller=seller).order_by('-created_at')

    if not products.exists():
        return Response({"message": "No products found."}, status=status.HTTP_404_NOT_FOUND)

    return Response(ProductSerializer(products, many=True).data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@verified_user_required
@not_banned_user_required
def product_bids_history(request, product_id):
    
    seller = request.user.marketuser

    try:
        product = Product.objects.get(id=product_id, seller=seller, sale_type='bid')
    except Product.DoesNotExist:
        return Response({"error": "Product not found or you do not have permission to view bids."}, status=status.HTTP_404_NOT_FOUND)

    bids = Bid.objects.filter(product=product).order_by('-amount')

    if not bids.exists():
        return Response({"message": "No bids placed on this product yet."}, status=status.HTTP_404_NOT_FOUND)

    return Response(BidSerializer(bids, many=True).data, status=status.HTTP_200_OK)



@swagger_auto_schema(
    method='get',
    operation_description="Retrieve all bids for a specific product.",
    responses={
        200: openapi.Response('List of bids', BidSerializer(many=True)),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@verified_user_required
@not_banned_user_required
def get_product_bids(request, product_id):
    try:
        product = Product.objects.get(id=product_id, seller=request.user.marketuser)
    except Product.DoesNotExist:
        return Response({"error": "Product not found or you do not have permission to view its bids."}, status=status.HTTP_404_NOT_FOUND)

    bids = Bid.objects.filter(product=product).order_by('-amount')
    serializer = BidSerializer(bids, many=True)
    return Response(serializer.data)


# Other existing views like delete_product, update_product, etc., remain unchanged.

class ProductPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

@swagger_auto_schema(
    method='get',
    operation_description="Retrieve all approved products with optional filtering by sale type, category, price range, and title.",
    manual_parameters=[
        openapi.Parameter('sale_type', openapi.IN_QUERY, description="Sale type (simple/bid)", type=openapi.TYPE_STRING),
        openapi.Parameter('category', openapi.IN_QUERY, description="Category name to filter products", type=openapi.TYPE_STRING),
        openapi.Parameter('min_price', openapi.IN_QUERY, description="Minimum price to filter products", type=openapi.TYPE_NUMBER),
        openapi.Parameter('max_price', openapi.IN_QUERY, description="Maximum price to filter products", type=openapi.TYPE_NUMBER),
        openapi.Parameter('title', openapi.IN_QUERY, description="Search for products by title (case-insensitive)", type=openapi.TYPE_STRING),
    ],
    responses={
        200: openapi.Response('Paginated list of products', ProductSerializer(many=True)),
    }
)

@api_view(['GET'])
def list_products(request):
    sale_type = request.query_params.get('sale_type', None)
    category = request.query_params.get('category', None)
    min_price = request.query_params.get('min_price', None)
    max_price = request.query_params.get('max_price', None)
    title = request.query_params.get('title', None)

    products = Product.objects.filter(is_approved=True,sold=False)
    if sale_type:
        products = products.filter(sale_type=sale_type)
    if category:
        products = products.filter(category__name__icontains=category)
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)
    if title:
        products = products.filter(title__icontains=title)

    # Paginate results
    paginator = ProductPagination()
    result_page = paginator.paginate_queryset(products, request)
    serializer = ProductSerializer(result_page, many=True)
    return paginator.get_paginated_response(serializer.data)



@swagger_auto_schema(
    method='patch',
    operation_description="Partially update a product. Only the seller of the product can update it.",
    request_body=ProductSerializer,
    responses={
        200: openapi.Response('Product updated successfully', ProductSerializer),
        400: openapi.Response('Invalid data provided'),
        404: openapi.Response('Product not found or you do not have permission to edit it'),
    }
)
@api_view(['PUT', 'PATCH'])  
@permission_classes([IsAuthenticated])
@verified_user_required
@not_banned_user_required
def update_product(request, product_id):
    seller = request.user.marketuser  

    try:
        product = Product.objects.get(id=product_id, seller=seller)  # Ensure the seller owns the product
    except Product.DoesNotExist:
        return Response({"error": "Product not found or you do not have permission to edit it"}, status=status.HTTP_404_NOT_FOUND)

    data = request.data
    product_serializer = ProductSerializer(product, data=data, partial=True)  # Enable partial updates
    if product_serializer.is_valid():
        product_serializer.save()
        return Response(product_serializer.data)
    return Response(product_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='delete',
    operation_description="Delete a product. Only the seller of the product can delete it.",
    responses={
        200: openapi.Response('Product deleted successfully'),
        404: openapi.Response('Product not found or you do not have permission to delete it'),
    }
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@verified_user_required
@not_banned_user_required
def delete_product(request, product_id):
    seller = request.user.marketuser  # Ensure the user is the seller
    try:
        product = Product.objects.get(id=product_id, seller=seller)
    except Product.DoesNotExist:
        return Response({"error": "Product not found or you do not have permission to delete it."}, status=status.HTTP_404_NOT_FOUND)

    product.delete()
    return Response({"message": "Product deleted successfully."}, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='get',
    operation_description="Retrieve all products listed by the authenticated seller.",
    responses={
        200: openapi.Response('List of seller products', ProductSerializer(many=True)),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@verified_user_required
@not_banned_user_required
def get_seller_products(request):
    seller = request.user.marketuser
    products = Product.objects.filter(seller=seller).order_by('-upload_date')
    serializer = ProductSerializer(products, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
@verified_user_required
@not_banned_user_required
def purchase_product(request, product_id):
    buyer = request.user.marketuser  # Authenticated user

    # Get the product
    product = get_object_or_404(Product, id=product_id, sale_type='simple')

    # Prevent the seller from purchasing their own product
    if product.seller == buyer:
        return Response({"error": "You cannot purchase your own product."}, status=status.HTTP_400_BAD_REQUEST)

    # Ensure the product is available for sale
    if product.sold:
        return Response({"error": "This product has already been sold."}, status=status.HTTP_400_BAD_REQUEST)

    # Create a new listing
    listing = Listing.objects.create(
        buyer=buyer,
        product=product,
        quantity=1,  # Assuming it's a single-unit purchase
        is_payed=False  # Payment is not yet confirmed
    )

    # Notify the seller
    seller_message = f"Your product '{product.title}' has been requested for purchase by {buyer.profile.username}."
    Notificationbid.objects.create(
        recipient=product.seller,
        message=seller_message,
        bid=None  # Since this isn't a bid-related notification
    )

    send_real_time_notification(product.seller, seller_message)
    return Response({
        "message": "Purchase request sent successfully.",
        "listing_id": listing.id
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@verified_user_required
@not_banned_user_required
def accept_related_listings(request, listing_id):
    listing = get_object_or_404(Listing, id=listing_id)

    if listing.product.seller != request.user.marketuser:
        return Response({"error": "You are not authorized to mark this listing as paid."}, status=status.HTTP_403_FORBIDDEN)
    listing.is_payed = True
    listing.save()
    message = f"Your payment for '{listing.product.title}' has been confirmed by the seller."
    send_real_time_notification(listing.buyer, message)

    return Response({"message": "Listing marked as paid successfully."}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@verified_user_required
@not_banned_user_required
def get_seller_listings(request):
    """Get all listings where the user is the seller (to approve payment)."""
    user = request.user.marketuser  # Get the authenticated MarketUser

    # Get listings where the user is the seller
    seller_listings = Listing.objects.filter(product__seller=user).select_related("product", "buyer")

    listings_data = [
        {
            "id": listing.id,
            "product": listing.product.title,
            "buyer": listing.buyer.profile.username,
            "purchase_date": listing.purchase_date,
            "quantity": listing.quantity,
            "is_payed": listing.is_payed
        }
        for listing in seller_listings
    ]

    return Response({"seller_listings": listings_data}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@verified_user_required
@not_banned_user_required
def get_buyer_purchases(request):
    """Get all listings where the user is the buyer (to see purchases)."""
    user = request.user.marketuser  # Get the authenticated MarketUser

    # Get listings where the user is the buyer
    buyer_listings = Listing.objects.filter(buyer=user).select_related("product")

    listings_data = [
        {
            "id": listing.id,
            "product": listing.product.title,
            "seller": listing.product.seller.profile.username,
            "purchase_date": listing.purchase_date,
            "quantity": listing.quantity,
            "is_payed": listing.is_payed
        }
        for listing in buyer_listings
    ]

    return Response({"buyer_purchases": listings_data}, status=status.HTTP_200_OK)
