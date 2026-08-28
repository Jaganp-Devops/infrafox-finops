"""
Database engine and session management. Uses a containerized Postgres
(see docker-compose.yml, added in Phase 5) rather than RDS - see
ARCHITECTURE.md for the cost reasoning (RDS db.t3.micro alone would cost
more per month than this entire project's compute).

For local/EC2 development before Docker Compose exists, this also works
against a Postgres instance installed directly on the box, or SQLite as
a fallback (see DATABASE_URL in .env).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency - yields a session, always closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
