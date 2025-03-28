from django.utils import timezone
from rest_framework import serializers
from .models import Product, ProductPhoto, Bid,Category
from rest_framework.exceptions import ValidationError
class ProductPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductPhoto
        fields = ['id', 'photo']




class ProductSerializer(serializers.ModelSerializer):
    photos = ProductPhotoSerializer(many=True, read_only=True)
    seller_name = serializers.CharField(source='seller.name', read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'title', 'description', 'price', 'starting_price', 'buy_now_price',
            'duration', 'bid_end_time', 'closed', 'currency', 'condition', 'location',
            'is_approved', 'sale_type', 'seller', 'seller_name', 'photos', 'category',
            'is_in_history', 'closed_at'
        ]
        read_only_fields = ['id', 'is_approved', 'seller', 'bid_end_time', 'closed']
        extra_kwargs = {
            'price': {
                'error_messages': {'invalid': '⚠️ السعر يجب أن يكون رقمًا صحيحًا أو عشريًا.'}
            },
            'starting_price': {
                'error_messages': {'invalid': '⚠️ السعر الابتدائي يجب أن يكون رقمًا صحيحًا أو عشريًا.'}
            },
            'buy_now_price': {
                'error_messages': {'invalid': '⚠️ سعر الشراء الفوري يجب أن يكون رقمًا صحيحًا أو عشريًا.'}
            },
            'duration': {
                'error_messages': {'invalid': '⚠️ مدة المزاد يجب أن تكون عددًا صحيحًا.'}
            },
            'bid_end_time': {
                'error_messages': {'invalid': '⚠️ وقت انتهاء المزاد يجب أن يكون تاريخًا صالحًا.'}
            },
            'location': {
                'error_messages': {'required': '⚠️ الموقع مطلوب.', 'blank': '⚠️ الموقع لا يمكن أن يكون فارغًا.'}
            },
            'currency': {
                'error_messages': {'required': '⚠️ العملة مطلوبة.'}
            },
            'condition': {
                'error_messages': {'required': '⚠️ الحالة مطلوبة.'}
            },
            'sale_type': {
                'error_messages': {'required': '⚠️ نوع البيع مطلوب.'}
            },
            'category': {
                'error_messages': {'required': '⚠️ الفئة مطلوبة.'}
            },
            'closed_at': {
                'error_messages': {'required': '⚠️ يجب تحديد وقت الإغلاق عند إغلاق المنتج.'}
            }
        }

    def validate(self, data):
        errors = {}

        # ✅ Title validation
        title = data.get('title')
        if not title or len(title) > 100:
            errors['title'] = {"error": "⚠️ العنوان مطلوب ويجب أن يكون أقل من 100 حرف."}

        # ✅ Description validation
        description = data.get('description')
        if not description:
            errors['description'] = {"error": "⚠️ الوصف مطلوب."}

        # ✅ Price validation
        price = data.get('price')
        sale_type = data.get('sale_type')
        if sale_type == "عادي":
            if price is None or price <= 0:
                errors['price'] = {"error": "⚠️ السعر مطلوب ويجب أن يكون أكبر من الصفر في المنتجات العادية."}
        
        # ✅ Auction fields validation
        starting_price = data.get('starting_price')
        buy_now_price = data.get('buy_now_price')
        duration = data.get('duration')

        if sale_type == "مزاد":
            if starting_price is None or starting_price <= 0:
                errors['starting_price'] = {"error": "⚠️ السعر الابتدائي مطلوب ويجب أن يكون أكبر من الصفر في المزادات."}

            if buy_now_price and buy_now_price <= starting_price:
                errors['buy_now_price'] = {"error": "⚠️ سعر الشراء الفوري يجب أن يكون أعلى من السعر الابتدائي."}

            if duration is None or duration <= 0:
                errors['duration'] = {"error": "⚠️ مدة المزاد مطلوبة ويجب أن تكون أكبر من الصفر."}

        # ✅ Currency validation
        currency = data.get('currency')
        valid_currencies = dict(Product.CURRENCY_CHOICES).keys()
        if currency not in valid_currencies:
            errors['currency'] = {"error": "⚠️ العملة غير صالحة."}

        # ✅ Condition validation
        condition = data.get('condition')
        valid_conditions = dict(Product.CONDITION_CHOICES).keys()
        if condition not in valid_conditions:
            errors['condition'] = {"error": "⚠️ الحالة غير صالحة."}

        # ✅ Sale Type validation
        valid_sale_types = dict(Product.SALE_TYPE_CHOICES).keys()
        if sale_type not in valid_sale_types:
            errors['sale_type'] = {"error": "⚠️ نوع البيع غير صالح."}

        # ✅ Location validation
        location = data.get('location')
        if not location or len(location) > 50:
            errors['location'] = {"error": "⚠️ الموقع مطلوب ويجب أن يكون أقل من 50 حرف."}

        # ✅ Category validation
        category = data.get('category')
        if sale_type != "مزاد" and not category:
            errors['category'] = {"error": "⚠️ الفئة مطلوبة."}

        # ✅ Closed & Closed_at Validation
        closed = data.get('closed')
        closed_at = data.get('closed_at')

        if closed and not closed_at:
            errors['closed_at'] = {"error": "⚠️ يجب تحديد وقت الإغلاق عند إغلاق المنتج."}
        
        # ✅ Bid End Time Validation
        bid_end_time = data.get('bid_end_time')
        if bid_end_time and bid_end_time <= timezone.now():
            errors['bid_end_time'] = {"error": "⚠️ وقت انتهاء المزاد يجب أن يكون في المستقبل."}

        # If errors exist, raise ValidationError with custom messages
        if errors:
            raise serializers.ValidationError(errors)

        return data




class BidSerializer(serializers.ModelSerializer):
    buyer_name = serializers.CharField(source='buyer.name', read_only=True)
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