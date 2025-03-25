from rest_framework import serializers
from .models import Product, ProductPhoto, Bid,Category

class ProductPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductPhoto
        fields = ['id', 'photo']


class ProductSerializer(serializers.ModelSerializer):
    photos = ProductPhotoSerializer(many=True, read_only=True)
    seller_name = serializers.CharField(source='seller.name', read_only=True)  # Fetch seller's name

    class Meta:
        model = Product
        fields = [
            'id', 'title', 'description', 'price', 'starting_price', 'buy_now_price', 
            'duration', 'bid_end_time', 'closed', 'currency', 'condition', 'location', 
            'is_approved', 'sale_type', 'seller', 'seller_name', 'photos', 'category', 
            'is_in_history', 'closed_at'
        ]
        read_only_fields = ['id', 'is_approved', 'seller', 'bid_end_time', 'closed']



class BidSerializer(serializers.ModelSerializer):
    buyer_name = serializers.CharField(source='buyer.user.username', read_only=True)
    product_name = serializers.CharField(source='product.title', read_only=True)
    seller_name = serializers.CharField(source='product.seller.user.username', read_only=True)
    
    class Meta:
        model = Bid
        fields = ['id', 'product', 'buyer', 'buyer_name', 'product_name', 'seller_name', 'amount', 'status', 'created_at']
        read_only_fields = ['id', 'buyer', 'buyer_name', 'product_name', 'seller_name', 'created_at']



class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'image']