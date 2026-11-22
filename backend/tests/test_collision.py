from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models import Ticket, Agent

client = TestClient(app)

def test_prevent_two_agents_taking_same_ticket():
    """
    Incident 4.1 Resolution:
    'Two agents opened the same ticket. Both clicked "take this ticket"...
     The spreadsheet allowed both agents to take the same ticket.'
    Verify that our backend prevents collision with HTTP 409 Conflict.
    """
    db = SessionLocal()
    agents = db.query(Agent).all()
    assert len(agents) >= 2, "Expected seeded agents"
    agent_a = agents[1] # Alex
    agent_b = agents[4] # Priya

    # Find unassigned ticket INC-0291
    ticket = db.query(Ticket).filter(Ticket.ticket_number == "INC-0291").first()
    ticket_id = ticket.id
    current_version = ticket.version
    db.close()

    # Agent A takes the ticket
    res_a = client.post(
        f"/api/agent/tickets/{ticket_id}/claim",
        json={"agent_id": agent_a.id, "current_version": current_version}
    )
    assert res_a.status_code == 200, f"Agent A claim failed: {res_a.text}"

    # Agent B attempts to take the ticket with the stale version / already assigned ticket
    res_b = client.post(
        f"/api/agent/tickets/{ticket_id}/claim",
        json={"agent_id": agent_b.id, "current_version": current_version}
    )

    # Agent B MUST receive HTTP 409 Conflict!
    assert res_b.status_code == 409, f"Expected 409 Conflict, got {res_b.status_code}"
    assert "already assigned" in res_b.json()["detail"].lower() or "conflict" in res_b.json()["detail"].lower()
