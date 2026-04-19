from sqlalchemy import Column, String, JSON, DateTime, Integer
from sqlalchemy.sql import func
from app.core.database import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, nullable=True, index=True)
    idea = Column(String, nullable=False)
    config = Column(JSON, nullable=True)
    run_state = Column(String, default="INITIALIZING", index=True)
    error = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

class GlobalState(Base):
    __tablename__ = "global_state"
    
    id = Column(String, primary_key=True, index=True)
    run_state = Column(String, default="INITIALIZING")
    project_brief = Column(JSON, nullable=True)
    phases = Column(JSON, nullable=True)
    artifacts = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class AgentRun(Base):
    __tablename__ = "agent_runs"
    
    id = Column(String, primary_key=True, index=True)
    global_state_id = Column(String, index=True)
    agent_name = Column(String, index=True)
    iteration = Column(Integer, default=1)
    status = Column(String, default="RUNNING")
    output = Column(JSON, nullable=True)
    error = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
