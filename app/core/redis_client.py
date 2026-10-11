import redis
from app.core.config import settings

# 创建redis连接池，复用连接（关键！高并发不要每次新建连接）
redis_pool = redis.ConnectionPool(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    decode_responses=True
)
redis = redis.Redis(connection_pool=redis_pool)
