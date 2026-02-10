# backend/app/db/base.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """Gemeinsame Basisklasse aller ORM-Modelle."""
    pass
