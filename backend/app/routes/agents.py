from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models import Agent
from ..schemas import AgentResponse

router = APIRouter(prefix="/agents", tags=["Agents"])

@router.get("", response_model=List[AgentResponse])
def list_agents(db: Session = Depends(get_db)):
    """Returns the 9 Arvo support agents."""
    return db.query(Agent).order_by(Agent.id.asc()).all()

@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent
