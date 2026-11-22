from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from .database import Base

class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    role = Column(String(50), default="Agent")  # "Lead", "Agent"
    avatar_color = Column(String(20), default="#3b82f6")

    tickets = relationship("Ticket", back_populates="assigned_agent")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_number = Column(String(20), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    customer_name = Column(String(100), nullable=False)
    customer_email = Column(String(120), nullable=False)
    customer_company = Column(String(100), default="Individual")

    # Severity: URGENT ("cannot work at all"), MEDIUM ("medium problems"), SMALL ("questions or small requests")
    severity = Column(String(20), nullable=False, default="MEDIUM", index=True)

    # Status: OPEN, IN_PROGRESS, WAITING_ON_CUSTOMER, RESOLVED, CLOSED
    status = Column(String(30), nullable=False, default="OPEN", index=True)

    assigned_agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    first_replied_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    # SLA Deadlines (business hours calculated)
    first_reply_deadline = Column(DateTime, nullable=False)
    resolution_deadline = Column(DateTime, nullable=False)

    # Pausing tracker (when WAITING_ON_CUSTOMER)
    total_paused_seconds = Column(Float, default=0.0, nullable=False)
    last_paused_at = Column(DateTime, nullable=True)

    # Concurrency control: Optimistic locking version
    version = Column(Integer, default=1, nullable=False)

    # Relationships
    assigned_agent = relationship("Agent", back_populates="tickets")
    messages = relationship("Message", back_populates="ticket", order_by="Message.created_at.asc()", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="ticket", order_by="AuditLog.timestamp.asc()", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False, index=True)
    sender_type = Column(String(20), nullable=False)  # "AGENT", "CUSTOMER", "SYSTEM"
    sender_name = Column(String(100), nullable=False)
    sender_id = Column(String(50), nullable=True)     # e.g. agent_id or customer email

    # SECURITY CRITICAL (Incident 4.2):
    # is_internal == True means it is a private team note.
    # It must NEVER be sent to customer via screen, API response, export, or list.
    is_internal = Column(Boolean, default=False, nullable=False, index=True)

    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    ticket = relationship("Ticket", back_populates="messages")


class AuditLog(Base):
    """
    Immutable audit record (Incident 4.3).
    Records exactly what happened, when it happened, and who did it.
    Append-only: No updates or deletes allowed.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False, index=True)
    actor_type = Column(String(20), nullable=False)   # "AGENT", "CUSTOMER", "SYSTEM"
    actor_name = Column(String(100), nullable=False)
    action = Column(String(50), nullable=False)       # "CREATED", "CLAIMED", "PUBLIC_REPLY", "INTERNAL_NOTE", etc.
    details = Column(Text, nullable=False)            # JSON / string describing event details
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    ticket = relationship("Ticket", back_populates="audit_logs")
