# Frontdesk - Support System for Arvo Systems

> A full-stack customer support management platform built for Arvo Systems to replace shared spreadsheets and WhatsApp groups. Features an exact business-hours SLA engine, concurrency collision prevention, private note security isolation, and an immutable audit trail.

---

## 1. Executive Summary & Problem Context

Arvo Systems employs 9 support agents handling approximately 40 customer problems daily. The legacy workflow (spreadsheet + WhatsApp) led to severe operational breakdowns:
- **~20% late rate** last quarter with no history or accountability.
- **Incident 4.1 (INC-0291):** Ticket collision — two agents claimed the same ticket simultaneously and gave conflicting answers to the customer.
- **Incident 4.2 (INC-0304):** Data leakage — an internal agent note regarding how to handle a difficult customer was accidentally sent to the customer.
- **Incident 4.3 (INC-0318):** Accountability failure — customer disputed reply time; no immutable timestamp or actor history existed to prove response latency.
- **SLA Discrepancies:** Spreadsheet falsely marked tickets as late over weekends (e.g. ticket arriving Friday at 6:00 PM marked late on Sunday morning) and penalized agents while waiting for customer replies.

**Frontdesk** eliminates these failure modes with a robust backend service and a single unified agent screen.

---

## 2. Business Rules & SLA Engine

### Working Hours & Calendar
- **Business Hours:** 9:30 AM to 6:30 PM (09:30 – 18:30), Monday through Friday (9 working hours = 540 working minutes/day).
- **Weekends:** Saturday and Sunday are non-working days (0 working seconds elapse).
- **Festival Holidays:** Company holidays (New Year, Republic Day, Diwali, Christmas, etc.) are excluded from working time.
- **Friday 6:00 PM Scenario:** A ticket arriving at 6:00 PM on Friday has only 30 working minutes elapsed before the 6:30 PM weekend cutoff. Over Saturday and Sunday, 0 business seconds elapse. On Monday at 9:30 AM, elapsed working time is still exactly 30 minutes. **It is never marked late over the weekend.**

### SLA Targets by Severity
| Severity | Customer Impact | First Reply Target | Resolution Target |
| :--- | :--- | :--- | :--- |
| **URGENT** | Customer cannot work at all | **2 working hours** | **Same working day** (by 18:30) |
| **MEDIUM** | Medium problems | **4.5 working hours** (half a day) | **3 working days** (27 working hours) |
| **SMALL** | Questions or small requests | **1 working day** (9 working hours) | **1 working week** (5 working days / 45 hours) |

### Customer Waiting Time & Lifecycle Rules
- **SLA Clock Pausing:** When an agent transitions a ticket to `WAITING_ON_CUSTOMER`, the SLA clock **immediately pauses**. When the customer replies, the clock **resumes**, with accumulated waiting time credited towards deadlines.
- **Auto-Close:** If a ticket remains in `WAITING_ON_CUSTOMER` for **1 working week** (45 working hours) without a customer reply, it automatically transitions to `CLOSED`.
- **Customer Reopening Window:** When a ticket is marked `RESOLVED`, the customer can reopen it within **7 calendar days** (1 week). Beyond 7 days, reopening is permanently blocked and requires a new ticket.
- **Mid-Flight Severity Escalation:** If a ticket is escalated to `URGENT` mid-flight, SLA targets are recalculated from creation time against the new SLA target. An explicit audit event documents the shift, and any immediate breach is prominently flagged.

---

## 3. Incident Solutions

### 🛡️ Incident 4.1 Resolution: Concurrency & Collision Prevention
- **Atomic Claiming with Optimistic Locking:** When an agent clicks "Take Ticket", an atomic database transaction verifies that `assigned_agent_id IS NULL` and `version == current_version`.
- If two agents attempt to claim the ticket concurrently, the second agent's request is rejected with **HTTP 409 Conflict**: *"Conflict: Ticket has already been claimed by [Agent Name]."*

