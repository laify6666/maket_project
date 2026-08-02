import json
import logging
import uuid
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from functools import wraps

from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import Address, BrowseHistory, Collect, Goods, Goodscar, Order, OrderItem, User

logger = logging.getLogger("buy")


# ---------------------------------------------------------------------------
# Helpers and decorators
# ---------------------------------------------------------------------------
def _safe_next(request):
    next_url = request.POST.get("next") or request.GET.get("next") or "/"
    if next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return "/"


def role_required(role, seller_approved=False):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("denglu")
            if request.user.role != role:
                messages.error(request, "当前账号没有访问权限")
                return redirect("index")
            if seller_approved and not request.user.is_seller_approved:
                return render(request, "seller_approval_pending.html", {})
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


buyer_required = role_required("buyer")
seller_required = role_required("seller", seller_approved=True)


def get_base_context(request):
    cart_count = 0
    if request.user.is_authenticated and request.user.role == "buyer":
        cart_count = (
            Goodscar.objects.filter(user=request.user)
            .aggregate(total=Sum("number"))
            .get("total")
            or 0
        )

    hot_goods = Goods.objects.filter(is_active=True).order_by("-sales_volume")[:5]
    hot_search = ["手机", "零食", "衣服", "书籍", "运动鞋"]

    browse_list = []
    browse_ids = [
        int(value)
        for value in request.session.get("browse", [])
        if str(value).isdigit()
    ][-6:]
    if browse_ids:
        goods_map = {
            goods.id: goods
            for goods in Goods.objects.filter(id__in=browse_ids, is_active=True)
        }
        browse_list = [goods_map[gid] for gid in browse_ids if gid in goods_map]

    return {
        "is_login": request.user.is_authenticated,
        "username": request.user.username if request.user.is_authenticated else "",
        "role": request.user.role if request.user.is_authenticated else "",
        "cart_count": cart_count,
        "hot_goods": hot_goods,
        "hot_search": hot_search,
        "browse_list": browse_list,
    }


def _validate_positive_int(value, default=1):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return result if result > 0 else default


def _validate_decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("金额格式不正确")


def _restore_stock_for_items(items):
    """Restore reserved stock without touching sales volume."""
    for item in items:
        if item.goods_id:
            Goods.objects.filter(pk=item.goods_id).update(stock=F("stock") + item.number)


def _increase_sales_for_items(items):
    for item in items:
        if item.goods_id:
            Goods.objects.filter(pk=item.goods_id).update(
                sales_volume=F("sales_volume") + item.number
            )


def _decrease_sales_for_items(items):
    for item in items:
        if item.goods_id:
            Goods.objects.filter(pk=item.goods_id).update(
                sales_volume=F("sales_volume") - item.number
            )


# ---------------------------------------------------------------------------
# Auth: register / login / logout
# ---------------------------------------------------------------------------
def register(request):
    ctx = get_base_context(request)
    if request.method == "GET":
        return render(request, "register.html", ctx)

    username = request.POST.get("username", "").strip()
    password = request.POST.get("password", "")
    password2 = request.POST.get("password2", "")
    phone = request.POST.get("phone", "").strip()
    role = request.POST.get("reg_role", "buyer")
    shop_name = request.POST.get("shop_name", "").strip()

    if role not in {"buyer", "seller"}:
        role = "buyer"
    if not username or not password:
        ctx["msg"] = "用户名和密码不能为空"
        return render(request, "register.html", ctx)
    if password != password2:
        ctx["msg"] = "两次输入的密码不一致"
        return render(request, "register.html", ctx)
    if User.objects.filter(username=username).exists():
        ctx["msg"] = "用户名已被占用"
        return render(request, "register.html", ctx)

    try:
        validate_password(password, User(username=username))
    except ValidationError as exc:
        ctx["msg"] = "；".join(exc.messages)
        return render(request, "register.html", ctx)

    user = User.objects.create_user(
        username=username,
        password=password,
        role=role,
        phone=phone,
        shop_name=shop_name if role == "seller" else "",
        is_seller_approved=role != "seller",
    )
    messages.success(request, "注册成功，请登录")
    return redirect("denglu")


