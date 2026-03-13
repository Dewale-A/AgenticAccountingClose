"""
============================================================
Server Launcher
============================================================
Run this file to start the FastAPI server.

Usage:
    python run_server.py

The server starts on http://localhost:8000 by default.
API documentation is available at:
    - Swagger UI: http://localhost:8000/docs
    - ReDoc: http://localhost:8000/redoc

Environment variables:
    API_HOST - Host to bind to (default: 0.0.0.0)
    API_PORT - Port to listen on (default: 8000)
============================================================
"""

import os
import sys
from pathlib import Path

# Add project root to Python path so imports work correctly.
# This is needed when running the script directly (not via a package manager).
project_root = str(Path(__file__).parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

import uvicorn


def main():
    """Start the FastAPI server."""
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8000"))

    print(f"""
    ================================================================
      Agentic Accounting Close Assistant
      SOX-Compliant Governance | Segregation of Duties | HITL
    ================================================================
      Server: http://{host}:{port}
      Docs:   http://{host}:{port}/docs
      Health: http://{host}:{port}/health
    ================================================================
    """)

    uvicorn.run(
        "src.api.routes:app",
        host=host,
        port=port,
        reload=True,  # Auto-reload on code changes (dev mode)
    )


if __name__ == "__main__":
    main()
