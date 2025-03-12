from django.core.management.base import BaseCommand
from django.utils import timezone
from Product.models import Product,Bid
import time
from Product.utils import *
class Command(BaseCommand):
    help = 'Checks for expired bids, selects the winner, and moves to history after 24 hours.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Starting bid expiration and history checker..."))

        while True:
            now = timezone.now()

            # 🔹 Step 1: Close expired bids and choose a winner
            expired_bids = Product.objects.filter(sale_type='مزاد', closed=False, bid_end_time__lte=now)
            for product in expired_bids:
                product.sold = True
                product.closed = True
                product.closed_at = now  # Save the closing time
                product.save()

                # 🏆 Find the highest bid
                highest_bid = Bid.objects.filter(product=product, status="accepted").order_by('-amount').first()

                if highest_bid:
                    highest_bid.winner = True
                    highest_bid.save()

                    # 📢 Notify seller & winner
                    send_real_time_notification(product.seller, f"المزاد على {product.title} قد انتهى! الفائز هو {highest_bid.buyer.name}.")
                    send_real_time_notification(highest_bid.buyer, f"لقد فزت بالمزاد على {product.title} بمبلغ {highest_bid.amount} {product.currency}.")

                    # 💬 Create a conversation between seller & winner
                    start_conversation(product.seller, highest_bid.buyer, product)
                
                else:
                    send_real_time_notification(product.seller, f"المزاد على {product.title} قد انتهى بدون عروض.")

                self.stdout.write(self.style.SUCCESS(f'Closed bid for: {product.title}'))

            # 🔹 Step 2: Move to history after 24 hours
            move_to_history = Product.objects.filter(sale_type='مزاد', closed=True, is_in_history=False, closed_at__lte=now - timezone.timedelta(hours=24))
            for product in move_to_history:
                product.is_in_history = True
                product.save()
                self.stdout.write(self.style.SUCCESS(f'Moved to history: {product.title}'))

            self.stdout.write(self.style.SUCCESS("Checked for expired bids. Sleeping for 60 seconds...")) 
            time.sleep(60) 