def denglu(request):
    ctx = get_base_context(request)
    if request.method == "GET":
        ctx["next"] = request.GET.get("next", "/")
        return render(request, "denglu.html", ctx)

    username = request.POST.get("username", "").strip()
    password = request.POST.get("password", "")
    login_type = request.POST.get("login_type", "buyer")
    if login_type not in {"buyer", "seller"}:
        login_type = "buyer"

    if not username or not password:
        ctx["msg"] = "用户名和密码不能为空"
        return render(request, "denglu.html", ctx)

    cache_key = f"login_fail_{username.lower()}"
    failures = cache.get(cache_key, 0)
    if failures >= 5:
        ctx["msg"] = "失败次数过多，请稍后再试"
        return render(request, "denglu.html", ctx)

    user = authenticate(request, username=username, password=password)
    if user is None:
        cache.set(cache_key, failures + 1, 300)
        ctx["msg"] = "用户名或密码错误"
        return render(request, "denglu.html", ctx)
    if not user.is_active:
        ctx["msg"] = "账号已被禁用"
        return render(request, "denglu.html", ctx)
    if user.role != login_type:
        ctx["msg"] = "登录入口与账号类型不匹配"
        return render(request, "denglu.html", ctx)
    if login_type == "seller" and not user.is_seller_approved:
        login(request, user)
        cache.delete(cache_key)
        return render(request, "seller_approval_pending.html", {"shop_name": user.shop_name})

    login(request, user)
    cache.delete(cache_key)
    return redirect(_safe_next(request))


@require_POST
def logout(request):
    auth_logout(request)
    return redirect("index")


# ---------------------------------------------------------------------------
# Public product browsing
# ---------------------------------------------------------------------------
def _paginate_goods(request, queryset):
    paginator = Paginator(queryset, 8)
    page_number = request.GET.get("page", 1)
    return paginator.get_page(page_number)


def index(request):
    goods = _paginate_goods(request, Goods.objects.filter(is_active=True))
    ctx = get_base_context(request)
    ctx["goods"] = goods
    return render(request, "index.html", ctx)


def category_filter(request):
    cat = request.GET.get("cat", "")
    queryset = Goods.objects.filter(is_active=True)
    if cat:
        queryset = queryset.filter(category=cat)
    goods = _paginate_goods(request, queryset)
    ctx = get_base_context(request)
    ctx["goods"] = goods
    return render(request, "index.html", ctx)


def price_filter(request):
    try:
        min_price = Decimal(str(request.GET.get("min", 0)))
        max_price = Decimal(str(request.GET.get("max", "999999")))
    except (InvalidOperation, TypeError, ValueError):
        min_price, max_price = Decimal("0"), Decimal("999999")
    queryset = Goods.objects.filter(
        is_active=True,
        price__gte=min_price,
        price__lte=max_price,
    )
    goods = _paginate_goods(request, queryset)
    ctx = get_base_context(request)
    ctx["goods"] = goods
    return render(request, "index.html", ctx)


def sort(request):
    sort_type = request.GET.get("a", "")
    queryset = Goods.objects.filter(is_active=True)
    if sort_type == "1":
        queryset = queryset.order_by("price")
    elif sort_type == "2":
        queryset = queryset.order_by("-sales_volume")
    elif sort_type == "3":
        queryset = queryset.order_by("-price")
    goods = _paginate_goods(request, queryset)
    ctx = get_base_context(request)
    ctx["goods"] = goods
    return render(request, "index.html", ctx)


