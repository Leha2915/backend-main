# backend/app/db/config.py
from __future__ import annotations
import os
from urllib.parse import quote_plus

#from dotenv import load_dotenv
#load_dotenv()

def _build_pg_url() -> str:
    if url := os.getenv("DATABASE_URL"):
        # Heroku commonly provides postgres://, but SQLAlchemy asyncpg expects
        # postgresql+asyncpg://
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    user = os.getenv("DB_USER")
    password = quote_plus(os.getenv("DB_PASSWORD"))  
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    name = os.getenv("DB_NAME")
    key = os.getenv("JWT_SECRET_KEY")

    missing = [k for k, v in {
        "DB_USER": user,
        "DB_PASSWORD": password,
        "DB_HOST": host,
        "DB_PORT": port,
        "DB_NAME": name,
        "JWT_SECRET_KEY" : key
    }.items() if not v]

    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")
                           

    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"

POSTGRES_URL: str = _build_pg_url()


# Zentrale Konfig – hier kann später z. B. Settings-Libs wie pydantic Settings angebunden werden
#POSTGRES_URL: str = os.getenv(
#    "DATABASE_URL",
#    "postgresql+asyncpg://postgres:secret@localhost:15432/laddering",
#)
