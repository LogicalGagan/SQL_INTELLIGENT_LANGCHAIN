"""SQL Query Executor module for SchemaScout.

Executes validated SQL queries against SQLite strictly in read-only mode
with row limit enforcement.
"""

from typing import Any
import sqlite3
from app import config


class SQLExecutor:
    """Executes read-only SQL queries on SQLite database."""

    def __init__(self, db_path: str | None = None, max_rows: int | None = None) -> None:
        self.db_path = str(db_path or config.DB_PATH)
        self.max_rows = max_rows or config.MAX_ROWS
        # Construct read-only URI
        # Forward slashes for SQLite URI
        norm_path = self.db_path.replace("\\", "/")
        self.uri = f"file:{norm_path}?mode=ro"

    def execute(self, sql: str, limit: int | None = None) -> tuple[list[str], list[list[Any]]]:
        """Executes a read-only query and returns column names and rows.

        Args:
            sql: Validated SQL query string.
            limit: Maximum rows to return (capped by max_rows).

        Returns:
            Tuple of (column_names: list[str], rows: list[list[Any]]).
        """
        row_limit = min(limit or self.max_rows, self.max_rows)
        clean_sql = sql.strip().rstrip(";")

        # Open SQLite strictly with uri=True and mode=ro
        conn = sqlite3.connect(self.uri, uri=True)
        try:
            cursor = conn.cursor()
            cursor.execute(clean_sql)
            
            # Extract column names from description
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            # Fetch up to row_limit
            raw_rows = cursor.fetchmany(row_limit)
            rows = [list(row) for row in raw_rows]
            
            return columns, rows
        finally:
            conn.close()


def execute_sql(sql: str, limit: int | None = None) -> tuple[list[str], list[list[Any]]]:
    """Convenience function for SQL execution."""
    executor = SQLExecutor()
    return executor.execute(sql, limit=limit)
