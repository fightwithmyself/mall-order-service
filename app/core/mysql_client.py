from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# 创建数据库引擎，配置连接池
engine = create_engine(
    settings.mysql_url,
    pool_pre_ping=True,      # 自动检测连接是否失效，自动重连
    pool_size=10,            # 连接池常驻连接数
    max_overflow=20         # 突发最大额外连接
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 获取数据库会话依赖（FastAPI接口注入用）
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
