from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from .init_db import Base
from pydantic import BaseModel, ValidationError, root_validator


class ContainerModel(BaseModel):
    name: str
    url: str = None
    tag: str = None
    
    class Config:
        orm_mode = True

class Container(Base):
    __tablename__ = "container"
    __table_args__ = (
        UniqueConstraint('url', 'tag', name='unique_url_tag'),
    )

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, nullable=True)
    tag = Column(String, nullable=True)
    name = Column(String, nullable=True)
    dockerfile = Column(String, nullable=True)