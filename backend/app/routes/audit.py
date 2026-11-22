from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models import AuditLog, Ticket
from ..schemas import AuditLogResponse

router = APIRouter(prefix="/audit", tags=["Audit Trail"])

@router.get("/ticket/{ticket_id}", response_model=List[AuditLogResponse])
def get_ticket_audit_trail(ticket_id: int, db: Session = Depends(get_db)):
    """
    Incident 4.3: Immutable audit trail.
    Returns chronological timeline of what happened, when it happened, and who did it.
    Append-only: No update or delete operations are exposed.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return db.query(AuditLog).filter(AuditLog.ticket_id == ticket_id).order_by(AuditLog.timestamp.asc()).all()
