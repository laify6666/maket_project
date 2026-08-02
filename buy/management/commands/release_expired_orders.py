from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from buy.models import Goods, Order


class Command(BaseCommand):
    help = "Cancel unpaid orders older than the timeout and release their stock."

    def add_arguments(self, parser):
        parser.add_argument("--minutes", type=int, default=30)

    def handle(self, *args, **options):
        minutes = options["minutes"]
        deadline = timezone.now() - timedelta(minutes=minutes)
        expired_orders = Order.objects.filter(status="unpaid", created_at__lt=deadline)
        count = 0

        with transaction.atomic():
            for order in expired_orders.select_for_update().prefetch_related("items"):
                for item in order.items.all():
                    if item.goods_id:
                        Goods.objects.filter(pk=item.goods_id).update(
                            stock=F("stock") + item.number
                        )
                order.status = "cancelled"
                order.cancelled_at = timezone.now()
                order.save(update_fields=["status", "cancelled_at", "updated_at"])
                count += 1

        self.stdout.write(self.style.SUCCESS(f"Released {count} expired order(s)."))
