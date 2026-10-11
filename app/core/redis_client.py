import redis

from app.core.config import settings

# 全局单例（redis-py 内部自带连接池，线程安全）
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    password=settings.REDIS_PASSWORD or None,
    decode_responses=True,
)
