from django.urls import path
from . import views

urlpatterns = [
    path('create_product/simple/', views.create_simple_product, name='create_product_simple'),
    path('create_product/bid/', views.create_bid_product, name='create_product_bid'),
    path('<int:product_id>/delete/', views.delete_product, name='delete_product'),
    # path('<int:product_id>/update/', views.update_product, name='update_product'),
    path('seller/products/', views.get_seller_products, name='get_seller_products'),
    path('list/', views.list_products, name='list_products'),
    path('<int:product_id>/bids/', views.get_product_bids, name='get_product_bids'),
    path('<int:product_id>/bid/', views.place_bid, name='place_bid'),
    path('<int:product_id>/<int:bid_id>/end_bid/', views.end_bid, name='end_bid'),
    path('<int:product_id>/Purchase/',views.purchase_product),
    path('listings/accept/<int:listing_id>/', views.accept_related_listings, name='accept_listing'),
    path('listings/seller/', views.get_seller_listings, name='seller_listings'),
    path('listings/buyer/', views.get_buyer_purchases, name='buyer_purchases'),
    path('History/',views.seller_products_history),
    path('Create_Category/',views.create_category),
    path('Get_All_Categories/',views.get_all_categories)
]
