from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime
from .init_db import Base


class WorkflowExecution(Base):
    __tablename__ = "workflow_execution"

    id = Column(Integer, primary_key=True, index=True)
    start_time = Column(DateTime, default=datetime.utcnow,)
    end_time = Column(DateTime, nullable=True)
    status = Column(String(255), default="queued")
    reana_id = Column(String(255), nullable=True)
    reana_name = Column(String(255), nullable=True)
    reana_run_number = Column(String(255), nullable=True)

    registry_id = Column(Integer, ForeignKey("workflow_registry.id"))

    # Add username/group here as well because user A from group G can register a workflow but user B from group G can execute it
    username = Column(String(255), nullable=False)
    group = Column(String(255), nullable=False)


class WorkflowExecutionStep(Base):
    __tablename__ = "workflow_execution_step"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    status = Column(String(255), default="running")
    start_time = Column(DateTime, default=datetime.utcnow,)
    end_time = Column(DateTime, nullable=True)

    workflow_execution_id = Column(Integer, ForeignKey("workflow_execution.id"))
