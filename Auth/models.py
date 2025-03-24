from django.db import models
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
# Create your models here.


class MarketUser(models.Model):
    REGISTRATION_METHODS = [
        ('google', 'Google'),
        ('facebook', 'Facebook'),
        ('apple', 'Apple ID'),
    ]

    profile = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(max_length=50, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pic/', blank=True, null=True, default='Default_pfp.jpg')
    is_banned = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    created = models.DateField(auto_now=True, null=True)
    registration_method = models.CharField(max_length=10, choices=REGISTRATION_METHODS, null=True, blank=True)

    def __str__(self):
        return self.profile.username

    def get_tokens(self):
        refresh = RefreshToken.for_user(self.profile)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
    

class DeletedAccounts(models.Model):
    email = models.EmailField(max_length=254)

    def __str__(self):
        return self.email