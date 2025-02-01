from django.contrib import admin
from .models import Category, Product, ProductPhoto, Bid, Listing,Notificationbid

admin.site.register(Category)
admin.site.register(Product)
admin.site.register(ProductPhoto)
admin.site.register(Bid)
admin.site.register(Listing)
admin.site.register(Notificationbid)
