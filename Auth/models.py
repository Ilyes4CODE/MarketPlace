from django.db import models
from django.contrib.auth.models import User
# Create your models here.


class MarketUser(models.Model):
    profile = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(max_length=50, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pic/', blank=True, null=True,default='Default_pfp.jpg')
    registration_method = models.CharField(max_length=10, choices=[('email', 'Email'), ('phone', 'Phone')], default='email')

    def __str__(self):
        return self.profile.username