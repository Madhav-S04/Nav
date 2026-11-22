from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime
from typing import List, Optional

from ..database import get_db
from ..models import Ticket, Message, AuditLog, Agent
from ..schemas import (
    AgentTicketListItem, AgentTicketDetailResponse, MessageResponse,
    ClaimTicketRequest, UpdateStatusRequest, UpdateSeverityRequest, MessageCreate
)
from ..sla_engine import (
    evaluate_ticket_sla, compute_sla_deadlines, calculate_working_seconds_between,
    AUTO_CLOSE_WORKING_SECONDS
)

router = APIRouter(prefix="/agent/tickets", tags=["Agent Tickets"])

def attach_sla_to_ticket(ticket: Ticket, db: Session) -> dict:
    sla_info = evaluate_ticket_sla(
        created_at=ticket.created_at,
        severity=ticket.severity,
        status=ticket.status,
        first_reply_deadline=ticket.first_reply_deadline,
        resolution_deadline=ticket.resolution_deadline,
        first_replied_at=ticket.first_replied_at,
        resolved_at=ticket.resolved_at,
        total_paused_seconds=ticket.total_paused_seconds,
        last_paused_at=ticket.last_paused_at,
        current_time=datetime.utcnow()
    )
    return sla_info


@router.get("", response_model=List[AgentTicketListItem])
def list_tickets(
    assigned_to: Optional[int] = Query(None, description="Filter by assigned agent id"),
    status: Optional[str] = Query(None, description="Filter by status (OPEN, IN_PROGRESS, WAITING_ON_CUSTOMER, RESOLVED, CLOSED)"),
    severity: Optional[str] = Query(None, description="Filter by severity (URGENT, MEDIUM, SMALL)"),
    view: Optional[str] = Query(None, description="Quick views: 'mine', 'late', 'waiting', 'unassigned'"),
    search: Optional[str] = Query(None, description="Search term for title, description, ticket number, customer"),
    current_agent_id: Optional[int] = Query(None, description="Current logged in agent id for 'mine' view"),
    db: Session = Depends(get_db)
):
    query = db.query(Ticket)

    if assigned_to is not None:
        query = query.filter(Ticket.assigned_agent_id == assigned_to)
    
    if status:
        query = query.filter(Ticket.status == status.upper())

    if severity:
        query = query.filter(Ticket.severity == severity.upper())

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Ticket.ticket_number.ilike(search_term),
                Ticket.title.ilike(search_term),
                Ticket.customer_name.ilike(search_term),
                Ticket.customer_email.ilike(search_term),
                Ticket.customer_company.ilike(search_term)
            )
        )

    if view == "unassigned":
        query = query.filter(Ticket.assigned_agent_id == None, Ticket.status != "CLOSED")
    elif view == "waiting":
        query = query.filter(Ticket.status == "WAITING_ON_CUSTOMER")
    elif view == "mine" and current_agent_id is not None:
        query = query.filter(Ticket.assigned_agent_id == current_agent_id)

    tickets = query.order_by(Ticket.created_at.desc()).all()

    results = []
    for t in tickets:
        sla_info = attach_sla_to_ticket(t, db)
        
        # If filtering specifically for 'late' view:
        if view == "late":
            if not (sla_info["reply_late"] or sla_info["resolve_late"]):
                continue

        item = AgentTicketListItem.model_validate(t)
        item.sla_info = sla_info
        results.append(item)

    return results


@router.get("/metrics")
def get_dashboard_metrics(db: Session = Depends(get_db)):
    """Computes real-time KPI metrics for support team."""
    all_tickets = db.query(Ticket).all()
    total = len(all_tickets)
    open_count = 0
    waiting_count = 0
    late_count = 0
    urgent_count = 0
    resolved_count = 0

    for t in all_tickets:
        if t.status in ("OPEN", "IN_PROGRESS"):
            open_count += 1
        elif t.status == "WAITING_ON_CUSTOMER":
            waiting_count += 1
        elif t.status in ("RESOLVED", "CLOSED"):
            resolved_count += 1

        if t.severity == "URGENT" and t.status not in ("RESOLVED", "CLOSED"):
            urgent_count += 1

        sla = attach_sla_to_ticket(t, db)
        if sla["reply_late"] or sla["resolve_late"]:
            late_count += 1

    return {
        "total_tickets": total,
        "active_tickets": open_count,
        "waiting_on_customer": waiting_count,
        "late_tickets": late_count,
        "urgent_tickets": urgent_count,
        "resolved_tickets": resolved_count,
    }


