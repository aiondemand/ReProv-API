from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
from datetime import datetime
from .init_db import Base
from sqlalchemy.orm import relationship


class Entity(Base):
    __tablename__ = 'entity'

    id = Column(Integer, autoincrement=True, primary_key=True)
    type = Column(Enum('workflow', 'workflow_intermediate_result_file', 'workflow_final_result_file'))
    path = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    size = Column(String(255), nullable=True)
    last_modified = Column(DateTime, nullable=True)

    workflow_execution_id = Column(Integer, ForeignKey('workflow_execution.id'))
    started = relationship("ActivityStartedBy", back_populates='entity')
    ended = relationship("ActivityEndedBy", back_populates='entity')


class Activity(Base):
    __tablename__ = 'activity'

    id = Column(Integer, autoincrement=True, primary_key=True)
    type = Column(Enum('workflow_execution', 'step_execution'))
    name = Column(String(255), nullable=False)
    start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_time = Column(DateTime, nullable=True)

    workflow_execution_id = Column(Integer, ForeignKey('workflow_execution.id'))
    # Use backref directly
    generated = relationship("Entity", secondary='entity_generated_by')
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


class ActivityStartedBy(Base):
    __tablename__ = "activity_started_by"

    id = Column(Integer, primary_key=True)
    activity_id = Column(Integer, ForeignKey('activity.id'))
    entity_id = Column(Integer, ForeignKey('entity.id'))
    time = Column(DateTime, nullable=False)

    entity = relationship("Entity", back_populates="started")


class ActivityEndedBy(Base):
    __tablename__ = "activity_ended_by"

    id = Column(Integer, primary_key=True)
    activity_id = Column(Integer, ForeignKey('activity.id'))
    entity_id = Column(Integer, ForeignKey('entity.id'))
    time = Column(DateTime, nullable=False)

    entity = relationship("Entity", back_populates="ended")
