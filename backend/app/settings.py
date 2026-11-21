"""Environment-driven settings. See .env.example in the project root."""

import os

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


def _split(value):
    items = []
    for part in value.split(","):
        part = part.strip()
        if part:
            items.append(part)
    return items


DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./stress_platform.db")
# Render and Heroku hand out 'postgres://' URLs, SQLAlchemy needs 'postgresql://'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

CORS_ORIGINS = _split(os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"))
MIN_METRIC_INTERVAL_SECONDS = float(os.environ.get("MIN_METRIC_INTERVAL_SECONDS", "20"))
MAX_SESSIONS_PER_CLIENT = int(os.environ.get("MAX_SESSIONS_PER_CLIENT", "200"))
DATA_RETENTION_DAYS = int(os.environ.get("DATA_RETENTION_DAYS", "90"))
FRONTEND_DIST = os.environ.get("FRONTEND_DIST", os.path.join(PROJECT_ROOT, "frontend", "dist"))
CONSENT_VERSION = "2026-11-v1"
