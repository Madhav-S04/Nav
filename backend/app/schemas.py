from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, ConfigDict, Field

# --- AGENT SCHEMAS ---
class AgentBase(BaseModel):
    name: str
    email: str
    role: str = "Agent"
    avatar_color: str = "#3b82f6"

class AgentResponse(AgentBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# --- MESSAGE SCHEMAS ---
class MessageBase(BaseModel):
    content: str

class MessageCreate(MessageBase):
    is_internal: bool = False
    sender_name: Optional[str] = None

class MessageResponse(BaseModel):
    id: int
    ticket_id: int
    sender_type: str
    sender_name: str
    sender_id: Optional[str] = None
    is_internal: bool
    content: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Customer-safe message response (Strictly NEVER leaks internal notes)
class CustomerMessageResponse(BaseModel):
    id: int
    sender_type: str
    sender_name: str
    content: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- AUDIT LOG SCHEMAS ---
class AuditLogResponse(BaseModel):
    id: int
    ticket_id: int
    actor_type: str
    actor_name: str
    action: str
    details: str
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)


# --- TICKET SCHEMAS ---
class TicketBase(BaseModel):
    title: str
    description: str
    customer_name: str
    customer_email: str
    customer_company: Optional[str] = "Individual"
    severity: str = "MEDIUM"  # "URGENT", "MEDIUM", "SMALL"

class TicketCreate(TicketBase):
    pass

class SlaEvaluationResponse(BaseModel):
    reply_status: str
    reply_late: bool
    reply_remaining_seconds: float
    effective_reply_deadline: str
    resolve_status: str
    resolve_late: bool
    resolve_remaining_seconds: float
    effective_resolve_deadline: str
    overall_sla_badge: str
    accumulated_paused_seconds: float
    can_auto_close: bool

class AgentTicketListItem(BaseModel):
    id: int
    ticket_number: str
    title: str
    customer_name: str
    customer_email: str
    customer_company: str
    severity: str
    status: str
    assigned_agent_id: Optional[int]
    assigned_agent: Optional[AgentResponse]
    created_at: datetime
    first_replied_at: Optional[datetime]
    resolved_at: Optional[datetime]
    closed_at: Optional[datetime]
    first_reply_deadline: datetime
    resolution_deadline: datetime
    total_paused_seconds: float
    last_paused_at: Optional[datetime]
    version: int
    sla_info: Optional[SlaEvaluationResponse] = None
    model_config = ConfigDict(from_attributes=True)

class AgentTicketDetailResponse(AgentTicketListItem):
    description: str
    messages: List[MessageResponse] = []
    audit_logs: List[AuditLogResponse] = []
    model_config = ConfigDict(from_attributes=True)


# Customer Facing Ticket Representation (Incident 4.2: zero internal note leakage)
class CustomerTicketResponse(BaseModel):
    ticket_number: str
    title: str
    description: str
    customer_name: str
    customer_email: str
    customer_company: str
    severity: str
    status: str
    created_at: datetime
    resolved_at: Optional[datetime]
    closed_at: Optional[datetime]
    can_reopen: bool
    messages: List[CustomerMessageResponse] = []
    model_config = ConfigDict(from_attributes=True)


# Actions
class ClaimTicketRequest(BaseModel):
    agent_id: int
    current_version: int

class UpdateStatusRequest(BaseModel):
    status: str
    agent_id: Optional[int] = None
    note: Optional[str] = None

class UpdateSeverityRequest(BaseModel):
    severity: str
    agent_id: int
    reason: Optional[str] = None

class CustomerReplyRequest(BaseModel):
    customer_name: str
    customer_email: str
    content: str
