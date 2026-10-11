from fastapi import APIRouter

from app.core.exceptions import BusinessError, ok
from app.services import product_service

router = APIRouter(prefix="/api/product", tags=["商品接口"])


@router.get("/list", summary="商品列表（Redis 缓存）")
def list_products():
    return ok(product_service.list_products())


@router.get("/{product_id}", summary="商品详情（Redis 缓存）")
def get_product(product_id: int):
    product = product_service.get_product(product_id)
    if product is None:
        raise BusinessError("商品不存在", 404)
    product["stock"] = product_service.get_stock(product_id)
    return ok(product)
