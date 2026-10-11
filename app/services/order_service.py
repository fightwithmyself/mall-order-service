import logging
import random
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, update

from app.core.config import settings
from app.core.exceptions import BusinessError
from app.core.mq_client import MQClient
from app.core.mysql_client import SessionLocal
from app.core.redis_client import redis_client
from app.core.redis_lock import RedisLock
from app.models.order import STATUS_TEXT, Order, OrderStatus
from app.models.product import Product
from app.schemas.order_schema import OrderCreateReq, OrderResp
from app.services import product_service
from app.services.product_service import stock_key

logger = logging.getLogger("order")

mq_client = MQClient()

# Redis 原子预扣库存：返回 1 成功 / 0 库存不足 / -1 库存未加载
_DEDUCT_LUA = """
local stock = redis.call('get', KEYS[1])
if not stock then
    return -1
end
if tonumber(stock) >= tonumber(ARGV[1]) then
    redis.call('decrby', KEYS[1], ARGV[1])
    return 1
end
return 0
"""


def _gen_order_no() -> str:
    return f"{datetime.now():%Y%m%d%H%M%S}{random.randint(0, 999999):06d}"


def _deduct_redis_stock(product_id: int, buy_num: int) -> None:
    key = stock_key(product_id)
    res = int(redis_client.eval(_DEDUCT_LUA, 1, key, buy_num))
    if res == -1:                                   # 缓存里还没有库存，从 MySQL 加载后重试
        if not product_service.ensure_stock_loaded(product_id):
            raise BusinessError("商品不存在", 404)
        res = int(redis_client.eval(_DEDUCT_LUA, 1, key, buy_num))
    if res != 1:
        raise BusinessError("库存不足", 409)


def _restore_redis_stock(product_id: int, buy_num: int) -> None:
    try:
        redis_client.incrby(stock_key(product_id), buy_num)
    except Exception:
        logger.exception("归还 Redis 库存失败 product_id=%s buy_num=%s", product_id, buy_num)


# ---------------------------------------------------------------- 创建订单

def create_order(req: OrderCreateReq) -> dict:
    """下单流程：
    1. 读商品缓存（校验商品存在、获取单价）
    2. 同一用户同一商品加分布式锁，防止重复提交
    3. Redis Lua 原子预扣库存（防超卖）
    4. MySQL 写入「待支付」订单；失败则归还 Redis 库存
    5. 投递 2 条消息：异步扣库存消息、30 分钟超时消息；投递失败则关闭订单并归还库存
    """
    product = product_service.get_product(req.product_id)
    if product is None:
        raise BusinessError("商品不存在", 404)

    lock = RedisLock(f"lock:order:{req.user_id}:{req.product_id}", ttl=5, wait=0)
    if not lock.acquire():
        raise BusinessError("请勿重复提交订单", 409)

    try:
        _deduct_redis_stock(req.product_id, req.buy_num)

        order_id = None
        sess = SessionLocal()
        try:
            order = Order(
                order_no=_gen_order_no(),
                user_id=req.user_id,
                product_id=req.product_id,
                buy_num=req.buy_num,
                total_price=Decimal(str(product["price"])) * req.buy_num,
                status=OrderStatus.PENDING_PAY.value,
            )
            sess.add(order)
            sess.commit()
            order_id = order.id
            order_no = order.order_no
        except Exception:
            sess.rollback()
            _restore_redis_stock(req.product_id, req.buy_num)
            raise
        finally:
            sess.close()

        try:
            mq_client.publish_timeout_msg(order_id)
            mq_client.publish_stock_msg(order_id, req.product_id, req.buy_num, uuid.uuid4().hex)
        except Exception:
            logger.exception("MQ 投递失败，关闭订单 order_id=%s", order_id)
            close_order(order_id, OrderStatus.CANCEL_MANUAL)
            raise BusinessError("系统繁忙，下单失败，请稍后重试", 503)

        return {"order_id": order_id, "order_no": order_no}
    finally:
        lock.release()


