from rest_framework import serializers
from Product.models import Notificationbid

class NotificationBidSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificationbid
        fields = ['id', 'message', 'created_at']