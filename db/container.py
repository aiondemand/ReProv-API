from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from .init_db import Base
from pydantic import BaseModel, ValidationError, root_validator


class ContainerModel(BaseModel):
    url: str = None
    tag: str = None
    name: str = None
    dockerfile: str = None

    @root_validator(pre=True)
    def check_exclusive_fields(cls, values):
        url = values.get("url")
        tag = values.get("tag")
        dockerfile = values.get("dockerfile")

        if url is not None and tag is not None and dockerfile is not None:
            raise ValueError("Either 'url' and 'tag' or 'dockerfile' should be provided, not both.")

        if (url is None or tag is None) and dockerfile is None:
            raise ValueError("Either 'url' and 'tag' or 'dockerfile' should be provided.")

        return values
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