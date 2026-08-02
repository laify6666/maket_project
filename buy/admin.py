from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Address, BrowseHistory, Collect, Goods, Goodscar, Order, OrderItem, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "username",
        "role",
        "phone",
        "shop_name",
        "is_seller_approved",
        "is_active",
        "date_joined",
    )
    list_filter = ("role", "is_seller_approved", "is_active")
    search_fields = ("username", "phone", "shop_name")
    fieldsets = UserAdmin.fieldsets + (
        (
            "商城资料",
            {
                "fields": ("role", "phone", "shop_name", "is_seller_approved"),
            },
        ),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "商城资料",
            {
                "fields": ("role", "phone", "shop_name", "is_seller_approved"),
            },
        ),
    )


@admin.register(Goods)
class GoodsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "seller",
        "category",
        "price",
        "stock",
        "sales_volume",
        "is_active",
        "created_at",
    )
    list_filter = ("category", "is_active", "seller")
    search_fields = ("name", "goodsdesc")


@admin.register(Goodscar)
class GoodscarAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "goods", "number", "price", "created_at")
    search_fields = ("user__username", "goods__name")


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "receiver_name", "phone", "full_address", "is_default")
    list_filter = ("is_default",)
    search_fields = ("user__username", "receiver_name", "detail")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_no",
        "user",
        "seller",
        "total_price",
        "status",
        "created_at",
        "updated_at",
    )
    list_filter = ("status", "seller", "created_at")
    search_fields = ("order_no", "user__username", "receiver_name", "receiver_phone")
    readonly_fields = ("created_at", "updated_at")


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "goods", "name", "price", "number", "total_price")
    search_fields = ("order__order_no", "name")


@admin.register(Collect)
class CollectAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "goods", "create_time")
    search_fields = ("user__username", "goods__name")


@admin.register(BrowseHistory)
class BrowseHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "goods", "browse_time")
    search_fields = ("user__username", "goods__name")
