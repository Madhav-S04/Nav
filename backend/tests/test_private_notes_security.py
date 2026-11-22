from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_private_team_notes_never_leaked_to_customer():
    """
    Incident 4.2 Resolution:
    'An agent wrote a private note for the team... By mistake, the note was sent to that customer.
     Private team notes must never be shown to a customer. Not on a screen. Not in an API response.
     Not in an export. Not in a list.'
    """
    # 1. Fetch INC-0304 from the agent endpoint (should see both internal note and public reply)
    tickets_res = client.get("/api/agent/tickets?search=INC-0304")
    assert tickets_res.status_code == 200
    tickets = tickets_res.json()
    assert len(tickets) > 0
    ticket_id = tickets[0]["id"]

    agent_detail = client.get(f"/api/agent/tickets/{ticket_id}").json()
    internal_notes = [m for m in agent_detail["messages"] if m["is_internal"] is True]
    assert len(internal_notes) > 0, "Agent should be able to see internal team notes"
    internal_content = internal_notes[0]["content"]

    # 2. Fetch INC-0304 from the Customer endpoint
    customer_res = client.get("/api/customer/tickets/INC-0304")
    assert customer_res.status_code == 200
    customer_data = customer_res.json()

    # Verify that the customer response does NOT contain any internal note
    customer_messages = customer_data["messages"]
    for msg in customer_messages:
        assert internal_content not in msg["content"], "SECURITY BREACH: Internal note leaked to customer!"
        assert "TEAM NOTE" not in msg["content"]

    # Also verify the raw response JSON string has zero mention of the private note content
    assert internal_content not in customer_res.text, "SECURITY BREACH: Raw response contains private note!"


def test_reopen_window_enforcement():
    """
    Meera's rule:
    'If a customer is unhappy after we mark a ticket as done, they should be able to open it again.
     But only for about one week. After that it is a new ticket, not the old one.'
    """
    # INC-0322 was resolved 2 days ago (within 7 days)
    res_recent = client.post("/api/customer/tickets/INC-0322/reopen")
    assert res_recent.status_code == 200
    assert res_recent.json()["status"] == "IN_PROGRESS"
