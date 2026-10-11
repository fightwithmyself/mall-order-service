from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

# 加载项目根目录.env文件
load_dotenv()

class Settings(BaseSettings):
    # MySQL
    MYSQL_HOST: str = os.getenv("MYSQL_HOST")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT"))
    MYSQL_USER: str = os.getenv("MYSQL_USER")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD")
    MYSQL_DB: str = os.getenv("MYSQL_DB")

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT"))

    # RabbitMQ
    RABBITMQ_HOST: str = os.getenv("RABBITMQ_HOST")
    RABBITMQ_PORT: int = int(os.getenv("RABBITMQ_PORT"))
    RABBITMQ_USER: str = os.getenv("RABBITMQ_USER")
    RABBITMQ_PASS: str = os.getenv("RABBITMQ_PASS")

    @property
    def mysql_url(self):
        return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"

settings = Settings()
