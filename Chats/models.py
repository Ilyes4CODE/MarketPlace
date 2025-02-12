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
    content = models.TextField(blank=True, null=True)  # Make content optional
    picture = models.ImageField(upload_to='message_pictures/', blank=True, null=True)  # Add picture field
    timestamp = models.DateTimeField(auto_now_add=True)
    seen = models.BooleanField(default=False)

    def __str__(self):
        return f"Message from {self.sender.profile.username} at {self.timestamp}"
    
class Notification(models.Model):
    user = models.ForeignKey(MarketUser, on_delete=models.CASCADE, related_name='chat_notifications')  
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='notifications')  
    is_read = models.BooleanField(default=False) 
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.user.profile.username} about message {self.message.id}"