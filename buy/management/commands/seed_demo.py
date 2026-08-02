from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Create demo buyer and approved seller accounts only (no sample goods)."

    def handle(self, *args, **options):
        seller, created_seller = User.objects.get_or_create(
            username="seller",
            defaults={
                "role": "seller",
                "shop_name": "示例小店",
                "is_seller_approved": True,
            },
        )
        if created_seller:
            seller.set_password("seller123456")
            seller.save()

        buyer, created_buyer = User.objects.get_or_create(
            username="buyer",
            defaults={
                "role": "buyer",
                "phone": "13800000000",
            },
        )
        if created_buyer:
            buyer.set_password("buyer123456")
            buyer.save()

        self.stdout.write(self.style.SUCCESS("Accounts ready."))
        self.stdout.write("No goods were created; add products from the seller dashboard.")
        self.stdout.write("buyer / buyer123456")
        self.stdout.write("seller / seller123456")
