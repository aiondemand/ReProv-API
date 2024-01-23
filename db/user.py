from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from .init_db import Base
from pydantic import BaseModel

class UserModel(BaseModel):
    username: str
    password: str
    class Config:
        orm_mode = True

class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=False)