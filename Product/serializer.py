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
    bidder_name = serializers.CharField(source='bidder.user.username', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = Bid
        fields = ['id', 'amount', 'bidder', 'product', 'bidder_name', 'product_name','winner']
        read_only_fields = ['id', 'bidder', 'product']
