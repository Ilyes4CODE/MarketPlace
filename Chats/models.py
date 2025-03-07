from django.db import models
from Auth.models import MarketUser
from Product.models import Product
# Create your models here.
class Conversation(models.Model):
    seller = models.ForeignKey(MarketUser, on_delete=models.CASCADE, related_name='seller_conversations')
    buyer = models.ForeignKey(MarketUser, on_delete=models.CASCADE, related_name='buyer_conversations')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('seller', 'buyer', 'product')  # Ensure unique conversations

    def __str__(self):
        return f"Conversation between {self.seller.profile.username} (Seller) and {self.buyer.profile.username} (Buyer)"
    
class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(MarketUser, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(MarketUser, on_delete=models.CASCADE, related_name='received_messages' ,null=True)  # ✅ Added recipient
    content = models.TextField(blank=True, null=True)  # Message text
    picture = models.ImageField(upload_to='message_pictures/', blank=True, null=True)  # Optional image
    timestamp = models.DateTimeField(auto_now_add=True)
    seen = models.BooleanField(default=False)  # Message read status

    def __str__(self):
        return f"Message from {self.sender.profile.username} to {self.recipient.profile.username} at {self.timestamp}"
    
class Notification(models.Model):
    user = models.ForeignKey(MarketUser, on_delete=models.CASCADE, related_name='general_notifications')  # ✅ Unique related_name
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='notifications')  
    is_read = models.BooleanField(default=False) 
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.user.profile.username} about message {self.message.id}"
    

class ChatNotification(models.Model):
    recipient = models.ForeignKey(MarketUser, on_delete=models.CASCADE, related_name="chat_message_notifications")  # ✅ Unique related_name
    sender = models.ForeignKey(MarketUser, on_delete=models.CASCADE, related_name="sent_chat_notifications")  # ✅ Unique related_name
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    seen = models.BooleanField(default=False)

    def __str__(self):
        return f"Chat Notification for {self.recipient.profile.username} from {self.sender.profile.username}"