@require_POST
def seek(request):
    name = request.POST.get("name", "").strip()
    queryset = Goods.objects.filter(is_active=True)
    if name:
        queryset = queryset.filter(name__icontains=name) | queryset.filter(
            goodsdesc__icontains=name
        )
    goods = _paginate_goods(request, queryset.distinct())
    ctx = get_base_context(request)
    ctx["goods"] = goods
    ctx["keyword"] = name
    return render(request, "index.html", ctx)


def xq(request):
    goods_id = request.GET.get("id")
    goods = get_object_or_404(Goods, id=goods_id, is_active=True)

    browse_arr = request.session.get("browse", [])
    if str(goods_id) not in browse_arr:
        browse_arr.append(str(goods_id))
    if len(browse_arr) > 12:
        browse_arr = browse_arr[-12:]
    request.session["browse"] = browse_arr
    request.session["current_goods_id"] = str(goods_id)

    if request.user.is_authenticated:
        BrowseHistory.objects.update_or_create(
            user=request.user,
            goods=goods,
            defaults={"browse_time": timezone.now()},
        )

    ctx = get_base_context(request)
    is_collect = (
        request.user.is_authenticated
        and request.user.role == "buyer"
        and Collect.objects.filter(user=request.user, goods=goods).exists()
    )
    ctx.update({"goods": goods, "is_collect": is_collect})
    return render(request, "xq.html", ctx)


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------
@require_POST
@buyer_required
def caradd(request):
    goods_id = request.POST.get("goods_id") or request.session.get("current_goods_id")
    goods = get_object_or_404(Goods, id=goods_id, is_active=True)
    number = _validate_positive_int(request.POST.get("number", 1))

    if number > goods.stock:
        ctx = get_base_context(request)
        ctx["goods"] = goods
        ctx["error"] = f"库存不足，当前库存：{goods.stock}"
        return render(request, "xq.html", ctx)

    item, created = Goodscar.objects.get_or_create(
        user=request.user,
        goods=goods,
        defaults={"number": number, "price": goods.price},
    )
    if not created:
        new_number = item.number + number
        if new_number > goods.stock:
            ctx = get_base_context(request)
            ctx["goods"] = goods
            ctx["error"] = f"库存不足，当前库存：{goods.stock}"
            return render(request, "xq.html", ctx)
        item.number = new_number
        item.price = goods.price
        item.save(update_fields=["number", "price", "updated_at"])
    return redirect("carlist")


@buyer_required
def carlist(request):
    cart_items = (
        Goodscar.objects.filter(user=request.user)
        .select_related("goods")
        .order_by("-created_at")
    )
    addresses = Address.objects.filter(user=request.user).order_by("-is_default")
    sum_price = sum(item.total_price for item in cart_items)
    ctx = get_base_context(request)
    ctx.update({"carlist": cart_items, "sumprice": sum_price, "addresses": addresses})
    return render(request, "carlist.html", ctx)


@require_POST
@buyer_required
def cart_change_num(request):
    item = get_object_or_404(Goodscar, id=request.POST.get("id"), user=request.user)
    op = request.POST.get("op")
    if op == "add":
        if item.number >= item.goods.stock:
            messages.error(request, "已达到库存上限")
        else:
            item.number += 1
            item.save(update_fields=["number", "updated_at"])
    elif op == "sub" and item.number > 1:
        item.number -= 1
        item.save(update_fields=["number", "updated_at"])
    return redirect("carlist")


@require_POST
@buyer_required
def cardel(request):
    item = get_object_or_404(Goodscar, id=request.POST.get("id"), user=request.user)
    request.session[f"del_cart_{item.id}"] = {
        "goods_id": item.goods_id,
        "number": item.number,
        "price": str(item.price),
    }
    item.delete()
    return redirect("carlist")


