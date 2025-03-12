from django.db import models
from Auth.models import MarketUser
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import timedelta

# Create your models here.

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=100,null=True)
    image = models.ImageField(upload_to='Category_pictures/',null = True)

    def __str__(self):
        return self.name


class Product(models.Model):
    CONDITION_CHOICES = [
    ('جديد', 'جديد'),
    ('مستعمل', 'مستعمل'),
    ]

    SALE_TYPE_CHOICES = [
        ('عادي', 'عادي'),
        ('مزاد', 'مزاد'),
    ]

    CURRENCY_CHOICES = [
        ('دولار', 'دولار'),
        ('ليرة', 'ليرة'),
    ]

    seller = models.ForeignKey(MarketUser, on_delete=models.CASCADE, related_name='products')
    title = models.CharField(max_length=100)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, related_name='products')
    is_in_history = models.BooleanField(default=False)
    
    # Simple Product Fields
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Bid Product Fields
    starting_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    buy_now_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    duration = models.IntegerField(null=True, blank=True)  # Duration in hours
    bid_end_time = models.DateTimeField(null=True, blank=True)  # Time when bidding should close
    closed = models.BooleanField(default=False)  # True if the bid has ended
    closed_at = models.DateTimeField(null=True, blank=True)
    
    currency = models.CharField(max_length=23, choices=CURRENCY_CHOICES, default='دولار')
    upload_date = models.DateTimeField(default=timezone.now)
    condition = models.CharField(max_length=10, choices=CONDITION_CHOICES, default='جديد')
    sale_type = models.CharField(max_length=10, choices=SALE_TYPE_CHOICES, default='عادي')
    is_approved = models.BooleanField(default=False)
    location = models.CharField(max_length=50, null=True)
    sold = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        """Automatically sets bid_end_time and schedules closing."""
        is_new = self.pk is None  # Check if the product is new

        if self.sale_type == 'مزاد' and self.duration:
            if not self.bid_end_time:
                self.bid_end_time = self.upload_date + timedelta(hours=self.duration)

        super().save(*args, **kwargs)  # Save the product first

        # Automatically close bid if the time has passed
        if self.sale_type == 'مزاد' and self.bid_end_time and timezone.now() >= self.bid_end_time:
            self.close_bidding()

    def close_bidding(self):
        from .utils import start_conversation,send_real_time_notification
        """Closes the bid, selects a winner, and schedules history move."""
        if self.closed:
            return  # Already closed

        self.closed = True
        self.closed_at = timezone.now()
        self.save()

        highest_bid = Bid.objects.filter(product=self, status="pending").order_by('-amount').first()

        if highest_bid:
            highest_bid.winner = True
            highest_bid.save()

            send_real_time_notification(self.seller, f"المزاد على {self.title} قد انتهى! الفائز هو {highest_bid.buyer.name}.")
            send_real_time_notification(highest_bid.buyer, f"لقد فزت بالمزاد على {self.title} بمبلغ {highest_bid.amount} {self.currency}.")
            
            start_conversation(self.seller, highest_bid.buyer, self)
        else:
            send_real_time_notification(self.seller, f"المزاد على {self.title} قد انتهى بدون عروض.")

        # Schedule moving to history after 24 hours
        self.move_to_history_time = timezone.now() + timedelta(days=1)
        self.save()

    def check_and_move_to_history(self):
        """Moves the product to history after 24 hours of closing."""
        if self.closed and not self.is_in_history:
            time_since_closed = timezone.now() - self.closed_at
            if time_since_closed >= timedelta(days=1):
                self.is_in_history = True
                self.save()

    

    def __str__(self):
        return f"{self.title} - {self.price or self.starting_price} ({'Closed' if self.closed else 'Active'})"
    

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
    winner = models.BooleanField(default=False)

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
        