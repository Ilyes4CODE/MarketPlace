from rest_framework import serializers
from .models import PredefinedMessage, Ticket, Message, Attachment

class PredefinedMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PredefinedMessage
        fields = '__all__'


class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ['id', 'subject', 'status', 'created_at']
        read_only_fields = ['id', 'status', 'created_at']  


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = '__all__'


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = '__all__'
