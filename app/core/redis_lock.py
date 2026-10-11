import time
import uuid

from app.core.redis_client import redis_client

# 只有持有者（token 一致）才能释放锁，避免锁过期后误删别人的锁。
# 不使用 TIME 等非确定性命令，兼容 Redis 3.x。
_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""


class LockAcquireError(Exception):
    pass


class RedisLock:
    """基于 SET NX EX 的分布式锁，可用作 with 上下文管理器

    :param key: 锁 key
    :param ttl: 锁自动过期时间（秒），防止持有者宕机造成死锁
    :param wait: 最长等待获取时间（秒），0 表示拿不到立刻失败
    """

    def __init__(self, key: str, ttl: int = 10, wait: float = 0, retry_interval: float = 0.05):
        self.key = key
        self.ttl = ttl
        self.wait = wait
        self.retry_interval = retry_interval
        self.token = uuid.uuid4().hex
        self._locked = False

    def acquire(self) -> bool:
        deadline = time.monotonic() + self.wait
        while True:
            if redis_client.set(self.key, self.token, nx=True, ex=self.ttl):
                self._locked = True
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(self.retry_interval)

    def release(self) -> None:
        if self._locked:
            redis_client.eval(_RELEASE_LUA, 1, self.key, self.token)
            self._locked = False

    def __enter__(self):
        if not self.acquire():
            raise LockAcquireError(self.key)
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False
