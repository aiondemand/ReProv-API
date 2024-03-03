from typing import List, Union
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
from datetime import datetime
from .init_db import Base
from .workflow_execution import WorkflowExecution
from sqlalchemy.orm import relationship



class Entity(Base):
    __tablename__ = 'entity'

    id = Column(Integer, autoincrement=True, primary_key=True)
    type = Column(Enum('workflow', 'workflow_intermediate_result_file', 'workflow_final_result_file'))
    path = Column(String, nullable=False)
    name = Column(String, nullable=False)
    size = Column(Integer, nullable=True)
    last_modified = Column(DateTime, nullable=True)

    workflow_execution_id = Column(Integer, ForeignKey('workflow_execution.id'))  

class Activity(Base):
    __tablename__ = 'activity'

    id = Column(Integer, autoincrement=True, primary_key=True)
    type = Column(Enum('workflow_execution', 'step_execution'))
    name = Column(String, nullable=False)
    start_time = Column(DateTime, default=datetime.utcnow, nullable=False)  
    end_time = Column(DateTime, nullable=True)

    workflow_execution_id = Column(Integer, ForeignKey('workflow_execution.id'))  
    # Use backref directly
    generated = relationship("Entity",secondary='entity_generated_by')
    used = relationship("Entity", secondary='entity_used_by')

class EntityUsedBy(Base):
    __tablename__ = "entity_used_by"

    id = Column(Integer, primary_key=True)
    entity_id = Column(Integer, ForeignKey('entity.id'))  
    activity_id = Column(Integer, ForeignKey('activity.id'))  


class EntityGeneratedBy(Base):
    __tablename__ = "entity_generated_by"

    id = Column(Integer, primary_key=True)
    entity_id = Column(Integer, ForeignKey('entity.id')) 
    activity_id = Column(Integer, ForeignKey('activity.id'))  
