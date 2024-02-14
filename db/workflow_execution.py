from typing import List, Union
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from datetime import datetime
from .init_db import Base
from pydantic import BaseModel

class WorkflowExecution(Base):
    __tablename__ = "workflow_execution"
   
 
    id = Column(Integer, primary_key=True, index=True)
    registry_id = Column(Integer, ForeignKey("workflow_registry.id"))
    start_time = Column(DateTime, default=datetime.utcnow,)
    end_time = Column(DateTime, nullable=True)
    status = Column(String, default="queued")
    reana_id = Column(String, nullable=True)
    reana_name = Column(String, nullable=True)
    reana_run_number = Column(String, nullable=True)