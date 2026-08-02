from django.core.management.base import BaseCommand
from django.db import transaction

from buy.models import (
    Address,
    BrowseHistory,
    Collect,
    Goods,
    Goodscar,
    Order,
    OrderItem,
)


class Command(BaseCommand):
    help = "Delete all shop business data (goods, cart, orders, favorites, history, addresses)."

    @transaction.atomic
    def handle(self, *args, **options):
        counts = {
            "Goods": Goods.objects.count(),
            "Goodscar": Goodscar.objects.count(),
            "OrderItem": OrderItem.objects.count(),
            "Order": Order.objects.count(),
            "Address": Address.objects.count(),
            "Collect": Collect.objects.count(),
            "BrowseHistory": BrowseHistory.objects.count(),
        }

        Goodscar.objects.all().delete()
        OrderItem.objects.all().delete()
        Order.objects.all().delete()
        Address.objects.all().delete()
        Collect.objects.all().delete()
        BrowseHistory.objects.all().delete()
        Goods.objects.all().delete()

        self.stdout.write("Deleted business data:")
        for name, count in counts.items():
            self.stdout.write(f"  {name}: {count}")
        self.stdout.write(self.style.SUCCESS("Done. User accounts are kept."))
