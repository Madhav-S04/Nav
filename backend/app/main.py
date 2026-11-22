import os
from datetime import datetime
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .config import settings
from .database import engine, Base, SessionLocal, get_db
from .seed_data import seed_database
from .sla_engine import is_during_working_hours, advance_to_working_time, WORK_START, WORK_END, DEFAULT_HOLIDAYS
from .routes import agents, agent_tickets, customer_tickets, audit

# Initialize database schema immediately
Base.metadata.create_all(bind=engine)

def init_db():
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()

# Auto-seed on module import
init_db()

app = FastAPI(
    title="Frontdesk API - Arvo Support System",
    description="Full-stack support management system built for Arvo Systems with business-hour SLA engine, collision prevention, private note isolation, and immutable audit logs.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS: Allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(agents.router, prefix=settings.API_PREFIX)
app.include_router(agent_tickets.router, prefix=settings.API_PREFIX)
app.include_router(customer_tickets.router, prefix=settings.API_PREFIX)
app.include_router(audit.router, prefix=settings.API_PREFIX)

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Frontdesk Backend",
        "database": settings.DATABASE_URL.split("://")[0],
        "server_time_utc": datetime.utcnow().isoformat(),
    }

@app.get("/api/business-calendar")
def get_business_calendar():
    """Returns current working status and calendar rules."""
    now = datetime.utcnow()
    in_work = is_during_working_hours(now)
    next_work = advance_to_working_time(now)
    
    return {
        "working_hours": f"{WORK_START.strftime('%H:%M')} to {WORK_END.strftime('%H:%M')} (Monday to Friday)",
        "current_time_utc": now.isoformat(),
        "is_currently_working_hours": in_work,
        "next_working_start": next_work.isoformat(),
        "holidays": [h.isoformat() for h in sorted(DEFAULT_HOLIDAYS)],
    }

# If frontend build exists, serve static files
dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
if os.path.exists(dist_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(dist_dir, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        file_path = os.path.join(dist_dir, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(dist_dir, "index.html"))
