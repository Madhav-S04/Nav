from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .models import Agent, Ticket, Message, AuditLog
from .sla_engine import compute_sla_deadlines, add_working_seconds

AGENTS_SEED = [
    {"name": "Meera Raman", "email": "meera@arvo.com", "role": "Support Lead", "avatar_color": "#8b5cf6"},
    {"name": "Alex Chen", "email": "alex@arvo.com", "role": "Senior Agent", "avatar_color": "#3b82f6"},
    {"name": "Jordan Lee", "email": "jordan@arvo.com", "role": "Agent", "avatar_color": "#10b981"},
    {"name": "Sam Rivera", "email": "sam@arvo.com", "role": "Agent", "avatar_color": "#f59e0b"},
    {"name": "Priya Nair", "email": "priya@arvo.com", "role": "Agent", "avatar_color": "#ec4899"},
    {"name": "Rahul Sharma", "email": "rahul@arvo.com", "role": "Agent", "avatar_color": "#06b6d4"},
    {"name": "Elena Rostova", "email": "elena@arvo.com", "role": "Agent", "avatar_color": "#84cc16"},
    {"name": "David Kim", "email": "david@arvo.com", "role": "Agent", "avatar_color": "#6366f1"},
    {"name": "Fatima Zahra", "email": "fatima@arvo.com", "role": "Agent", "avatar_color": "#f97316"},
]

