# What Did You Not Finish, and Why?

**Candidate Submission Note**  
**Role:** Full Stack Developer  
**System:** Frontdesk (for Arvo Systems)  

---

### Executive Summary

In building **Frontdesk**, the priority was placed squarely on the business-critical requirements revealed in Meera's meeting notes and the three October/November incident reports:
1. **The Business Hours & SLA Engine:** Exact handling of 9:30 AM to 6:30 PM, Monday to Friday, festival holidays, the Friday 6:00 PM rollover rule, customer waiting pause/resume, the 1-week auto-close, the 7-day customer reopen window, and mid-flight severity escalation.
2. **Incident 4.1 Resolution (Collision Prevention):** Atomic database claiming with optimistic locking to prevent dual-agent replies.
3. **Incident 4.2 Resolution (Security & Leak Prevention):** Complete isolation of private team notes at both the database query layer, serialization layer, and frontend UI.
4. **Incident 4.3 Resolution (Auditability):** An append-only, immutable audit log capturing every actor, action, timestamp, and SLA status.
5. **The Unified Agent Screen:** Filterable, real-time ticket management, tabbed customer reply vs. internal note composer, and a complementary Customer Portal simulator.

To deliver a reliable, fully working system within the ~8-hour budget, specific features were deliberately scoped out or deferred. Below is an honest breakdown of what was not finished, why, and how each would be implemented in Phase 2.

---

### 1. Real-Time WebSockets for Live Presence & Typing Indicators

- **What was deferred:** While ticket collision is prevented via **atomic database transactions and optimistic locking version checks** (returning HTTP 409 Conflict if another agent claims or updates a ticket), active real-time typing indicators (e.g., *"Priya is currently typing a reply..."*) were not built with WebSockets.
- **Why it was deferred:** Implementing WebSockets across distributed instances requires an external message broker (such as Redis Pub/Sub) or sticky sessions. For a free-tier hosting deployment (Render/Railway/Fly.io) and easy local evaluation without Redis daemon dependencies, optimistic concurrency control at the database boundary provides 100% data integrity without infrastructure bloat.
- **Phase 2 Plan:** Introduce FastAPI WebSockets or Server-Sent Events (SSE) backed by Redis pub/sub to stream ephemeral presence beacons when an agent focuses the reply box.

---

### 2. Inbound Email Hook / IMAP Synchronization

- **What was deferred:** Inbound email ingestion (receiving customer emails directly from Gmail or Outlook into tickets).
- **Why it was deferred:** Setting up an inbound email pipeline requires registering custom DNS MX records, configuring webhook endpoints on SendGrid/Mailgun/Postmark, and managing SPF/DKIM authentication. In a hiring test environment without access to a company DNS domain, this cannot be evaluated reliably. Instead, we built the **Customer Portal API and web UI**, which replicates the exact customer experience (ticket submission, viewing public message history, replying, and reopening).
- **Phase 2 Plan:** Add a webhook receiver endpoint (`POST /api/webhooks/inbound-email`) using Mailgun/SendGrid parse webhooks with token verification.

---

### 3. Background Cron Worker Daemon (Celery / Redis) for Auto-Close

- **What was deferred:** Stale tickets in `WAITING_ON_CUSTOMER` for > 1 working week (45 working hours) are evaluated on-demand during ticket listing and via a maintenance endpoint (`POST /api/agent/tickets/auto-close-stale`), rather than running a standalone Celery beat background worker process.
- **Why it was deferred:** Running Celery or RQ requires a persistent broker (Redis or RabbitMQ) and a secondary worker process. Running multiple background daemons increases deployment friction for reviewers testing the application locally. On-demand SLA evaluation at query time produces the exact same business outcome with zero external daemon overhead.
- **Phase 2 Plan:** Add APScheduler or Celery Beat scheduled tasks running hourly in production.

---

### 4. Rich-Text WYSIWYG Formatting & File Attachments

- **What was deferred:** The composer uses clean plaintext with structured display rather than a full WYSIWYG editor (such as TipTap or Quill) or file attachment upload.
- **Why it was deferred:** Plain text ensures strict sanitization and avoids XSS vulnerabilities or formatting mismatches when messages are forwarded to customers. File uploads require S3/GCS bucket credentials and presigned URL infrastructure.
- **Phase 2 Plan:** Integrate AWS S3 / Cloudflare R2 presigned uploads with strict MIME-type whitelisting and virus scanning.

---

### 5. Production OAuth2 / SAML Enterprise SSO

- **What was deferred:** The system features 9 pre-seeded Arvo agent identities with a quick-switcher in the navigation bar to allow reviewers to immediately test multi-agent handoffs and collision protection without having to register 9 separate email accounts. Real SAML 2.0 / Okta SSO was omitted.
- **Why it was deferred:** Setting up external identity providers (Google Workspace SSO, Okta) requires domain verification and OAuth client credentials that cannot run in an isolated test repo.
- **Phase 2 Plan:** Implement JWT-based sessions backed by Google Workspace OAuth 2.0 or Auth0.

---

### Summary

The choices made prioritized **sound architecture, ironclad business rules, security isolation, and developer experience**. Every rule from the meeting notes and every failure mode from the October/November incidents has been systematically addressed and verified with automated tests.
