from typing import List, Union
from sqlalchemy import Column, Integer, String, UniqueConstraint
from .init_db import Base
from pydantic import BaseModel

class WorkflowModel(BaseModel):
    name: str
    version: str
    class Config:
        orm_mode = True


class Workflow(Base):
    __tablename__ = "workflow"
    # __table_args__ = (
    #     UniqueConstraint('name', 'version', name='uq_name_version'),
    # )

 
    id = Column(Integer, primary_key=True, index=True, autoincrement=True) # PK of table
    reana_id = Column(String, nullable=False) # ID assigned to workflow by REANA
    name = Column(String, nullable=False)
    reana_name = Column(String, nullable=False) # name assigned to workflow by REANA
    version = Column(String, nullable=False)
    spec_file = Column(String, nullable=False)
    input_file = Column(String, nullable=True)