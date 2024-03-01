from typing import List, Union
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Enum, Table
from datetime import datetime
from .init_db import Base
from pydantic import BaseModel
from sqlalchemy.orm import relationship




class Entity(Base):
    __tablename__ = 'entity'
    
    id = Column(Integer, autoincrement=True, primary_key=True)
    type = Column(Enum('workflow', 'workflow_intermediate_result_file', 'workflow_final_result_file'))
    path = Column(String, nullable=False)
    name = Column(String, nullable=False)
    size = Column(Integer, nullable=True)
    last_modified = Column(DateTime, nullable=True)

    used_by = relationship('Activity', secondary='entity_activity', back_populates='generated_by')




class Activity(Base):
    __tablename__ = 'activity'
    
    id = Column(Integer, autoincrement=True, primary_key=True)
    type = Column(Enum('workflow_execution', 'step_execution'))
    start_time = Column(DateTime, default=datetime.utcnow,)
    end_time = Column(DateTime, nullable=True)

    generated_by = relationship('Entity', secondary='entity_activity', back_populates='used_by')



class EntityActivity(Base):
    __tablename__ = "entity_activity"

    id = Column(Integer, primary_key=True)
    entity_id = Column(String, ForeignKey('entity.id'))
    activity_id = Column(Integer, ForeignKey('activity.id'))