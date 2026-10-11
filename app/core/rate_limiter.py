import time
import uuid

from fastapi import Request

from app.core.exceptions import BusinessError
from app.core.redis_client import redis_client

# 滑动窗口限流（ZSET）：窗口内请求数 >= limit 则拒绝。
# 时间戳由调用方传入，Lua 内不使用 TIME，兼容 Redis 3.x。
_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call('zremrangebyscore', key, 0, now - window)
if redis.call('zcard', key) >= limit then
    return 0
end
redis.call('zadd', key, now, ARGV[4])
redis.call('pexpire', key, window)
return 1
"""


def is_allowed(key: str, limit: int, window_seconds: int) -> bool:
    now_ms = int(time.time() * 1000)
    member = f"{now_ms}-{uuid.uuid4().hex[:8]}"
    res = redis_client.eval(_SLIDING_WINDOW_LUA, 1, key, now_ms, window_seconds * 1000, limit, member)
    return int(res) == 1


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:                       # 部署在 Nginx 后面时取真实客户端 IP
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(scope: str, limit: int, window_seconds: int):
    """生成 FastAPI 依赖：按 客户端IP + scope 限流"""

    def dependency(request: Request):
        key = f"rate:{scope}:{client_ip(request)}"
        if not is_allowed(key, limit, window_seconds):
            raise BusinessError(f"请求过于频繁，请 {window_seconds} 秒后再试", status_code=429)

    return dependency