@require_POST
@buyer_required
def cart_undo(request):
    item_id = request.POST.get("id")
    key = f"del_cart_{item_id}"
    data = request.session.pop(key, None)
    if not data:
        return JsonResponse({"status": "error", "message": "没有可恢复的记录"})
    goods = Goods.objects.filter(pk=data["goods_id"], is_active=True).first()
    if not goods:
        return JsonResponse({"status": "error", "message": "商品已下架"})
    item, created = Goodscar.objects.get_or_create(
        user=request.user,
        goods=goods,
        defaults={"number": data["number"], "price": Decimal(data["price"])},
    )
    if not created:
        item.number = min(item.number + data["number"], goods.stock)
        item.save(update_fields=["number", "updated_at"])
    return JsonResponse({"status": "success"})


@require_GET
def get_cart_count(request):
    if not request.user.is_authenticated or request.user.role != "buyer":
        return JsonResponse({"status": "success", "count": 0})
    count = (
        Goodscar.objects.filter(user=request.user)
        .aggregate(total=Sum("number"))
        .get("total")
        or 0
    )
    return JsonResponse({"status": "success", "count": count})


# ---------------------------------------------------------------------------
# Addresses
# ---------------------------------------------------------------------------
@require_POST
@buyer_required
def add_address(request):
    receiver_name = request.POST.get("receiver_name", "").strip()
    phone = request.POST.get("phone", "").strip()
    detail = request.POST.get("detail", "").strip()
    if not receiver_name or not phone or not detail:
        messages.error(request, "收货人、电话和详细地址不能为空")
        return redirect("address_list")

    is_default = request.POST.get("is_default") == "on"
    with transaction.atomic():
        if is_default:
            Address.objects.filter(user=request.user).update(is_default=False)
        Address.objects.create(
            user=request.user,
            receiver_name=receiver_name,
            phone=phone,
            province=request.POST.get("province", "").strip(),
            city=request.POST.get("city", "").strip(),
            district=request.POST.get("district", "").strip(),
            detail=detail,
            is_default=is_default,
        )
    return redirect("address_list")


@buyer_required
def address_list(request):
    addresses = Address.objects.filter(user=request.user).order_by("-is_default")
    ctx = get_base_context(request)
    ctx["addresses"] = addresses
    return render(request, "address_list.html", ctx)


@require_POST
@buyer_required
def delete_address(request):
    address = get_object_or_404(Address, id=request.POST.get("id"), user=request.user)
    address.delete()
    return redirect("address_list")


@require_POST
@buyer_required
def set_default_address(request):
    address = get_object_or_404(Address, id=request.POST.get("id"), user=request.user)
    with transaction.atomic():
        Address.objects.filter(user=request.user).update(is_default=False)
        address.is_default = True
        address.save(update_fields=["is_default"])
    return redirect("address_list")


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
def _generate_order_no():
    return timezone.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:10].upper()


@require_POST
@buyer_required
def create_order(request):
    address_id = request.POST.get("address_id")
    if not address_id:
        messages.error(request, "请选择收货地址")
        return redirect("carlist")
    address = get_object_or_404(Address, id=address_id, user=request.user)
    cart_items = list(
        Goodscar.objects.filter(user=request.user).select_related("goods", "goods__seller")
    )
    if not cart_items:
        messages.warning(request, "购物车为空")
        return redirect("carlist")

    groups = defaultdict(list)
    try:
        with transaction.atomic():
            goods_map = {}
            for item in cart_items:
                goods = Goods.objects.select_for_update().get(pk=item.goods_id)
                if goods.stock < item.number:
                    raise ValidationError(f"「{goods.name}」库存不足")
                goods.stock -= item.number
                goods.save(update_fields=["stock", "updated_at"])
                goods_map[item.goods_id] = goods
                groups[goods.seller_id].append(item)

            created_orders = []
            for seller_id, items in groups.items():
                order_no = _generate_order_no()
                total = sum(item.total_price for item in items)
                order = Order.objects.create(
                    order_no=order_no,
                    user=request.user,
                    seller_id=seller_id,
                    address=address.full_address,
                    receiver_name=address.receiver_name,
                    receiver_phone=address.phone,
                    total_price=total,
                    status="unpaid",
                )
                for item in items:
                    OrderItem.objects.create(
                        order=order,
                        goods=goods_map[item.goods_id],
                        name=item.goods.name,
                        price=item.price,
                        number=item.number,
                    )
                created_orders.append(order)

            Goodscar.objects.filter(user=request.user).delete()
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if exc.messages else "下单失败")
        return redirect("carlist")

    if len(created_orders) == 1:
        return redirect("payon", order_no=created_orders[0].order_no)
    messages.success(request, f"已按店铺拆分生成 {len(created_orders)} 个订单")
    return redirect("orderlist")


