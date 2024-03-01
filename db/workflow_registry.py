from typing import List, Union
from sqlalchemy import Column, Integer, String, UniqueConstraint
from .init_db import Base
from pydantic import BaseModel

class WorkflowRegistryModel(BaseModel):
    name: str
    version: str
    class Config:
        orm_mode = True


class WorkflowRegistry(Base):
    __tablename__ = "workflow_registry"
    # __table_args__ = (
    #     UniqueConstraint('name', 'version', name='uq_name_version'),
    # )

 
    id = Column(Integer, primary_key=True, index=True, autoincrement=True) # PK of table
    name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    spec_file_content = Column(String, nullable=False)
    input_file_content = Column(String, nullable=True)