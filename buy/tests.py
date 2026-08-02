import io

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from .models import Address, Goods, Goodscar, Order

User = get_user_model()


def make_image_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buffer, format="PNG")
    return buffer.getvalue()


class BaseShopTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user(
            username="seller1",
            password="seller-pass-123",
            role="seller",
            shop_name="示例小店",
            is_seller_approved=True,
        )
        cls.buyer = User.objects.create_user(
            username="buyer1",
            password="buyer-pass-123",
            role="buyer",
        )
        cls.other_buyer = User.objects.create_user(
            username="buyer2",
            password="buyer-pass-123",
            role="buyer",
        )
        cls.goods = Goods.objects.create(
            name="测试商品",
            price="19.90",
            category="food",
            stock=10,
            sales_volume=0,
            seller=cls.seller,
            is_active=True,
        )

    def setUp(self):
        cache.clear()

    def login_buyer(self, username="buyer1"):
        self.client.post(
            reverse("denglu"),
            {"username": username, "password": "buyer-pass-123", "login_type": "buyer"},
        )

    def login_seller(self):
        self.client.post(
            reverse("denglu"),
            {"username": "seller1", "password": "seller-pass-123", "login_type": "seller"},
        )

    def create_address(self, user=None):
        user = user or self.buyer
        return Address.objects.create(
            user=user,
            receiver_name="张三",
            phone="13800000000",
            province="上海市",
            city="上海市",
            district="浦东新区",
            detail="测试路 1 号",
            is_default=True,
        )

    def address_id(self):
        return Address.objects.get(user=self.buyer).id


class AuthTests(BaseShopTest):
    def test_register_and_login_buyer(self):
        resp = self.client.post(
            reverse("register"),
            {
                "username": "newbuyer",
                "password": "strong-pass-123",
                "password2": "strong-pass-123",
                "phone": "13900000000",
                "reg_role": "buyer",
            },
        )
        self.assertRedirects(resp, reverse("denglu"))
        self.assertTrue(User.objects.filter(username="newbuyer").exists())

    def test_register_rejects_weak_password(self):
        resp = self.client.post(
            reverse("register"),
            {
                "username": "weakuser",
                "password": "123",
                "password2": "123",
                "reg_role": "buyer",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username="weakuser").exists())

    def test_login_rate_limit(self):
        for _ in range(5):
            self.client.post(
                reverse("denglu"),
                {"username": "buyer1", "password": "wrong", "login_type": "buyer"},
            )
        resp = self.client.post(
            reverse("denglu"),
            {"username": "buyer1", "password": "buyer-pass-123", "login_type": "buyer"},
        )
        self.assertContains(resp, "失败次数过多")

    def test_seller_requires_approval(self):
        pending = User.objects.create_user(
            username="pending_seller",
            password="seller-pass-123",
            role="seller",
            is_seller_approved=False,
        )
        self.client.post(
            reverse("denglu"),
            {"username": "pending_seller", "password": "seller-pass-123", "login_type": "seller"},
        )
        resp = self.client.get(reverse("seller_goods_list"))
        self.assertContains(resp, "审核中")


class CartTests(BaseShopTest):
    def test_add_and_merge_cart(self):
        self.login_buyer()
        self.client.post(reverse("caradd"), {"goods_id": self.goods.id, "number": 2})
        self.client.post(reverse("caradd"), {"goods_id": self.goods.id, "number": 3})
        item = Goodscar.objects.get(user=self.buyer, goods=self.goods)
        self.assertEqual(item.number, 5)

    def test_cart_rejects_over_stock(self):
        self.login_buyer()
        self.client.post(reverse("caradd"), {"goods_id": self.goods.id, "number": 99})
        self.assertFalse(Goodscar.objects.filter(user=self.buyer).exists())

    def test_anonymous_cannot_use_cart(self):
        resp = self.client.post(reverse("caradd"), {"goods_id": self.goods.id, "number": 1})
        self.assertEqual(resp.status_code, 302)


