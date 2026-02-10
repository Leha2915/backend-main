# backend/app/db/__init__.py
"""
Re-Exports für bequemes Importieren:

    from backend.app.db import Base, get_db, engine, async_session
"""
from .base import Base            # noqa: F401
from .session import get_db, engine, async_session   # noqa: F401
