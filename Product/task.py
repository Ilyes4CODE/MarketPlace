from celery import shared_task
from django.utils import timezone
from .models import Product

@shared_task
def close_expired_bids():
    """Closes bids that have reached their deadline."""
    expired_bids = Product.objects.filter(sale_type='bid', closed=False, bid_end_time__lte=timezone.now())
    for bid in expired_bids:
        bid.closed = True
        bid.save()
    return f"Closed {expired_bids.count()} expired bids."