class OrderFlowTests(BaseShopTest):
    def test_create_order_reserves_stock(self):
        self.login_buyer()
        self.create_address()
        self.client.post(reverse("caradd"), {"goods_id": self.goods.id, "number": 3})
        resp = self.client.post(reverse("create_order"), {"address_id": self.address_id()})
        self.assertIn(resp.status_code, (200, 302))
        self.goods.refresh_from_db()
        self.assertEqual(self.goods.stock, 7)
        order = Order.objects.get(user=self.buyer)
        self.assertEqual(order.status, "unpaid")

    def test_pay_and_cannot_pay_twice(self):
        self.login_buyer()
        self.create_address()
        self.client.post(reverse("caradd"), {"goods_id": self.goods.id, "number": 2})
        self.client.post(reverse("create_order"), {"address_id": self.address_id()})
        order = Order.objects.get(user=self.buyer)
        self.client.post(reverse("pay_process"), {"order_no": order.order_no})
        order.refresh_from_db()
        self.assertEqual(order.status, "paid")
        self.goods.refresh_from_db()
        self.assertEqual(self.goods.sales_volume, 2)

        self.client.post(reverse("pay_process"), {"order_no": order.order_no})
        order.refresh_from_db()
        self.assertEqual(order.status, "paid")
        self.goods.refresh_from_db()
        self.assertEqual(self.goods.sales_volume, 2)

    def test_cancel_unpaid_restores_stock(self):
        self.login_buyer()
        self.create_address()
        self.client.post(reverse("caradd"), {"goods_id": self.goods.id, "number": 4})
        self.client.post(reverse("create_order"), {"address_id": self.address_id()})
        order = Order.objects.get(user=self.buyer)
        self.client.post(reverse("cancel_order"), {"order_no": order.order_no})
        order.refresh_from_db()
        self.assertEqual(order.status, "cancelled")
        self.goods.refresh_from_db()
        self.assertEqual(self.goods.stock, 10)

    def test_order_detail_requires_owner(self):
        self.login_buyer()
        self.create_address()
        self.client.post(reverse("caradd"), {"goods_id": self.goods.id, "number": 1})
        self.client.post(reverse("create_order"), {"address_id": self.address_id()})
        order = Order.objects.get(user=self.buyer)

        self.client.logout()
        self.client.login(username="buyer2", password="buyer-pass-123")
        resp = self.client.get(reverse("order_detail", args=[order.order_no]))
        self.assertEqual(resp.status_code, 404)


class RefundFlowTests(BaseShopTest):
    def test_buyer_refund_then_seller_approves(self):
        self.login_buyer()
        self.create_address()
        self.client.post(reverse("caradd"), {"goods_id": self.goods.id, "number": 2})
        self.client.post(reverse("create_order"), {"address_id": self.address_id()})
        order = Order.objects.get(user=self.buyer)
        self.client.post(reverse("pay_process"), {"order_no": order.order_no})

        resp = self.client.post(
            reverse("refund"),
            data='{"order_no": "%s", "reason": "不想要了"}' % order.order_no,
            content_type="application/json",
        )
        self.assertEqual(resp.json()["status"], "success")
        order.refresh_from_db()
        self.assertEqual(order.status, "refunding")

        self.client.logout()
        self.login_seller()
        self.client.post(reverse("seller_refund_approve", args=[order.order_no]))
        order.refresh_from_db()
        self.assertEqual(order.status, "refunded")
        self.goods.refresh_from_db()
        self.assertEqual(self.goods.stock, 10)
        self.assertEqual(self.goods.sales_volume, 0)

    def test_unpaid_order_cannot_apply_refund(self):
        self.login_buyer()
        self.create_address()
        self.client.post(reverse("caradd"), {"goods_id": self.goods.id, "number": 1})
        self.client.post(reverse("create_order"), {"address_id": self.address_id()})
        order = Order.objects.get(user=self.buyer)
        resp = self.client.post(
            reverse("refund"),
            data='{"order_no": "%s", "reason": "测试"}' % order.order_no,
            content_type="application/json",
        )
        self.assertEqual(resp.json()["status"], "error")


class SellerTests(BaseShopTest):
    def test_seller_can_add_and_soft_delete_goods(self):
        self.login_seller()
        image = SimpleUploadedFile("goods.png", make_image_bytes(), content_type="image/png")
        resp = self.client.post(
            reverse("seller_add_goods"),
            {
                "name": "新商品",
                "category": "books",
                "price": "29.90",
                "weight": "500g",
                "stock": "8",
                "goodsdesc": "测试描述",
                "imgurl": image,
            },
        )
        self.assertRedirects(resp, reverse("seller_goods_list"))
        goods = Goods.objects.get(name="新商品")
        self.assertTrue(goods.is_active)

        self.client.post(reverse("seller_del_goods"), {"id": goods.id})
        goods.refresh_from_db()
        self.assertFalse(goods.is_active)

    def test_seller_cannot_manage_other_sellers_goods(self):
        self.login_seller()
        other_seller = User.objects.create_user(
            username="seller2",
            password="seller-pass-123",
            role="seller",
            is_seller_approved=True,
        )
        other_goods = Goods.objects.create(
            name="别人商品",
            price="9.90",
            category="other",
            stock=5,
            seller=other_seller,
        )
        resp = self.client.post(reverse("seller_del_goods"), {"id": other_goods.id})
        self.assertEqual(resp.status_code, 404)
        other_goods.refresh_from_db()
        self.assertTrue(other_goods.is_active)
