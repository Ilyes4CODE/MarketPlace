from django.db import models
from Auth.models import MarketUser
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

# Create your models here.

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    CONDITION_CHOICES = [
        ('new', 'New'),
        ('used', 'Used'),
    ]

    SALE_TYPE_CHOICES = [
        ('simple', 'Simple'),
        ('bid', 'Bid'),
    ]

    seller = models.ForeignKey(MarketUser, on_delete=models.CASCADE, related_name='products') 
    title = models.CharField(max_length=100)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Optional for bidding
    upload_date = models.DateTimeField(default=timezone.now) 
    condition = models.CharField(max_length=10, choices=CONDITION_CHOICES, default='new')
    sale_type = models.CharField(max_length=10, choices=SALE_TYPE_CHOICES, default='simple')
    is_approved = models.BooleanField(default=False)
    sold = models.BooleanField(default=False)
    
    def __str__(self):
        return self.title
    

class ProductPhoto(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='photos')
    photo = models.ImageField(upload_to='product_photos/')  
    def __str__(self):
        return f"Photo for {self.product.title}"

class Bid(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    buyer = models.ForeignKey(MarketUser, on_delete=models.CASCADE, related_name="bids")  # Updated to MarketUser
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=10,
        choices=[("pending", "Pending"), ("accepted", "Accepted"), ("rejected", "Rejected")],
        default="pending"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.buyer.name} bid {self.amount} on {self.product.title}"

class Listing(models.Model):
    buyer = models.ForeignKey(MarketUser, on_delete=models.CASCADE, related_name='purchases')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='listings')
    purchase_date = models.DateTimeField(default=timezone.now) 
    quantity = models.PositiveIntegerField(default=1)
    is_payed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.buyer.profile.username} purchased {self.product.title} on {self.purchase_date}"
    

class Notificationbid(models.Model):
    recipient = models.ForeignKey(
        MarketUser,
        on_delete=models.CASCADE,
        related_name='product_notifications'  # Unique related_name
    )
    message = models.TextField()
    bid = models.ForeignKey(
        Bid,
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    timestamp = models.DateTimeField(default=timezone.now,null=True, blank=True)

    def __str__(self):
        return f"Notification for {self.recipient.profile.username}: {self.message}"

@receiver(post_save, sender=Bid)
def create_bid_notification(sender, instance, created, **kwargs):
    if created:
        product = instance.product
        seller = product.seller  # The seller of the product
        buyer = instance.buyer  # The buyer who placed the bid

        # # Notify the Seller (New Bid Placed)
        # seller_message = f"A new bid of {instance.amount} has been placed on your product '{product.title}'."
        # Notificationbid.objects.create(
        #     recipient=seller,
        #     message=seller_message,
        #     bid=instance
        # )

        # Notify the Buyer (Bid Under Review)
        buyer_message = f"Your bid of {instance.amount} on '{product.title}' is under review."
        Notificationbid.objects.create(
            recipient=buyer,
            message=buyer_message,
            bid=instance
        )
        