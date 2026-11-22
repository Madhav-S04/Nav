"""
Frontdesk Local Runner
Launches the FastAPI backend which serves both the REST API and the built React frontend.
Open http://127.0.0.1:8000 in your browser!
"""

import sys
import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("  FRONTDESK - Arvo Systems Support Platform")
    print("  Starting unified full-stack server...")
    print("  Access the app at: http://127.0.0.1:8000")
    print("  Interactive API Swagger Docs: http://127.0.0.1:8000/docs")
    print("=" * 60)
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
