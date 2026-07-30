"""Vercel serverless entrypoint.

Vercel's Python runtime discovers an ASGI callable named ``app`` in files under
``api/``. Every route is rewritten here by vercel.json, so the same FastAPI
application serves both this and the long-running Docker deployment.
"""

import sys
from pathlib import Path

# The function's working directory is the project root, but `app` sits beside
# this file's parent — make sure it is importable either way.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402

__all__ = ["app"]
