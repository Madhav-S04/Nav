import os

class Settings:
    PROJECT_NAME: str = "Frontdesk - Arvo Support System"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    
    # Database: Supports PostgreSQL (e.g. postgresql://user:password@localhost/frontdesk)
    # Automatically falls back to SQLite for instant local zero-setup execution.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./frontdesk.db")
    
    # If using Render / Supabase / Railway postgres, SQLAlchemy requires postgresql:// instead of postgres://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

settings = Settings()
