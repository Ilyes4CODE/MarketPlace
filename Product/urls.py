# Product/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('create/', views.create_product, name='create_product'),
    path('update/<int:product_id>/', views.update_product, name='update_product'),
    path('delete/<int:product_id>/', views.delete_product, name='delete_product'),
    path('seller-products/', views.get_seller_products, name='get_seller_products'),
    path('list/', views.list_products, name='list_products'),
    # path('search/', views.search_products, name='search_products'),
]