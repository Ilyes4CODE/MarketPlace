from django.urls import path
from . import views

urlpatterns = [
    path('create/', views.create_product, name='create_product'),
    path('<int:product_id>/delete/', views.delete_product, name='delete_product'),
    path('<int:product_id>/update/', views.update_product, name='update_product'),
    path('seller/products/', views.get_seller_products, name='get_seller_products'),
    path('list/', views.list_products, name='list_products'),
    path('<int:product_id>/bids/', views.get_product_bids, name='get_product_bids'),
    path('<int:product_id>/bid/', views.place_bid, name='place_bid'),
    path('<int:product_id>/<int:bid_id>/end_bid/', views.end_bid, name='end_bid'),
]