### 🔒 Incident 4.2 Resolution: Strict Security & Private Note Isolation
- **Architectural Zero-Leak Guarantee:**
  - Messages are strictly segregated: `is_internal = False` (public reply) vs `is_internal = True` (private team note).
  - The Customer-facing API endpoints (`/api/customer/tickets/{ticket_number}`) filter `WHERE is_internal = false`. Private notes are never fetched, serialized, or returned in any customer response, list, or export.
  - The Agent UI features two distinct, color-coded composition tabs:
    - **Public Reply:** Standard blue theme indicating customer visibility.
    - **Private Team Note:** High-contrast amber card with a lock icon and clear warning: *"Visible ONLY to Arvo support team. Never sent to customer."*

### 📜 Incident 4.3 Resolution: Immutable Audit Trail
- **Append-Only Activity Log:** Every state change, claim, public reply, internal note, severity change, and SLA calculation is permanently recorded in the `audit_logs` table.
- **No Mutation Allowed:** The API exposes no `PUT` or `DELETE` endpoints for audit records.
- **Full Transparency:** Agents and managers can review the exact sequence of events down to the second.

---

## 4. Technology Stack

- **Backend:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 ORM, Uvicorn.
- **Database:** PostgreSQL (production / Docker) with automatic fallback to SQLite (`sqlite:///./frontdesk.db`) for instant zero-configuration local runs.
- **Frontend:** React 19, Vite, Lucide Icons, Custom Responsive CSS Design System.
- **Testing:** Pytest (verifying business hours engine, weekend rollover, collision protection, and private note security).

---

## 5. How to Run Locally

### Option A: Quick Local Run (Zero Configuration, SQLite)
The system automatically defaults to SQLite if no PostgreSQL URL is provided.

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd Nav
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r backend/requirements.txt
   ```

3. **Run the application:**
   ```bash
   python run_local.py
   ```
   *(Or on Windows, simply double-click `start.bat`)*

4. **Access the application:**
   - **Web UI (Agent & Customer Portal):** [http://127.0.0.1:8000](http://127.0.0.1:8000)
   - **Interactive API Documentation (Swagger):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

### Option B: Run with Docker Compose (PostgreSQL)

To run the full stack with a dedicated PostgreSQL database container:

```bash
docker compose up --build
```
The app will be available at [http://localhost:8000](http://localhost:8000) with a healthy PostgreSQL instance.

---

## 6. Running Automated Tests

Run the test suite to verify business hour SLA math, weekend rollover, and incident rules:

```bash
python -m pytest backend/tests/test_sla_engine.py -v
```

---

## 7. Pre-Seeded Demonstration Data

Upon startup, Frontdesk automatically seeds the 9 Arvo support agents and key incident scenarios:
- **Meera Raman (Support Lead)** and 8 agents (Alex Chen, Jordan Lee, Sam Rivera, Priya Nair, Rahul Sharma, Elena Rostova, David Kim, Fatima Zahra).
- **INC-0291:** The Collision Incident ticket (ready to test concurrent claim conflict).
- **INC-0304:** The Private Note Incident ticket (contains a confidential note; switch to Customer Portal to verify zero leakage!).
- **INC-0318:** The Disputed Latency Incident ticket (immutable audit trail proving the 40-minute response).
- **INC-0319:** The Friday 6:00 PM ticket (demonstrating that 0 working hours elapse over the weekend).
- **INC-0320:** Urgent severity ticket (2-hour first reply target).
- **INC-0321:** Paused SLA ticket (status: `WAITING_ON_CUSTOMER`).
- **INC-0322:** Resolved ticket eligible for 7-day customer reopening.

---

## 8. What Was Not Finished and Why

See [NOT_FINISHED_EXPLANATION.md](NOT_FINISHED_EXPLANATION.md) for the detailed submission note addressing architectural trade-offs, deferred features, and Phase 2 roadmap.