# ---------------------------------------------------------------- 支付 / 关单

def pay_order(order_id: int) -> dict:
    """模拟支付：仅「待支付」订单可支付，行锁保证与超时关单互斥"""
    with SessionLocal() as sess:
        order = sess.execute(select(Order).where(Order.id == order_id).with_for_update()).scalar_one_or_none()
        if order is None:
            raise BusinessError("订单不存在", 404)
        if order.status == OrderStatus.PAID.value:
            return to_resp(order).model_dump(mode="json")        # 幂等：重复支付直接返回
        if order.status != OrderStatus.PENDING_PAY.value:
            raise BusinessError(f"订单{STATUS_TEXT[order.status]}，无法支付", 409)
        order.status = OrderStatus.PAID.value
        order.pay_time = datetime.now()
        sess.commit()
        sess.refresh(order)
        return to_resp(order).model_dump(mode="json")


def close_order(order_id: int, to_status: OrderStatus) -> bool:
    """关闭待支付订单并归还库存（超时关单 / 手动取消 / 下单补偿 共用）

    返回 True 表示本次确实关闭了订单；订单已支付或已关闭则返回 False（幂等）。
    用 SELECT ... FOR UPDATE 与「支付」「库存消费者」互斥。
    """
    with SessionLocal() as sess:
        order = sess.execute(select(Order).where(Order.id == order_id).with_for_update()).scalar_one_or_none()
        if order is None or order.status != OrderStatus.PENDING_PAY.value:
            return False
        order.status = to_status.value
        if order.stock_deducted:                    # 消费者已扣过 MySQL 库存才需要加回
            sess.execute(
                update(Product).where(Product.id == order.product_id).values(stock=Product.stock + order.buy_num)
            )
        product_id, buy_num = order.product_id, order.buy_num
        sess.commit()

    _restore_redis_stock(product_id, buy_num)
    return True


def cancel_order(order_id: int) -> dict:
    with SessionLocal() as sess:
        order = sess.get(Order, order_id)
        if order is None:
            raise BusinessError("订单不存在", 404)
        status = order.status
    if status != OrderStatus.PENDING_PAY.value:
        raise BusinessError(f"订单{STATUS_TEXT[status]}，无法取消", 409)
    if not close_order(order_id, OrderStatus.CANCEL_MANUAL):
        raise BusinessError("订单状态已变化，无法取消", 409)
    return get_order(order_id)


# ---------------------------------------------------------------- 查询

def to_resp(order: Order) -> OrderResp:
    product = product_service.get_product(order.product_id)
    remaining = 0
    if order.status == OrderStatus.PENDING_PAY.value:
        elapsed = (datetime.now() - order.create_time).total_seconds()
        remaining = max(0, int(settings.ORDER_TIMEOUT_SECONDS - elapsed))
    return OrderResp(
        id=order.id,
        order_no=order.order_no,
        user_id=order.user_id,
        product_id=order.product_id,
        product_name=product["product_name"] if product else None,
        buy_num=order.buy_num,
        total_price=float(order.total_price),
        status=order.status,
        status_text=STATUS_TEXT.get(order.status, "未知"),
        create_time=order.create_time,
        pay_time=order.pay_time,
        remaining_seconds=remaining,
    )


def get_order(order_id: int) -> dict:
    with SessionLocal() as sess:
        order = sess.get(Order, order_id)
        if order is None:
            raise BusinessError("订单不存在", 404)
        return to_resp(order).model_dump(mode="json")


def list_orders(user_id: int, limit: int = 50) -> list[dict]:
    with SessionLocal() as sess:
        orders = (
            sess.query(Order).filter(Order.user_id == user_id).order_by(Order.id.desc()).limit(limit).all()
        )
        return [to_resp(o).model_dump(mode="json") for o in orders]
