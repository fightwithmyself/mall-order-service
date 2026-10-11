from sqlalchemy import Column, Integer, Numeric, String

from app.core.mysql_client import Base


class Product(Base):
    __tablename__ = "product"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="商品id")
    product_name = Column(String(128), nullable=False, comment="商品名称")
    description = Column(String(255), nullable=True, comment="商品描述")
    image = Column(String(255), nullable=True, comment="商品图片（emoji或URL）")
    stock = Column(Integer, nullable=False, default=0, comment="库存数量（MySQL，最终一致）")
    price = Column(Numeric(10, 2), nullable=False, comment="商品单价")