@buyer_required
def payon(request, order_no):
    order = get_object_or_404(Order, order_no=order_no, user=request.user)
    ctx = get_base_context(request)
    ctx["order"] = order
    return render(request, "payon.html", ctx)


@require_POST
@buyer_required
def pay_process(request):
    order_no = request.POST.get("order_no")
    order = get_object_or_404(Order, order_no=order_no, user=request.user)
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status != "unpaid":
            messages.error(request, "订单状态已变化，不能重复支付")
            return redirect("payon", order_no=order_no)
        order.status = "paid"
        order.paid_at = timezone.now()
        order.save(update_fields=["status", "paid_at", "updated_at"])
        items = list(order.items.all())
        _increase_sales_for_items(items)
    messages.success(request, "支付成功")
    return redirect("orderlist")


@buyer_required
def orderlist(request):
    status = request.GET.get("status")
    queryset = Order.objects.filter(user=request.user).select_related("seller")
    if status:
        queryset = queryset.filter(status=status)
    orders = queryset.prefetch_related("items").order_by("-created_at")
    ctx = get_base_context(request)
    ctx["orders_list"] = orders
    return render(request, "orderlist.html", ctx)


@buyer_required
def order_detail(request, order_no):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__goods"),
        order_no=order_no,
        user=request.user,
    )
    ctx = get_base_context(request)
    ctx["order"] = order
    return render(request, "order_detail.html", ctx)


@require_POST
@buyer_required
def cancel_order(request):
    order_no = request.POST.get("order_no")
    order = get_object_or_404(Order, order_no=order_no, user=request.user)
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status != "unpaid":
            messages.error(request, "只有待支付订单可以取消")
            return redirect("order_detail", order_no=order_no)
        items = list(order.items.all())
        _restore_stock_for_items(items)
        order.status = "cancelled"
        order.cancelled_at = timezone.now()
        order.save(update_fields=["status", "cancelled_at", "updated_at"])
    messages.success(request, "订单已取消")
    return redirect("orderlist")


@require_POST
@buyer_required
def confirm_receipt(request):
    order_no = request.POST.get("order_no")
    order = get_object_or_404(Order, order_no=order_no, user=request.user)
    if order.status != "shipped":
        messages.error(request, "只有已发货订单可以确认收货")
        return redirect("order_detail", order_no=order_no)
    order.status = "completed"
    order.completed_at = timezone.now()
    order.save(update_fields=["status", "completed_at", "updated_at"])
    messages.success(request, "已确认收货")
    return redirect("order_detail", order_no=order_no)


@require_POST
@buyer_required
def update_address_before_ship(request):
    order_no = request.POST.get("order_no")
    order = get_object_or_404(Order, order_no=order_no, user=request.user)
    if order.status not in {"unpaid", "paid"}:
        return JsonResponse({"status": "error", "message": "当前状态不能修改地址"})
    new_address = request.POST.get("new_address", "").strip()
    receiver_name = request.POST.get("receiver_name", "").strip()
    receiver_phone = request.POST.get("receiver_phone", "").strip()
    if not new_address:
        return JsonResponse({"status": "error", "message": "地址不能为空"})
    order.address = new_address
    if receiver_name:
        order.receiver_name = receiver_name
    if receiver_phone:
        order.receiver_phone = receiver_phone
    order.save(update_fields=["address", "receiver_name", "receiver_phone", "updated_at"])
    return JsonResponse({"status": "success"})


