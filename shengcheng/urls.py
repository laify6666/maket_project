from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView

from buy import views

urlpatterns = [
    path("favicon.ico", RedirectView.as_view(url="/static/a1.png", permanent=True)),
    path("admin/", admin.site.urls),

    # Public pages
    path("", views.index, name="index"),
    path("register/", views.register, name="register"),
    path("denglu/", views.denglu, name="denglu"),
    path("logout/", views.logout, name="logout"),
    path("xq/", views.xq, name="xq"),
    path("category/", views.category_filter, name="category"),
    path("price_filter/", views.price_filter, name="price_filter"),
    path("sort/", views.sort, name="sort"),
    path("seek/", views.seek, name="seek"),

    # Buyer cart
    path("caradd/", views.caradd, name="caradd"),
    path("carlist/", views.carlist, name="carlist"),
    path("cart_change_num/", views.cart_change_num, name="cart_change_num"),
    path("cardel/", views.cardel, name="cardel"),
    path("cart_undo/", views.cart_undo, name="cart_undo"),
    path("get_cart_count/", views.get_cart_count, name="get_cart_count"),

    # Buyer order flow
    path("create_order/", views.create_order, name="create_order"),
    path("payon/<str:order_no>/", views.payon, name="payon"),
    path("pay_process/", views.pay_process, name="pay_process"),
    path("orderlist/", views.orderlist, name="orderlist"),
    path("order_detail/<str:order_no>/", views.order_detail, name="order_detail"),
    path("cancel_order/", views.cancel_order, name="cancel_order"),
    path("confirm_receipt/", views.confirm_receipt, name="confirm_receipt"),
    path("refund/", views.refund, name="refund"),

    # Buyer addresses and profile
    path("add_address/", views.add_address, name="add_address"),
    path("address_list/", views.address_list, name="address_list"),
    path("delete_address/", views.delete_address, name="delete_address"),
    path("set_default_address/", views.set_default_address, name="set_default_address"),
    path("update_address_before_ship/", views.update_address_before_ship, name="update_address_before_ship"),
    path("user_center/", views.user_center, name="user_center"),
    path("edit_user/", views.edit_user_info, name="edit_user_info"),
    path("modify_pwd/", views.modify_pwd, name="modify_pwd"),

    # Favorites
    path("collect/", views.collect_add, name="collect_add"),
    path("my_collect/", views.my_collect, name="my_collect"),
    path("cancel_collect/", views.cancel_collect, name="cancel_collect"),

    # Seller dashboard
    path("seller/goods_list/", views.seller_goods_list, name="seller_goods_list"),
    path("seller/add_goods/", views.seller_add_goods, name="seller_add_goods"),
    path("seller/del_goods/", views.seller_del_goods, name="seller_del_goods"),
    path("seller/orders/", views.seller_orders, name="seller_orders"),
    path("seller/orders/<str:order_no>/ship/", views.seller_ship, name="seller_ship"),
    path(
        "seller/refund/<str:order_no>/approve/",
        views.seller_refund_approve,
        name="seller_refund_approve",
    ),
    path(
        "seller/refund/<str:order_no>/reject/",
        views.seller_refund_reject,
        name="seller_refund_reject",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
