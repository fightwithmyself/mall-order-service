from fastapi import APIRouter, Depends, Query

from app.core.config import settings
from app.core.exceptions import ok
from app.core.rate_limiter import rate_limit
from app.schemas.order_schema import OrderCreateReq
from app.services import order_service

router = APIRouter(prefix="/api/order", tags=["订单接口"])


@router.post(
    "/create",
    summary="创建订单",
    dependencies=[Depends(rate_limit("create_order", settings.RATE_LIMIT_CREATE_ORDER, settings.RATE_LIMIT_WINDOW))],
)
def create_order(req: OrderCreateReq):
    """限流 → 商品缓存 → 分布式锁 → Redis Lua 预扣库存 → MySQL 待支付订单 → 投递 MQ（扣库存 + 超时关单）"""
    return ok(order_service.create_order(req), "下单成功")


@router.get("/list", summary="按用户查询订单列表")
def list_orders(user_id: int = Query(gt=0)):
    return ok(order_service.list_orders(user_id))


@router.get("/{order_id}", summary="查询订单详情")
def get_order(order_id: int):
    return ok(order_service.get_order(order_id))


@router.post("/{order_id}/pay", summary="模拟支付")
def pay_order(order_id: int):
    return ok(order_service.pay_order(order_id), "支付成功")


@router.post("/{order_id}/cancel", summary="取消订单")
def cancel_order(order_id: int):
    return ok(order_service.cancel_order(order_id), "订单已取消")
