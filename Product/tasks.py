from celery import shared_task
from django.utils import timezone
from .models import Product, Bid
from .utils import send_real_time_notification, start_conversation

@shared_task
def close_bidding_task(product_id):
    """Closes the bid, selects the winner, and schedules history move."""
    try:
        product = Product.objects.get(id=product_id)

        if product.sale_type != 'مزاد' or product.closed:
            return  # Not a bidding product or already closed

        if product.bid_end_time and timezone.now() >= product.bid_end_time:
            product.closed = True
            product.closed_at = timezone.now()
            product.save()

            highest_bid = Bid.objects.filter(product=product, status="accepted").order_by('-amount').first()

            if highest_bid:
                highest_bid.winner = True
                highest_bid.save()

                send_real_time_notification(product.seller, f"المزاد على {product.title} قد انتهى! الفائز هو {highest_bid.buyer.name}.")
                send_real_time_notification(highest_bid.buyer, f"لقد فزت بالمزاد على {product.title} بمبلغ {highest_bid.amount} {product.currency}.")

                start_conversation(product.seller, highest_bid.buyer, product)
            else:
                send_real_time_notification(product.seller, f"المزاد على {product.title} قد انتهى بدون عروض.")

            product.save()

            # 🔹 Schedule move to history after 24 hours
            move_product_to_history.apply_async((product.id,), countdown=86400)  # 24 hours = 86400 seconds

    except Product.DoesNotExist:
        return  # Product was deleted or doesn't exist


@shared_task
def move_product_to_history(product_id):
    """Moves a closed product to history after 24 hours."""
    try:
        product = Product.objects.get(id=product_id)

        if product.closed and not product.is_in_history:
            product.is_in_history = True
            product.save()

    except Product.DoesNotExist:
        return  # Product was deleted or doesn't exist
