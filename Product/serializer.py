from rest_framework import serializers
from .models import Product, ProductPhoto, Bid

class ProductPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductPhoto
        fields = ['id', 'photo']


class ProductSerializer(serializers.ModelSerializer):
    photos = ProductPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'title', 'description', 'price', 'condition', 
            'is_approved', 'sale_type', 'seller', 'photos'
        ]
        read_only_fields = ['id', 'is_approved', 'seller']


class BidSerializer(serializers.ModelSerializer):
    buyer_name = serializers.CharField(source='buyer.user.username', read_only=True)
    product_name = serializers.CharField(source='product.title', read_only=True)
    seller_name = serializers.CharField(source='product.seller.user.username', read_only=True)
    
    class Meta:
        model = Bid
        fields = ['id', 'product', 'buyer', 'buyer_name', 'product_name', 'seller_name', 'amount', 'status', 'created_at']
        read_only_fields = ['id', 'buyer', 'buyer_name', 'product_name', 'seller_name', 'created_at']


