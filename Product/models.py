from django.db import models
from Auth.models import MarketUser
from django.utils import timezone
# Create your models here.

class Product(models.Model):
    CONDITION_CHOICES = [
        ('new', 'New'),
        ('used', 'Used'),
    ]

    seller = models.ForeignKey(MarketUser, on_delete=models.CASCADE, related_name='products') 
    title = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    upload_date = models.DateTimeField(default=timezone.now) 
    condition = models.CharField(max_length=10, choices=CONDITION_CHOICES, default='new')
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return self.title

class ProductPhoto(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='photos')
    photo = models.ImageField(upload_to='product_photos/')  
    def __str__(self):
        return f"Photo for {self.product.title}"
    
class Listing(models.Model):
    buyer = models.ForeignKey(MarketUser, on_delete=models.CASCADE, related_name='purchases')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='listings')
    purchase_date = models.DateTimeField(default=timezone.now) 
    quantity = models.PositiveIntegerField(default=1) 

    def __str__(self):
        return f"{self.buyer.profile.username} purchased {self.product.title} on {self.purchase_date}"