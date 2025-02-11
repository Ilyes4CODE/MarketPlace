from rest_framework import serializers
from Product.models import Notificationbid

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificationbid
        fields = ['id', 'recipient', 'message', 'bid', 'is_read', 'created_at', 'timestamp']