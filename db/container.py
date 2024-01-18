from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from .init_db import Base
from pydantic import BaseModel

class ContainerModel(BaseModel):
    url: str
    tag: str = 'latest'
    name: str = None
    dockerfile: str = None
    class Config:
        orm_mode = True

class Container(Base):
    __tablename__ = "container"
    __table_args__ = (
        UniqueConstraint('url', 'tag', name='unique_url_tag'),
    )

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, nullable=False)
    tag = Column(String, default='latest', nullable=True)
    name = Column(String, nullable=True)
    dockerfile = Column(String, nullable=True)