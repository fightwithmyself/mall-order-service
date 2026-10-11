"""商品缓存与库存缓存

缓存策略：
- 商品静态信息 product:{id} / product:list：缓存 + 随机 TTL 抖动（防雪崩）
- 不存在的商品缓存空值 "null" 短时间（防穿透）
- 缓存未命中时用分布式锁串行重建，其余请求等待后复用结果（防击穿）
- 库存 stock:{id} 单独存储，只有 Redis Lua 能扣减，MySQL 库存由消费者异步扣减
"""
import json
import random
from typing import Optional

from app.core.config import settings
from app.core.mysql_client import SessionLocal
from app.core.redis_client import redis_client
from app.core.redis_lock import LockAcquireError, RedisLock
from app.models.product import Product

NULL_MARK = "null"
NULL_TTL = 60
LIST_KEY = "product:list"


def stock_key(product_id: int) -> str:
    return f"stock:{product_id}"


def _ttl() -> int:
    return settings.PRODUCT_CACHE_TTL + random.randint(0, 60)


def _to_dict(p: Product) -> dict:
    return {
        "id": p.id,
        "product_name": p.product_name,
        "description": p.description,
        "image": p.image,
        "price": float(p.price),
    }


# ---------------- 商品详情 ----------------

def get_product(product_id: int) -> Optional[dict]:
    """读取商品静态信息（不含库存）；商品不存在返回 None"""
    key = f"product:{product_id}"
    cached = redis_client.get(key)
    if cached is not None:
        return None if cached == NULL_MARK else json.loads(cached)

    try:
        with RedisLock(f"lock:{key}", ttl=10, wait=3):
            cached = redis_client.get(key)      # 拿到锁后二次检查，别人可能已重建
            if cached is not None:
                return None if cached == NULL_MARK else json.loads(cached)
            return _load_product_from_db(product_id, key)
    except LockAcquireError:
        return _load_product_from_db(product_id, key)   # 等锁超时则降级直接查库


def _load_product_from_db(product_id: int, key: str) -> Optional[dict]:
    with SessionLocal() as sess:
        p = sess.get(Product, product_id)
        if p is None:
            redis_client.set(key, NULL_MARK, ex=NULL_TTL)
            return None
        data = _to_dict(p)
        redis_client.set(key, json.dumps(data, ensure_ascii=False), ex=_ttl())
        return data


# ---------------- 库存 ----------------

def ensure_stock_loaded(product_id: int) -> bool:
    """库存 key 不存在时，从 MySQL 加载进 Redis；商品不存在返回 False"""
    key = stock_key(product_id)
    if redis_client.exists(key):
        return True
    try:
        with RedisLock(f"lock:stock_load:{product_id}", ttl=10, wait=3):
            if redis_client.exists(key):
                return True
            with SessionLocal() as sess:
                p = sess.get(Product, product_id)
                if p is None:
                    return False
                redis_client.set(key, p.stock, nx=True)
                return True
    except LockAcquireError:
        return bool(redis_client.exists(key))


def get_stock(product_id: int) -> int:
    ensure_stock_loaded(product_id)
    val = redis_client.get(stock_key(product_id))
    return max(int(val), 0) if val is not None else 0


# ---------------- 商品列表 ----------------

def list_products() -> list[dict]:
    """商品列表：静态信息走缓存，库存实时取自 Redis"""
    cached = redis_client.get(LIST_KEY)
    if cached is not None:
        items = json.loads(cached)
    else:
        try:
            with RedisLock(f"lock:{LIST_KEY}", ttl=10, wait=3):
                cached = redis_client.get(LIST_KEY)
                items = json.loads(cached) if cached is not None else _load_list_from_db()
        except LockAcquireError:
            items = _load_list_from_db()

    for item in items:
        item["stock"] = get_stock(item["id"])
    return items


def _load_list_from_db() -> list[dict]:
    with SessionLocal() as sess:
        products = sess.query(Product).order_by(Product.id).all()
        items = [_to_dict(p) for p in products]
    redis_client.set(LIST_KEY, json.dumps(items, ensure_ascii=False), ex=_ttl())
    return items


def clear_product_cache(product_id: Optional[int] = None) -> None:
    """商品信息变更后调用，使缓存失效"""
    redis_client.delete(LIST_KEY)
    if product_id is not None:
        redis_client.delete(f"product:{product_id}")
