from rest_framework import serializers
from .models import Message, Conversation,Notification

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'sender', 'content', 'picture', 'timestamp', 'seen']
        read_only_fields = ['id', 'sender', 'timestamp', 'seen']


class ConversationSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'seller', 'buyer', 'product', 'created_at', 'last_message']

    def get_last_message(self, obj):
        last_msg = obj.messages.order_by('-timestamp').first()
        if last_msg:
            return {
                "content": last_msg.content,
                "picture": last_msg.picture.url if last_msg.picture else None,
                "timestamp": last_msg.timestamp,
                "seen": last_msg.seen,
                "sender_id": last_msg.sender.id,
                "recipient_id": last_msg.recipient.id if last_msg.recipient else None
            }
        return None  # No messages yet

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'message', 'is_read', 'created_at']
        read_only_fields = ['id', 'created_at']