from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """统一从环境变量 / .env 读取配置，未配置时使用本地默认值"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # MySQL
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DB: str = "mall_order"

    # Redis
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""

    # RabbitMQ
    RABBITMQ_HOST: str = "127.0.0.1"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASS: str = "guest"

    # 业务参数
    ORDER_TIMEOUT_SECONDS: int = 30 * 60   # 未支付自动关单时间，调试可设为 30
    PRODUCT_CACHE_TTL: int = 300           # 商品缓存基础过期时间（秒），实际会加随机抖动
    RATE_LIMIT_CREATE_ORDER: int = 10      # 下单限流：每个窗口内每个 IP 最多请求次数
    RATE_LIMIT_WINDOW: int = 60            # 限流窗口（秒）

    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def mysql_url(self) -> str:
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}?charset=utf8mb4"
        )


settings = Settings()