@require_POST
@buyer_required
def refund(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "请求格式错误"})

    order_no = data.get("order_no")
    reason = (data.get("reason") or "").strip()
    order = get_object_or_404(Order, order_no=order_no, user=request.user)
    if order.status not in {"paid", "shipped"}:
        return JsonResponse({"status": "error", "message": "当前订单状态不能申请退款"})
    if not reason:
        return JsonResponse({"status": "error", "message": "请填写退款原因"})
    order.status = "refunding"
    order.refund_reason = reason
    order.status_before_refund = order.status
    order.save(update_fields=["status", "refund_reason", "status_before_refund", "updated_at"])
    return JsonResponse({"status": "success", "message": "退款申请已提交，等待卖家处理"})


# ---------------------------------------------------------------------------
# Favorites
# ---------------------------------------------------------------------------
@require_POST
@buyer_required
def collect_add(request):
    goods = get_object_or_404(Goods, id=request.POST.get("gid"), is_active=True)
    obj, created = Collect.objects.get_or_create(user=request.user, goods=goods)
    if created:
        return JsonResponse({"status": "add"})
    obj.delete()
    return JsonResponse({"status": "del"})


@buyer_required
def my_collect(request):
    collect_list = Collect.objects.filter(user=request.user).select_related("goods")
    ctx = get_base_context(request)
    ctx["collect_list"] = collect_list
    return render(request, "my_collect.html", ctx)


@require_POST
@buyer_required
def cancel_collect(request):
    collect = get_object_or_404(Collect, id=request.POST.get("id"), user=request.user)
    collect.delete()
    return redirect("my_collect")


# ---------------------------------------------------------------------------
# User profile
# ---------------------------------------------------------------------------
@buyer_required
def user_center(request):
    ctx = get_base_context(request)
    ctx["user"] = request.user
    return render(request, "user_center.html", ctx)


@require_POST
@buyer_required
def edit_user_info(request):
    phone = request.POST.get("phone", "").strip()
    email = request.POST.get("email", "").strip()
    if email:
        from django.core.validators import validate_email

        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "邮箱格式不正确")
            return redirect("user_center")
    request.user.phone = phone
    request.user.email = email
    request.user.save(update_fields=["phone", "email"])
    messages.success(request, "资料已更新")
    return redirect("user_center")


@require_POST
@buyer_required
def modify_pwd(request):
    old_pwd = request.POST.get("old_pwd", "")
    new_pwd = request.POST.get("new_pwd", "")
    new_pwd2 = request.POST.get("new_pwd2", "")
    if not request.user.check_password(old_pwd):
        messages.error(request, "原密码错误")
        return redirect("user_center")
    if len(new_pwd) < 8:
        messages.error(request, "新密码至少 8 位")
        return redirect("user_center")
    if new_pwd != new_pwd2:
        messages.error(request, "两次输入的新密码不一致")
        return redirect("user_center")
    try:
        validate_password(new_pwd, request.user)
    except ValidationError as exc:
        messages.error(request, "；".join(exc.messages))
        return redirect("user_center")
    request.user.set_password(new_pwd)
    request.user.save(update_fields=["password"])
    update_session_auth_hash(request, request.user)
    messages.success(request, "密码已修改")
    return redirect("user_center")


# ---------------------------------------------------------------------------
# Seller dashboard
# ---------------------------------------------------------------------------
@seller_required
def seller_goods_list(request):
    goods = Goods.objects.filter(seller=request.user).order_by("-created_at")
    return render(request, "seller_goods_list.html", {"goods_list": goods})


