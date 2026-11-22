from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List

from ..database import get_db
from ..models import Ticket, Message, AuditLog
from ..schemas import (
    CustomerTicketResponse, CustomerMessageResponse, TicketCreate,
    CustomerReplyRequest
)
from ..sla_engine import (
    compute_sla_deadlines, calculate_working_seconds_between, REOPEN_WINDOW_DAYS
)

router = APIRouter(prefix="/customer/tickets", tags=["Customer Portal"])

@router.post("", response_model=CustomerTicketResponse)
def create_customer_ticket(payload: TicketCreate, db: Session = Depends(get_db)):
    """
    Customer submits a new support ticket.
    Computes business-hour SLA deadlines and initializes immutable audit log.
    """
    now = datetime.utcnow()
    # Generate sequential incident number
    last_ticket = db.query(Ticket).order_by(Ticket.id.desc()).first()
    next_num = (last_ticket.id + 325) if last_ticket else 326
    ticket_number = f"INC-{next_num:04d}"

    deadlines = compute_sla_deadlines(now, payload.severity)

    ticket = Ticket(
        ticket_number=ticket_number,
        title=payload.title,
        description=payload.description,
        customer_name=payload.customer_name,
        customer_email=payload.customer_email,
        customer_company=payload.customer_company or "Individual",
        severity=payload.severity.upper(),
        status="OPEN",
        created_at=now,
        first_reply_deadline=deadlines["reply_deadline"],
        resolution_deadline=deadlines["resolution_deadline"],
        total_paused_seconds=0.0,
        version=1
    )
    db.add(ticket)
    db.flush()

    # Initial message
    initial_msg = Message(
        ticket_id=ticket.id,
        sender_type="CUSTOMER",
        sender_name=payload.customer_name,
        sender_id=payload.customer_email,
        is_internal=False,  # Public initial message
        content=payload.description,
        created_at=now
    )
    db.add(initial_msg)

    # Immutable audit trail
    audit = AuditLog(
        ticket_id=ticket.id,
        actor_type="CUSTOMER",
        actor_name=payload.customer_name,
        action="TICKET_CREATED",
        details=f"Ticket created by {payload.customer_name} ({payload.customer_email}) with severity {payload.severity.upper()}.",
        timestamp=now
    )
    db.add(audit)
    db.commit()
    db.refresh(ticket)

    return get_customer_ticket_view(ticket)


@router.get("/{ticket_number}", response_model=CustomerTicketResponse)
def get_customer_ticket(ticket_number: str, db: Session = Depends(get_db)):
    """
    SECURITY CRITICAL (Incident 4.2):
    Customer view strictly filters out any message where is_internal == True.
    Private team notes are NEVER returned in this response.
    """
    ticket = db.query(Ticket).filter(Ticket.ticket_number == ticket_number.upper()).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return get_customer_ticket_view(ticket)


def get_customer_ticket_view(ticket: Ticket) -> CustomerTicketResponse:
    now = datetime.utcnow()
    # Check reopen eligibility: must be RESOLVED and resolved_at <= 7 days ago
    can_reopen = False
    if ticket.status == "RESOLVED" and ticket.resolved_at:
        days_since_resolved = (now - ticket.resolved_at).total_seconds() / 86400
        can_reopen = days_since_resolved <= REOPEN_WINDOW_DAYS

    # Filter out any internal notes! ONLY public messages are included
    public_messages = [
        CustomerMessageResponse.model_validate(m)
        for m in ticket.messages
        if not m.is_internal
    ]

    return CustomerTicketResponse(
        ticket_number=ticket.ticket_number,
        title=ticket.title,
        description=ticket.description,
        customer_name=ticket.customer_name,
        customer_email=ticket.customer_email,
        customer_company=ticket.customer_company,
        severity=ticket.severity,
        status=ticket.status,
        created_at=ticket.created_at,
        resolved_at=ticket.resolved_at,
        closed_at=ticket.closed_at,
        can_reopen=can_reopen,
        messages=public_messages
    )


@router.post("/{ticket_number}/reply", response_model=CustomerTicketResponse)
def customer_reply(ticket_number: str, payload: CustomerReplyRequest, db: Session = Depends(get_db)):
    """
    When customer replies:
    - If status was WAITING_ON_CUSTOMER, the SLA clock is UNPAUSED (elapsed pause added to total_paused_seconds).
    - Status flips back to IN_PROGRESS so agents see active customer response.
    """
    ticket = db.query(Ticket).filter(Ticket.ticket_number == ticket_number.upper()).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.status == "CLOSED":
        raise HTTPException(
            status_code=400,
            detail="This ticket is closed. Please submit a new ticket instead."
        )

    now = datetime.utcnow()

    # Unpause SLA timer if waiting on customer
    was_waiting = (ticket.status == "WAITING_ON_CUSTOMER")
    if was_waiting and ticket.last_paused_at:
        paused_working_secs = calculate_working_seconds_between(ticket.last_paused_at, now)
        ticket.total_paused_seconds += paused_working_secs
        ticket.last_paused_at = None
        ticket.status = "IN_PROGRESS"

    # Save customer message (Always public!)
    msg = Message(
        ticket_id=ticket.id,
        sender_type="CUSTOMER",
        sender_name=payload.customer_name,
        sender_id=payload.customer_email,
        is_internal=False,
        content=payload.content,
        created_at=now
    )
    db.add(msg)

    # Log immutable audit trail
    details = f"Customer {payload.customer_name} replied."
    if was_waiting:
        details += " SLA timer resumed. Status changed to IN_PROGRESS."

    audit = AuditLog(
        ticket_id=ticket.id,
        actor_type="CUSTOMER",
        actor_name=payload.customer_name,
        action="CUSTOMER_REPLY",
        details=details,
        timestamp=now
    )
    db.add(audit)

    ticket.version += 1
    db.commit()
    db.refresh(ticket)

    return get_customer_ticket_view(ticket)


@router.post("/{ticket_number}/reopen", response_model=CustomerTicketResponse)
def customer_reopen(ticket_number: str, db: Session = Depends(get_db)):
    """
    Rule from Meera:
    'If a customer is unhappy after we mark a ticket as done, they should be able to open it again.
     But only for about one week. After that it is a new ticket, not the old one.'
    """
    ticket = db.query(Ticket).filter(Ticket.ticket_number == ticket_number.upper()).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.status != "RESOLVED":
        raise HTTPException(
            status_code=400,
            detail=f"Ticket cannot be reopened because current status is {ticket.status} (only RESOLVED tickets can be reopened)."
        )

    now = datetime.utcnow()
    if ticket.resolved_at:
        days_since_resolved = (now - ticket.resolved_at).total_seconds() / 86400
        if days_since_resolved > REOPEN_WINDOW_DAYS:
            raise HTTPException(
                status_code=400,
                detail=f"Reopen window expired: This ticket was resolved {days_since_resolved:.1f} days ago (allowed window is {REOPEN_WINDOW_DAYS} days). Please open a new ticket."
            )

    ticket.status = "IN_PROGRESS"
    ticket.resolved_at = None
    ticket.version += 1

    audit = AuditLog(
        ticket_id=ticket.id,
        actor_type="CUSTOMER",
        actor_name=ticket.customer_name,
        action="TICKET_REOPENED",
        details=f"Customer {ticket.customer_name} was unhappy and reopened the ticket within the 7-day window. Status changed back to IN_PROGRESS.",
        timestamp=now
    )
    db.add(audit)
    db.commit()
    db.refresh(ticket)

    return get_customer_ticket_view(ticket)