@router.get("/{ticket_id}", response_model=AgentTicketDetailResponse)
def get_ticket_detail(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    sla_info = attach_sla_to_ticket(ticket, db)
    detail = AgentTicketDetailResponse.model_validate(ticket)
    detail.sla_info = sla_info
    return detail


@router.post("/{ticket_id}/claim")
def claim_ticket(ticket_id: int, payload: ClaimTicketRequest, db: Session = Depends(get_db)):
    """
    Incident 4.1 Solution: Atomic Ticket Claiming & Collision Prevention.
    Prevents two agents claiming the same ticket concurrently.
    Uses version checking and database check.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    agent = db.query(Agent).filter(Agent.id == payload.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Check if already assigned to someone else
    if ticket.assigned_agent_id is not None and ticket.assigned_agent_id != payload.agent_id:
        assigned_name = ticket.assigned_agent.name if ticket.assigned_agent else f"Agent #{ticket.assigned_agent_id}"
        raise HTTPException(
            status_code=409,
            detail=f"Conflict: Ticket {ticket.ticket_number} is already assigned to {assigned_name}."
        )

    # Check optimistic concurrency version
    if ticket.version != payload.current_version:
        raise HTTPException(
            status_code=409,
            detail=f"Conflict: Ticket {ticket.ticket_number} was just updated by another agent. Please refresh."
        )

    old_assigned = ticket.assigned_agent.name if ticket.assigned_agent else "Unassigned"
    ticket.assigned_agent_id = agent.id
    if ticket.status == "OPEN":
        ticket.status = "IN_PROGRESS"
    ticket.version += 1

    # Record immutable audit log
    audit = AuditLog(
        ticket_id=ticket.id,
        actor_type="AGENT",
        actor_name=agent.name,
        action="TICKET_CLAIMED",
        details=f"Ticket claimed by {agent.name} (previously {old_assigned}). Status updated to {ticket.status}."
    )
    db.add(audit)
    db.commit()
    db.refresh(ticket)

    return {"message": "Ticket successfully claimed", "ticket": AgentTicketListItem.model_validate(ticket)}


@router.post("/{ticket_id}/messages")
def post_ticket_message(ticket_id: int, payload: MessageCreate, agent_id: int = Query(...), db: Session = Depends(get_db)):
    """
    Handles both:
    1. Public customer replies (is_internal=False): Emailed/visible to customer, counts towards First Reply SLA.
    2. Private team notes (is_internal=True): NEVER visible to customer (Incident 4.2).
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    now = datetime.utcnow()

    # Create message
    msg = Message(
        ticket_id=ticket.id,
        sender_type="AGENT",
        sender_name=agent.name,
        sender_id=str(agent.id),
        is_internal=payload.is_internal,
        content=payload.content,
        created_at=now
    )
    db.add(msg)

    # If it is a public customer reply, check if this is the first reply
    action_type = "INTERNAL_NOTE" if payload.is_internal else "PUBLIC_REPLY"
    audit_detail = f"Private team note added by {agent.name}." if payload.is_internal else f"Public reply sent to customer by {agent.name}."

    if not payload.is_internal:
        if ticket.first_replied_at is None:
            ticket.first_replied_at = now
            audit_detail += " (Marked as First Reply)."

    # Log immutable audit trail (Incident 4.3)
    audit = AuditLog(
        ticket_id=ticket.id,
        actor_type="AGENT",
        actor_name=agent.name,
        action=action_type,
        details=audit_detail,
        timestamp=now
    )
    db.add(audit)

    ticket.version += 1
    db.commit()
    db.refresh(msg)

    return {"message": "Message sent", "data": MessageResponse.model_validate(msg)}


@router.post("/{ticket_id}/status")
def update_ticket_status(ticket_id: int, payload: UpdateStatusRequest, db: Session = Depends(get_db)):
    """
    Updates ticket status with business SLA clock management:
    - Entering WAITING_ON_CUSTOMER: PAUSES the SLA timer (records last_paused_at).
    - Leaving WAITING_ON_CUSTOMER: RESUMES the SLA timer (adds elapsed working seconds to total_paused_seconds).
    - Entering RESOLVED: Sets resolved_at timestamp.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    agent_name = "System"
    if payload.agent_id:
        agent = db.query(Agent).filter(Agent.id == payload.agent_id).first()
        if agent:
            agent_name = agent.name

    new_status = payload.status.upper()
    old_status = ticket.status
    if new_status == old_status:
        return {"message": "Status unchanged", "status": new_status}

    now = datetime.utcnow()

    # Clock Pausing logic:
    if old_status == "WAITING_ON_CUSTOMER" and new_status != "WAITING_ON_CUSTOMER":
        # Resume timer: compute pause duration and accumulate
        if ticket.last_paused_at:
            paused_working_secs = calculate_working_seconds_between(ticket.last_paused_at, now)
            ticket.total_paused_seconds += paused_working_secs
            ticket.last_paused_at = None

    if new_status == "WAITING_ON_CUSTOMER":
        # Pause timer
        ticket.last_paused_at = now

    if new_status == "RESOLVED":
        ticket.resolved_at = now
    elif old_status == "RESOLVED" and new_status != "RESOLVED":
        ticket.resolved_at = None

    if new_status == "CLOSED":
        ticket.closed_at = now

    ticket.status = new_status
    ticket.version += 1

    # Log immutable audit trail
    audit_desc = f"Status changed from {old_status} to {new_status} by {agent_name}."
    if payload.note:
        audit_desc += f" Note: {payload.note}"

    audit = AuditLog(
        ticket_id=ticket.id,
        actor_type="AGENT" if payload.agent_id else "SYSTEM",
        actor_name=agent_name,
        action="STATUS_CHANGED",
        details=audit_desc,
        timestamp=now
    )
    db.add(audit)
    db.commit()
    db.refresh(ticket)

    return {"message": f"Status updated to {new_status}", "status": new_status}


@router.post("/{ticket_id}/severity")
def update_ticket_severity(ticket_id: int, payload: UpdateSeverityRequest, db: Session = Depends(get_db)):
    """
    Section 3 Edge Case Answer:
    What happens to the timer if we change a ticket to urgent in the middle?
    - Recalculates first_reply_deadline and resolution_deadline using the new severity target from creation time.
    - If elapsed business time already exceeds the urgent SLA, the ticket is flagged as immediately breached.
    - An explicit immutable audit log is recorded documenting the SLA adjustment.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    agent = db.query(Agent).filter(Agent.id == payload.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    new_sev = payload.severity.upper()
    old_sev = ticket.severity
    if new_sev == old_sev:
        return {"message": "Severity unchanged"}

    # Recalculate SLA targets
    deadlines = compute_sla_deadlines(ticket.created_at, new_sev)
    old_reply_dl = ticket.first_reply_deadline
    old_resolve_dl = ticket.resolution_deadline

    ticket.severity = new_sev
    ticket.first_reply_deadline = deadlines["reply_deadline"]
    ticket.resolution_deadline = deadlines["resolution_deadline"]
    ticket.version += 1

    details = (
        f"Severity changed from {old_sev} to {new_sev} by {agent.name}. "
        f"SLA Deadlines recalculated from ticket creation time: "
        f"Reply deadline changed from {old_reply_dl.strftime('%Y-%m-%d %H:%M')} to {ticket.first_reply_deadline.strftime('%Y-%m-%d %H:%M')}. "
        f"Resolution deadline changed from {old_resolve_dl.strftime('%Y-%m-%d %H:%M')} to {ticket.resolution_deadline.strftime('%Y-%m-%d %H:%M')}."
    )
    if payload.reason:
        details += f" Reason: {payload.reason}"

    audit = AuditLog(
        ticket_id=ticket.id,
        actor_type="AGENT",
        actor_name=agent.name,
        action="SEVERITY_CHANGED",
        details=details,
        timestamp=datetime.utcnow()
    )
    db.add(audit)
    db.commit()
    db.refresh(ticket)

    return {
        "message": f"Severity updated to {new_sev}",
        "new_reply_deadline": ticket.first_reply_deadline.isoformat(),
        "new_resolution_deadline": ticket.resolution_deadline.isoformat(),
    }


@router.post("/auto-close-stale")
def trigger_auto_close_stale(db: Session = Depends(get_db)):
    """
    Auto-close rule from Support Lead Meera:
    'If a customer does not reply for about one working week, we close the ticket.'
    Evaluates all tickets in WAITING_ON_CUSTOMER. If paused working seconds >= 45 working hours, auto-closes.
    """
    now = datetime.utcnow()
    candidates = db.query(Ticket).filter(Ticket.status == "WAITING_ON_CUSTOMER").all()
    closed_count = 0

    for t in candidates:
        if t.last_paused_at:
            working_seconds_waiting = calculate_working_seconds_between(t.last_paused_at, now)
            if (t.total_paused_seconds + working_seconds_waiting) >= AUTO_CLOSE_WORKING_SECONDS:
                t.status = "CLOSED"
                t.closed_at = now
                t.total_paused_seconds += working_seconds_waiting
                t.last_paused_at = None
                t.version += 1

                audit = AuditLog(
                    ticket_id=t.id,
                    actor_type="SYSTEM",
                    actor_name="Frontdesk Automation",
                    action="AUTO_CLOSED",
                    details="Ticket automatically closed because customer did not reply within 1 working week (45 working hours).",
                    timestamp=now
                )
                db.add(audit)
                closed_count += 1

    db.commit()
    return {"message": f"Auto-closed {closed_count} stale tickets", "count": closed_count}
