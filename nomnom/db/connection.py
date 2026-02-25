import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def get_connection(db_path: str) -> sqlite3.Connection:
    """Open a SQLite connection with WAL mode and row factory enabled."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def run_migrations(db_path: str) -> None:
    """Apply any unapplied SQL migration files from the migrations directory."""
    conn = get_connection(db_path)
    try:
        # Ensure tracking table exists
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS _schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()

        applied = {
            row["filename"]
            for row in conn.execute("SELECT filename FROM _schema_migrations")
        }

        migration_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
        for migration_path in migration_files:
            filename = migration_path.name
            if filename in applied:
                continue
            logger.info("Applying migration: %s", filename)
            sql = migration_path.read_text()
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO _schema_migrations (filename) VALUES (?)", (filename,)
            )
            conn.commit()
            logger.info("Migration applied: %s", filename)
    finally:
        conn.close()
