"""
Database connection and session management using SQLAlchemy.
"""
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from sqlalchemy.pool import StaticPool

from app.config import get_settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


# Get settings
settings = get_settings()

# Create engine with appropriate configuration
if settings.database_url.startswith("sqlite"):
    # SQLite specific configuration
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=settings.log_level == "DEBUG"
    )

    # Enable foreign key support for SQLite
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        """Enable foreign key constraints for SQLite."""
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    # PostgreSQL or other databases
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        echo=settings.log_level == "DEBUG"
    )

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session.
    Yields a session and ensures it's closed after use.

    Usage in FastAPI:
        @app.get("/items/")
        def read_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize the database by creating all tables.
    This should be called during application startup.
    """
    # Import models to ensure they're registered
    from app import models  # noqa: F401

    # Create all tables
    Base.metadata.create_all(bind=engine)


def drop_db() -> None:
    """
    Drop all database tables.
    WARNING: This will delete all data!
    Use only for testing or complete reset.
    """
    from app import models  # noqa: F401
    Base.metadata.drop_all(bind=engine)


def reset_db() -> None:
    """
    Reset the database by dropping and recreating all tables.
    WARNING: This will delete all data!
    """
    drop_db()
    init_db()


class DatabaseManager:
    """
    Database manager for advanced operations.
    """

    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    def close_session(self, session: Session) -> None:
        """Close a database session."""
        session.close()

    def create_tables(self) -> None:
        """Create all database tables."""
        init_db()

    def drop_tables(self) -> None:
        """Drop all database tables."""
        drop_db()

    def reset_tables(self) -> None:
        """Reset all database tables."""
        reset_db()

    def check_connection(self) -> bool:
        """
        Check if database connection is working.
        Returns True if connection is successful, False otherwise.
        """
        try:
            from sqlalchemy import text
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def get_table_names(self) -> list[str]:
        """Get list of all table names in the database."""
        return list(Base.metadata.tables.keys())

    def backup_database(self, backup_path: str) -> bool:
        """
        Backup SQLite database to a file.
        Only works with SQLite databases.

        Args:
            backup_path: Path where backup should be saved

        Returns:
            True if backup successful, False otherwise
        """
        if not settings.database_url.startswith("sqlite"):
            raise NotImplementedError("Backup only supported for SQLite databases")

        try:
            import shutil

            # Get the database file path from URL
            db_path = settings.database_url.replace("sqlite:///", "")

            # Create backup
            shutil.copy2(db_path, backup_path)
            return True
        except Exception:
            return False


# Global database manager instance
db_manager = DatabaseManager()


def get_db_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    return db_manager
