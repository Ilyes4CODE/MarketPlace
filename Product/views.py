from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from .models import Product, ProductPhoto, Bid,Notificationbid
from .serializer import ProductSerializer, ProductPhotoSerializer, BidSerializer

@swagger_auto_schema(
    method='post',
    operation_description="Create a new product. The authenticated user will be set as the seller.",
    request_body=ProductSerializer,
    responses={
        201: openapi.Response('Product created successfully', ProductSerializer),
        400: openapi.Response('Invalid data provided'),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_product(request):
    seller = request.user.marketuser
    data = request.data

    product_serializer = ProductSerializer(data=data, context={'seller': seller})
    if product_serializer.is_valid():
        product = product_serializer.save(seller=seller)
        photos = request.FILES.getlist('photos')
        for photo in photos:
            ProductPhoto.objects.create(product=product, photo=photo)

        return Response(product_serializer.data, status=status.HTTP_201_CREATED)
    return Response(product_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    operation_description="Place a bid on a product.",
    request_body=BidSerializer,
    responses={
        201: openapi.Response('Bid placed successfully', BidSerializer),
        400: openapi.Response('Invalid data provided'),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def place_bid(request, product_id):
    # Check if the product exists and is eligible for bidding
    product = Product.objects.filter(id=product_id, sale_type='bid', is_approved=True).first()
    if not product:
        return Response({"error": "Product not available for bidding."}, status=status.HTTP_404_NOT_FOUND)

    # Create a mutable copy of the request data
    data = request.data.copy()
    data['bidder'] = request.user.marketuser.id  # Add the bidder's ID
    data['product'] = product.pk  # Add the product's ID

    # Pass the modified data to the serializer
    bid_serializer = BidSerializer(data=data)
    if bid_serializer.is_valid():
        bid_serializer.save(bidder=request.user.marketuser, product=product)
        return Response(bid_serializer.data, status=status.HTTP_201_CREATED)

    return Response(bid_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    operation_description="End the bidding process for a product and select a winning bid.",
    # request_body=openapi.Schema(
    #     type=openapi.TYPE_OBJECT,
    #     properties={
    #         'bid_id': openapi.Schema(
    #             type=openapi.TYPE_INTEGER,
    #             description="ID of the selected bid to mark as the winner."
    #         ),
    #     },
    #     required=['bid_id']
    # ),
    responses={
        200: openapi.Response(
            description="Bidding ended successfully.",
            examples={
                "application/json": {
                    "message": "Bidding ended successfully.",
                    "winning_bid": {
                        "id": 123,
                        "product": 1,
                        "bidder": 2,
                        "amount": "500.00",
                        "bid_date": "2025-01-28T15:30:00Z",
                        "winner": True
                    }
                }
            }
        ),
        400: openapi.Response(
            description="Bad Request - Missing or invalid bid_id.",
            examples={
                "application/json": {
                    "error": "No bid_id provided. Please select a bid to end the auction."
                }
            }
        ),
        404: openapi.Response(
            description="Product or Bid Not Found.",
            examples={
                "application/json": {
                    "error": "Product not found or you do not have permission to end the bid."
                }
            }
        ),
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
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
        # Retrieve the selected bid
        selected_bid = Bid.objects.get(id=bid_id, product=product)
    except Bid.DoesNotExist:
        return Response({"error": "Selected bid not found or does not belong to this product."}, status=status.HTTP_404_NOT_FOUND)

    # Mark the selected bid as the winner
    selected_bid.winner = True
    selected_bid.save()

    # Update the product status to sold
    product.sold = True
    product.save()

    # Create a notification for the winner
    notification_message = f"Congratulations! Your bid of {selected_bid.amount} on {product.title} has won."
    Notificationbid.objects.create(
        recipient=selected_bid.bidder,
        message=notification_message,
        bid=selected_bid,
    )

    return Response({
        "message": "Bidding ended successfully.",
        "winning_bid": BidSerializer(selected_bid).data
    })

@swagger_auto_schema(
    method='get',
    operation_description="Retrieve all bids for a specific product.",
    responses={
        200: openapi.Response('List of bids', BidSerializer(many=True)),
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
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
def get_seller_products(request):
    seller = request.user.marketuser
    products = Product.objects.filter(seller=seller).order_by('-upload_date')
    serializer = ProductSerializer(products, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)