def seed_database(db: Session):
    # Check if already seeded
    if db.query(Agent).first() is not None:
        return

    print("Seeding Arvo Systems 9 support agents and demo scenarios...")

    # 1. Seed Agents
    agent_instances = []
    for a in AGENTS_SEED:
        agent = Agent(**a)
        db.add(agent)
        agent_instances.append(agent)
    db.commit()

    # Re-fetch agents with IDs
    agents = db.query(Agent).all()
    meera = agents[0]
    alex = agents[1]
    priya = agents[4]
    rahul = agents[5]

    now = datetime.utcnow()

    # 2. INC-0291 (Incident 4.1 from PDF: Collision / Take Ticket)
    inc_0291_created = now - timedelta(hours=3)
    dls_0291 = compute_sla_deadlines(inc_0291_created, "MEDIUM")
    t1 = Ticket(
        ticket_number="INC-0291",
        title="Database synchronization failure during nightly batch",
        description="Our nightly ETL synchronization job threw error code DB_SYNC_502. We need urgent guidance on retry parameters.",
        customer_name="Marcus Vance",
        customer_email="m.vance@apexlogistics.com",
        customer_company="Apex Logistics",
        severity="MEDIUM",
        status="OPEN",
        assigned_agent_id=None,  # Unassigned - ideal for testing collision prevention!
        created_at=inc_0291_created,
        first_reply_deadline=dls_0291["reply_deadline"],
        resolution_deadline=dls_0291["resolution_deadline"],
        total_paused_seconds=0.0,
        version=1
    )
    db.add(t1)
    db.flush()

    m1 = Message(
        ticket_id=t1.id,
        sender_type="CUSTOMER",
        sender_name="Marcus Vance",
        sender_id="m.vance@apexlogistics.com",
        is_internal=False,
        content="Our nightly ETL synchronization job threw error code DB_SYNC_502. We need urgent guidance on retry parameters.",
        created_at=inc_0291_created
    )
    a1 = AuditLog(
        ticket_id=t1.id,
        actor_type="CUSTOMER",
        actor_name="Marcus Vance",
        action="TICKET_CREATED",
        details="Ticket created via API integration with severity MEDIUM.",
        timestamp=inc_0291_created
    )
    db.add_all([m1, a1])

    # 3. INC-0304 (Incident 4.2 from PDF: Private Team Notes vs Customer Leakage)
    inc_0304_created = now - timedelta(days=2)
    dls_0304 = compute_sla_deadlines(inc_0304_created, "MEDIUM")
    t2 = Ticket(
        ticket_number="INC-0304",
        title="Custom export template failing to render invoice currency symbols",
        description="When exporting invoices to PDF, the Euro and GBP symbols render as question marks. Can this be fixed immediately?",
        customer_name="Clara Oswald",
        customer_email="clara@oswaldtrading.co.uk",
        customer_company="Oswald Trading Ltd",
        severity="MEDIUM",
        status="IN_PROGRESS",
        assigned_agent_id=alex.id,
        created_at=inc_0304_created,
        first_replied_at=inc_0304_created + timedelta(minutes=45),
        first_reply_deadline=dls_0304["reply_deadline"],
        resolution_deadline=dls_0304["resolution_deadline"],
        total_paused_seconds=0.0,
        version=3
    )
    db.add(t2)
    db.flush()

    # Messages for INC-0304: Initial, internal note, public reply
    m2_1 = Message(
        ticket_id=t2.id,
        sender_type="CUSTOMER",
        sender_name="Clara Oswald",
        sender_id="clara@oswaldtrading.co.uk",
        is_internal=False,
        content="When exporting invoices to PDF, the Euro and GBP symbols render as question marks. Can this be fixed immediately?",
        created_at=inc_0304_created
    )
    m2_2 = Message(
        ticket_id=t2.id,
        sender_type="AGENT",
        sender_name=alex.name,
        sender_id=str(alex.id),
        is_internal=True,  # ⚠️ PRIVATE TEAM NOTE (Incident 4.2)
        content="🔒 TEAM NOTE: Clara has escalation rights to our VP. We had a font encoding issue on the PDF worker cluster last month. Check the UTF-8 font embedding in the PDF generator before replying. Keep customer calm.",
        created_at=inc_0304_created + timedelta(minutes=30)
    )
    m2_3 = Message(
        ticket_id=t2.id,
        sender_type="AGENT",
        sender_name=alex.name,
        sender_id=str(alex.id),
        is_internal=False,  # PUBLIC CUSTOMER REPLY
        content="Hello Clara, thank you for reaching out. We have reproduced the currency font glyph issue on our PDF generation service and our engineering team is applying a patch to the character encoding map right now.",
        created_at=inc_0304_created + timedelta(minutes=45)
    )
    a2_1 = AuditLog(
        ticket_id=t2.id,
        actor_type="CUSTOMER",
        actor_name="Clara Oswald",
        action="TICKET_CREATED",
        details="Ticket created with severity MEDIUM.",
        timestamp=inc_0304_created
    )
    a2_2 = AuditLog(
        ticket_id=t2.id,
        actor_type="AGENT",
        actor_name=alex.name,
        action="INTERNAL_NOTE",
        details=f"Private team note added by {alex.name} regarding font encoding patch and customer sensitivity.",
        timestamp=inc_0304_created + timedelta(minutes=30)
    )
    a2_3 = AuditLog(
        ticket_id=t2.id,
        actor_type="AGENT",
        actor_name=alex.name,
        action="PUBLIC_REPLY",
        details=f"Public reply sent to customer by {alex.name} (First reply fulfilled in 45m).",
        timestamp=inc_0304_created + timedelta(minutes=45)
    )
    db.add_all([m2_1, m2_2, m2_3, a2_1, a2_2, a2_3])

    # 4. INC-0318 (Incident 4.3 from PDF: Disputed Reply Time with Immutable Audit Proof)
    inc_0318_created = now - timedelta(days=1, hours=4)
    dls_0318 = compute_sla_deadlines(inc_0318_created, "URGENT")
    t3 = Ticket(
        ticket_number="INC-0318",
        title="Production checkout gateway returning 500 error",
        description="Our checkout process is completely halted! Customers cannot complete purchases. Immediate assistance required!",
        customer_name="Gordon Ramsey",
        customer_email="gordon@hellskitchen.com",
        customer_company="Hell's Kitchen Retail",
        severity="URGENT",
        status="RESOLVED",
        assigned_agent_id=priya.id,
        created_at=inc_0318_created,
        first_replied_at=inc_0318_created + timedelta(minutes=40),  # Exactly 40 mins!
        resolved_at=inc_0318_created + timedelta(hours=3),
        first_reply_deadline=dls_0318["reply_deadline"],
        resolution_deadline=dls_0318["resolution_deadline"],
        total_paused_seconds=0.0,
        version=4
    )
    db.add(t3)
    db.flush()

    m3_1 = Message(
        ticket_id=t3.id,
        sender_type="CUSTOMER",
        sender_name="Gordon Ramsey",
        sender_id="gordon@hellskitchen.com",
        is_internal=False,
        content="Our checkout process is completely halted! Customers cannot complete purchases. Immediate assistance required!",
        created_at=inc_0318_created
    )
    m3_2 = Message(
        ticket_id=t3.id,
        sender_type="AGENT",
        sender_name=priya.name,
        sender_id=str(priya.id),
        is_internal=False,
        content="Hi Gordon, we detected the gateway timeout on Payment Gateway Route 3 and rerouted your traffic through Backup Gateway 1. Transactions are clearing again.",
        created_at=inc_0318_created + timedelta(minutes=40)
    )
    a3_1 = AuditLog(
        ticket_id=t3.id,
        actor_type="CUSTOMER",
        actor_name="Gordon Ramsey",
        action="TICKET_CREATED",
        details="Critical incident reported by customer. Severity: URGENT (2hr reply SLA).",
        timestamp=inc_0318_created
    )
    a3_2 = AuditLog(
        ticket_id=t3.id,
        actor_type="AGENT",
        actor_name=priya.name,
        action="PUBLIC_REPLY",
        details=f"Public reply dispatched by {priya.name} at { (inc_0318_created + timedelta(minutes=40)).isoformat() }. Exactly 40 minutes elapsed from creation.",
        timestamp=inc_0318_created + timedelta(minutes=40)
    )
    a3_3 = AuditLog(
        ticket_id=t3.id,
        actor_type="AGENT",
        actor_name=priya.name,
        action="STATUS_CHANGED",
        details="Status changed from IN_PROGRESS to RESOLVED by Priya Nair. Gateway issue verified resolved.",
        timestamp=inc_0318_created + timedelta(hours=3)
    )
    db.add_all([m3_1, m3_2, a3_1, a3_2, a3_3])

    # 5. INC-0319: The Friday 6:00 PM Ticket (Demonstrates Business Hours Rule)
    # Arrived at Friday 18:00 (30 mins before closing at 18:30).
    # Saturday & Sunday are non-working.
    friday_1800 = datetime(2026, 11, 20, 18, 0, 0)  # Recent Friday
    dls_0319 = compute_sla_deadlines(friday_1800, "MEDIUM")
    t4 = Ticket(
        ticket_number="INC-0319",
        title="Weekly summary report formatting error",
        description="Our Friday end-of-week report had column misalignment in section 4. Please take a look when you get a chance.",
        customer_name="Arthur Pendelton",
        customer_email="arthur@camelotcorp.com",
        customer_company="Camelot Corp",
        severity="MEDIUM",
        status="OPEN",
        assigned_agent_id=rahul.id,
        created_at=friday_1800,
        first_reply_deadline=dls_0319["reply_deadline"],
        resolution_deadline=dls_0319["resolution_deadline"],
        total_paused_seconds=0.0,
        version=1
    )
    db.add(t4)
    db.flush()

    m4_1 = Message(
        ticket_id=t4.id,
        sender_type="CUSTOMER",
        sender_name="Arthur Pendelton",
        sender_id="arthur@camelotcorp.com",
        is_internal=False,
        content="Our Friday end-of-week report had column misalignment in section 4. Please take a look when you get a chance.",
        created_at=friday_1800
    )
    a4_1 = AuditLog(
        ticket_id=t4.id,
        actor_type="CUSTOMER",
        actor_name="Arthur Pendelton",
        action="TICKET_CREATED",
        details=f"Ticket arrived at Friday 18:00:00. Working time elapsed before weekend: 30 minutes. Non-working over weekend. Deadline properly projected to next week.",
        timestamp=friday_1800
    )
    db.add_all([m4_1, a4_1])

    # 6. INC-0320: Urgent Ticket ("Cannot work at all" - 2 hr reply SLA)
    inc_0320_created = now - timedelta(hours=1, minutes=10)
    dls_0320 = compute_sla_deadlines(inc_0320_created, "URGENT")
    t5 = Ticket(
        ticket_number="INC-0320",
        title="Authentication service returning 401 on all SSO logins",
        description="Our entire workforce of 400 people is locked out of the portal this morning. We cannot work at all!",
        customer_name="Siddharth Rao",
        customer_email="s.rao@novushealth.org",
        customer_company="Novus Health",
        severity="URGENT",
        status="OPEN",
        assigned_agent_id=meera.id,
        created_at=inc_0320_created,
        first_reply_deadline=dls_0320["reply_deadline"],
        resolution_deadline=dls_0320["resolution_deadline"],
        total_paused_seconds=0.0,
        version=1
    )
    db.add(t5)
    db.flush()

    m5_1 = Message(
        ticket_id=t5.id,
        sender_type="CUSTOMER",
        sender_name="Siddharth Rao",
        sender_id="s.rao@novushealth.org",
        is_internal=False,
        content="Our entire workforce of 400 people is locked out of the portal this morning. We cannot work at all!",
        created_at=inc_0320_created
    )
    a5_1 = AuditLog(
        ticket_id=t5.id,
        actor_type="CUSTOMER",
        actor_name="Siddharth Rao",
        action="TICKET_CREATED",
        details="URGENT: Entire company locked out. 2-hour first reply target.",
        timestamp=inc_0320_created
    )
    db.add_all([m5_1, a5_1])

    # 7. INC-0321: Ticket in WAITING_ON_CUSTOMER (Paused SLA clock)
    inc_0321_created = now - timedelta(days=1, hours=2)
    dls_0321 = compute_sla_deadlines(inc_0321_created, "MEDIUM")
    paused_at_0321 = now - timedelta(hours=4)
    t6 = Ticket(
        ticket_number="INC-0321",
        title="Webhook callback endpoint intermittently dropping payloads",
        description="We suspect payload drops on payload sizes exceeding 2MB on our endpoint.",
        customer_name="Tanya Miller",
        customer_email="tmiller@cloudscale.io",
        customer_company="CloudScale Systems",
        severity="MEDIUM",
        status="WAITING_ON_CUSTOMER",
        assigned_agent_id=alex.id,
        created_at=inc_0321_created,
        first_replied_at=inc_0321_created + timedelta(hours=1),
        first_reply_deadline=dls_0321["reply_deadline"],
        resolution_deadline=dls_0321["resolution_deadline"],
        total_paused_seconds=3600.0,  # 1 hour previously paused
        last_paused_at=paused_at_0321, # currently paused
        version=3
    )
    db.add(t6)
    db.flush()

    m6_1 = Message(
        ticket_id=t6.id,
        sender_type="CUSTOMER",
        sender_name="Tanya Miller",
        sender_id="tmiller@cloudscale.io",
        is_internal=False,
        content="We suspect payload drops on payload sizes exceeding 2MB on our endpoint.",
        created_at=inc_0321_created
    )
    m6_2 = Message(
        ticket_id=t6.id,
        sender_type="AGENT",
        sender_name=alex.name,
        sender_id=str(alex.id),
        is_internal=False,
        content="Hi Tanya, could you provide the request headers and transaction ID for the failed payload from your server logs?",
        created_at=paused_at_0321
    )
    a6_1 = AuditLog(
        ticket_id=t6.id,
        actor_type="AGENT",
        actor_name=alex.name,
        action="STATUS_CHANGED",
        details="Status changed to WAITING_ON_CUSTOMER. SLA resolution clock PAUSED pending Tanya's reply.",
        timestamp=paused_at_0321
    )
    db.add_all([m6_1, m6_2, a6_1])

    # 8. INC-0322: Resolved Ticket within 7-day Reopen Window
    inc_0322_created = now - timedelta(days=3)
    dls_0322 = compute_sla_deadlines(inc_0322_created, "SMALL")
    t7 = Ticket(
        ticket_number="INC-0322",
        title="How to update billing address for quarterly invoice?",
        description="We recently moved offices and need to change the corporate address appearing on receipts.",
        customer_name="Fiona Gallagher",
        customer_email="fiona@southside.org",
        customer_company="Southside Co",
        severity="SMALL",
        status="RESOLVED",
        assigned_agent_id=priya.id,
        created_at=inc_0322_created,
        first_replied_at=inc_0322_created + timedelta(hours=2),
        resolved_at=now - timedelta(days=2),  # Resolved 2 days ago (<= 7 days: can reopen!)
        first_reply_deadline=dls_0322["reply_deadline"],
        resolution_deadline=dls_0322["resolution_deadline"],
        total_paused_seconds=0.0,
        version=3
    )
    db.add(t7)
    db.flush()

    m7_1 = Message(
        ticket_id=t7.id,
        sender_type="CUSTOMER",
        sender_name="Fiona Gallagher",
        sender_id="fiona@southside.org",
        is_internal=False,
        content="We recently moved offices and need to change the corporate address appearing on receipts.",
        created_at=inc_0322_created
    )
    m7_2 = Message(
        ticket_id=t7.id,
        sender_type="AGENT",
        sender_name=priya.name,
        sender_id=str(priya.id),
        is_internal=False,
        content="Hi Fiona, you can update this directly in Settings > Organization > Invoicing Address. I have also manually updated your profile.",
        created_at=inc_0322_created + timedelta(hours=2)
    )
    a7_1 = AuditLog(
        ticket_id=t7.id,
        actor_type="AGENT",
        actor_name=priya.name,
        action="STATUS_CHANGED",
        details="Status changed to RESOLVED. Eligible for customer reopening for 7 calendar days.",
        timestamp=now - timedelta(days=2)
    )
    db.add_all([m7_1, m7_2, a7_1])

    db.commit()
    print("Database seeding completed successfully.")
