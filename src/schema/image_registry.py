from sqlalchemy import Column, Integer, String
from sqlalchemy.dialects.mysql import LONGTEXT
from .init_db import Base


class ImageRegistry(Base):
    __tablename__ = "image_registry"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    version = Column(String(255), nullable=False)
    description = Column(LONGTEXT, nullable=False)
    username = Column(String(255), nullable=False)
    group = Column(String(255), nullable=False)
