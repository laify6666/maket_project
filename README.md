# Django 商城项目（改进版）
这是基于我课程作业重新改进开发的线上商城系统，基于django框架，用ai辅助开发的项目
## 快速开始
如果有便携版，则直接看便携包说明即可，若没有则
打开终端输入以下命令
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```
（记得要安装python）```

演示账号：

- 买家：`buyer / buyer123456`
- 卖家：`seller / seller123456`

## 常用命令

```bash
python manage.py check
python manage.py test buy
python manage.py release_expired_orders --minutes 30
```

## 改进要点

- 新增 `MEDIA_ROOT/MEDIA_URL`，商品图片独立存放于 `media/goods/`。
- 用户改用 Django auth 体系，登录限流、session 轮换、密码校验。
- 购物车、地址、订单、收藏、浏览记录全部改为外键关联。
- 价格改为 `DecimalField`，订单按卖家拆分，下单预占库存并使用行锁。
- 订单状态机覆盖待支付、已支付、已发货、已完成、已取消、退款中、已退款。
- 卖家注册需平台审核，卖家可上架/下架商品、发货、处理退款。
- 状态变更统一使用 POST + CSRF，并补齐对象级归属校验。
- 增加核心业务测试与 CI。