@seller_required
def seller_add_goods(request):
    ctx = get_base_context(request)
    ctx["category_list"] = Goods.CATEGORY_CHOICES
    if request.method == "GET":
        return render(request, "seller_add_goods.html", ctx)

    name = request.POST.get("name", "").strip()
    category = request.POST.get("category", "")
    weight = request.POST.get("weight", "").strip()
    goodsdesc = request.POST.get("goodsdesc", "").strip()
    img = request.FILES.get("imgurl")

    try:
        price = _validate_decimal(request.POST.get("price"))
        stock = int(request.POST.get("stock", "0"))
    except (ValidationError, ValueError):
        ctx["err"] = "价格和库存必须是有效数字"
        return render(request, "seller_add_goods.html", ctx)

    if not all([name, category, weight, img]):
        ctx["err"] = "商品名称、分类、规格和图片为必填项"
        return render(request, "seller_add_goods.html", ctx)
    if price <= 0 or stock < 0:
        ctx["err"] = "价格必须大于 0，库存不能为负数"
        return render(request, "seller_add_goods.html", ctx)
    if category not in dict(Goods.CATEGORY_CHOICES):
        ctx["err"] = "请选择有效分类"
        return render(request, "seller_add_goods.html", ctx)
    if img.size > 5 * 1024 * 1024:
        ctx["err"] = "图片不能超过 5MB"
        return render(request, "seller_add_goods.html", ctx)

    Goods.objects.create(
        name=name,
        category=category,
        price=price,
        weight=weight,
        stock=stock,
        goodsdesc=goodsdesc,
        imgurl=img,
        seller=request.user,
        is_active=True,
    )
    messages.success(request, "商品已上架")
    return redirect("seller_goods_list")


@require_POST
@seller_required
def seller_del_goods(request):
    goods = get_object_or_404(Goods, id=request.POST.get("id"), seller=request.user)
    goods.is_active = False
    goods.save(update_fields=["is_active", "updated_at"])
    messages.success(request, "商品已下架")
    return redirect("seller_goods_list")


@seller_required
def seller_orders(request):
    orders = (
        Order.objects.filter(seller=request.user)
        .select_related("user")
        .prefetch_related("items__goods")
        .order_by("-created_at")
    )
    return render(request, "seller_orders.html", {"orders": orders})


@require_POST
@seller_required
def seller_ship(request, order_no):
    order = get_object_or_404(Order, order_no=order_no, seller=request.user)
    tracking_no = request.POST.get("tracking_no", "").strip()
    if order.status != "paid":
        messages.error(request, "只有已支付订单可以发货")
        return redirect("seller_orders")
    if not tracking_no:
        messages.error(request, "请填写物流单号")
        return redirect("seller_orders")
    order.status = "shipped"
    order.tracking_no = tracking_no
    order.shipped_at = timezone.now()
    order.save(update_fields=["status", "tracking_no", "shipped_at", "updated_at"])
    messages.success(request, "已发货")
    return redirect("seller_orders")


@require_POST
@seller_required
def seller_refund_approve(request, order_no):
    order = get_object_or_404(Order, order_no=order_no, seller=request.user)
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status != "refunding":
            messages.error(request, "该订单不在退款申请状态")
            return redirect("seller_orders")
        items = list(order.items.all())
        _restore_stock_for_items(items)
        _decrease_sales_for_items(items)
        order.status = "refunded"
        order.save(update_fields=["status", "updated_at"])
    messages.success(request, "退款已通过")
    return redirect("seller_orders")


@require_POST
@seller_required
def seller_refund_reject(request, order_no):
    order = get_object_or_404(Order, order_no=order_no, seller=request.user)
    if order.status != "refunding":
        messages.error(request, "该订单不在退款申请状态")
        return redirect("seller_orders")
    order.status = order.status_before_refund or "paid"
    order.refund_reason = ""
    order.status_before_refund = ""
    order.save(update_fields=["status", "refund_reason", "status_before_refund", "updated_at"])
    messages.success(request, "已驳回退款申请")
    return redirect("seller_orders")
