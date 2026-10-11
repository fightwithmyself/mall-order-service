from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# 全项目唯一的 ORM Base，所有模型都从这里导入
Base = declarative_base()

engine = create_engine(settings.mysql_url, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class MysqlClient:
    @staticmethod
    def get_session():
        return SessionLocal()
