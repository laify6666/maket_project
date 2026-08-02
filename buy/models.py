from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """Buyer/seller account with optional merchant approval."""

    ROLE_CHOICES = [
        ("buyer", "买家"),
        ("seller", "卖家"),
    ]

    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default="buyer",
        verbose_name="账号类型",
    )
    phone = models.CharField(max_length=20, blank=True, default="", verbose_name="手机号")
    shop_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="店铺名称",
    )
    is_seller_approved = models.BooleanField(
        default=False,
        verbose_name="卖家是否通过审核",
    )

    class Meta:
        verbose_name = "用户"
        verbose_name_plural = "用户"

    def __str__(self):
        return self.username


class Goods(models.Model):
    """Product published by an approved seller."""

    CATEGORY_CHOICES = [
        ("electronics", "电子产品"),
        ("clothing", "服装配饰"),
        ("food", "食品饮料"),
        ("books", "图书文具"),
        ("home", "家居生活"),
        ("sports", "运动户外"),
        ("beauty", "美妆个护"),
        ("other", "其他"),
    ]

    name = models.CharField(max_length=100, db_index=True, verbose_name="商品名称")
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="商品价格",
    )
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default="other",
        db_index=True,
        verbose_name="商品类别",
    )
    stock = models.PositiveIntegerField(default=0, verbose_name="库存数量")
    sales_volume = models.PositiveIntegerField(default=0, verbose_name="销量")
    goodsdesc = models.TextField(blank=True, default="", verbose_name="商品描述")
    weight = models.CharField(max_length=100, blank=True, default="", verbose_name="规格/重量")
    imgurl = models.ImageField(
        upload_to="goods/%Y/%m/",
        blank=True,
        null=True,
        verbose_name="商品图片",
    )
    seller = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="goods",
        verbose_name="所属卖家",
    )
    is_active = models.BooleanField(default=True, verbose_name="是否上架")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "商品"
        verbose_name_plural = "商品"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["category", "price"]),
            models.Index(fields=["seller", "is_active"]),
        ]

    def __str__(self):
        return self.name


class Goodscar(models.Model):
    """One line in a buyer's cart. The same product is merged into one row."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="cart_items",
        verbose_name="所属用户",
    )
    goods = models.ForeignKey(
        Goods,
        on_delete=models.CASCADE,
        related_name="cart_items",
        verbose_name="商品",
    )
    number = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="商品数量",
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="加入购物车时的单价",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="添加时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "购物车"
        verbose_name_plural = "购物车"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "goods"],
                name="uniq_cart_user_goods",
            )
        ]

    @property
    def total_price(self):
        return self.price * self.number

    def __str__(self):
        return f"{self.user.username} - {self.goods.name}"


class Address(models.Model):
    """Shipping address owned by a buyer."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="addresses",
        verbose_name="所属用户",
    )
    receiver_name = models.CharField(max_length=50, verbose_name="收货人姓名")
    phone = models.CharField(max_length=20, verbose_name="联系电话")
    province = models.CharField(max_length=50, blank=True, default="", verbose_name="省份")
    city = models.CharField(max_length=50, blank=True, default="", verbose_name="城市")
    district = models.CharField(max_length=50, blank=True, default="", verbose_name="区县")
    detail = models.CharField(max_length=200, verbose_name="详细地址")
    is_default = models.BooleanField(default=False, verbose_name="是否默认地址")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "收货地址"
        verbose_name_plural = "收货地址"

    @property
    def full_address(self):
        return f"{self.province}{self.city}{self.district}{self.detail}"

    def __str__(self):
        return f"{self.receiver_name} - {self.full_address}"


class Order(models.Model):
    """Order created per seller so each merchant can ship independently."""

    STATUS_CHOICES = [
        ("unpaid", "待支付"),
        ("paid", "已支付"),
        ("shipped", "已发货"),
        ("completed", "已完成"),
        ("cancelled", "已取消"),
        ("refunding", "退款中"),
        ("refunded", "已退款"),
    ]

    order_no = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        verbose_name="订单号",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="orders",
        verbose_name="买家",
    )
    seller = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sold_orders",
        verbose_name="卖家",
    )
    address = models.CharField(max_length=500, verbose_name="收货地址")
    receiver_name = models.CharField(max_length=50, blank=True, default="", verbose_name="收货人")
    receiver_phone = models.CharField(max_length=20, blank=True, default="", verbose_name="收货电话")
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="订单总额",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="unpaid",
        db_index=True,
        verbose_name="订单状态",
    )
    refund_reason = models.TextField(blank=True, default="", verbose_name="退款原因")
    status_before_refund = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="申请退款前的状态",
    )
    tracking_no = models.CharField(max_length=100, blank=True, default="", verbose_name="物流单号")
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name="支付时间")
    shipped_at = models.DateTimeField(null=True, blank=True, verbose_name="发货时间")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="完成时间")
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name="取消时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="下单时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "订单"
        verbose_name_plural = "订单"
        ordering = ["-created_at"]

    def __str__(self):
        return self.order_no


class OrderItem(models.Model):
    """Snapshot of a product inside an order."""

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="所属订单",
    )
    goods = models.ForeignKey(
        Goods,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
        verbose_name="商品",
    )
    name = models.CharField(max_length=100, verbose_name="商品名称")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="成交单价")
    number = models.PositiveIntegerField(verbose_name="商品数量")

    class Meta:
        verbose_name = "订单商品"
        verbose_name_plural = "订单商品"

    @property
    def total_price(self):
        return self.price * self.number

    def __str__(self):
        return f"{self.order.order_no} - {self.name}"


class Collect(models.Model):
    """A buyer's favorite products."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="collects",
        verbose_name="用户",
    )
    goods = models.ForeignKey(
        Goods,
        on_delete=models.CASCADE,
        related_name="collected_by",
        verbose_name="商品",
    )
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="收藏时间")

    class Meta:
        verbose_name = "收藏"
        verbose_name_plural = "收藏"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "goods"],
                name="uniq_collect_user_goods",
            )
        ]

    def __str__(self):
        return f"{self.user.username} - {self.goods.name}"


class BrowseHistory(models.Model):
    """Product view history; linked to the user when logged in."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="browse_history",
        verbose_name="用户",
    )
    goods = models.ForeignKey(
        Goods,
        on_delete=models.CASCADE,
        related_name="browse_history",
        verbose_name="浏览商品",
    )
    browse_time = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="浏览时间")

    class Meta:
        verbose_name = "浏览记录"
        verbose_name_plural = "浏览记录"
        ordering = ["-browse_time"]

    def __str__(self):
        return f"{self.user or '匿名'} 浏览 {self.goods.name}"
