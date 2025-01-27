# Product/serializers.py
from rest_framework import serializers
from .models import Product, ProductPhoto

class ProductPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductPhoto
        fields = ['id', 'photo']

class ProductSerializer(serializers.ModelSerializer):
    photos = ProductPhotoSerializer(many=True, read_only=True)  

    class Meta:
        model = Product
        fields = ['id', 'seller', 'title', 'description', 'price', 'upload_date', 'condition', 'is_approved', 'photos']
        read_only_fields = ['id', 'seller', 'upload_date', 'is_approved']

    def create(self, validated_data):
        seller = self.context['seller']
        return Product.objects.create(seller=seller, **validated_data)