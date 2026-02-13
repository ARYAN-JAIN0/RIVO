"""Database connection and session management - FIXED VERSION

CRITICAL FIX: SQLAlchemy echo is now conditional on DEBUG setting.
In production (DEBUG=False), SQL logging is disabled for better performance.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import get_config

config = get_config()
DATABASE_URL = config.DATABASE_URL

# FIXED: Make echo conditional on DEBUG setting
# echo=True logs all SQL statements (useful for development, bad for production)
engine = create_engine(
    DATABASE_URL, 
    echo=config.DEBUG,  # Only log SQL in debug mode
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600    # Recycle connections after 1 hour
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    """
    Dependency function for getting database sessions.
    Use with FastAPI dependency injection or context managers.
    
    Example:
        with get_db_session() as db:
            leads = db.query(Lead).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_database_connection() -> bool:
    """
    Verify database connectivity at application startup.
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False
