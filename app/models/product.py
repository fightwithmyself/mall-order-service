from sqlalchemy import Column, Integer, String, DECIMAL
from app.core.mysql_client import Base

class Product(Base):
    __tablename__ = "product"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="商品id")
    product_name = Column(String(128), nullable=False, comment="商品名称")
    stock = Column(Integer, nullable=False, default=0, comment="库存数量")
    price = Column(DECIMAL(10,2), nullable=False, comment="商品单价")
