"""SQL Validator module for SchemaScout.

Enforces SQL safety and schema conformity using sqlglot and SQLite EXPLAIN.
Rejects non-SELECT queries, multiple statements, disallowed operations,
nonexistent tables or columns, and syntax errors.
"""

from typing import Any
import sqlglot
from sqlglot import exp
import sqlalchemy as sa
from app.schema_loader import SchemaInfo, load_schema
from app import config


DISALLOWED_EXPRESSIONS = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Command,  # e.g., PRAGMA
    exp.Create,
    exp.Transaction,
)


class SQLValidator:
    """Validates SQL queries against safety rules and reflected database schema."""

    def __init__(self, schema_info: SchemaInfo | None = None, db_url: str | None = None) -> None:
        self.schema_info = schema_info or load_schema(db_url)
        self.db_url = db_url or config.DB_URL
        self._engine = sa.create_engine(self.db_url)

    def validate(self, sql: str) -> tuple[bool, str | None]:
        """Validates a SQL query string.

        Args:
            sql: Raw SQL query string.

        Returns:
            Tuple of (is_valid: bool, error_message: str | None).
        """
        if not sql or not sql.strip():
            return False, "Query is empty."

        clean_sql = sql.strip().rstrip(";")

        # 1. Parse using sqlglot
        try:
            parsed_statements = sqlglot.parse(clean_sql, read="sqlite")
        except Exception as e:
            return False, f"SQL parse error: {str(e)}"

        if not parsed_statements:
            return False, "Failed to parse any valid SQL statement."

        # 2. Reject multiple statements
        if len(parsed_statements) > 1:
            return False, "Multiple SQL statements are strictly forbidden."

        root = parsed_statements[0]
        if root is None:
            return False, "Parsed expression is empty."

        # 3. Must be a SELECT expression (or Union/Subquery that resolves to Select)
        if not isinstance(root, exp.Select) and not (isinstance(root, exp.Union) and isinstance(root.this, exp.Select)):
            return False, f"Only SELECT statements are permitted. Received: {root.key.upper()}"

        # 4. Check for forbidden AST nodes
        for node in root.walk():
            if isinstance(node, DISALLOWED_EXPRESSIONS):
                return False, f"Forbidden statement or command detected: {node.key.upper()}"

        # 5. Check table and column existence against reflected schema
        valid_tables = {tbl.lower(): tbl for tbl in self.schema_info.get_table_names()}
        table_columns: dict[str, set[str]] = {}
        for tbl_name, tbl_meta in self.schema_info.tables.items():
            table_columns[tbl_name.lower()] = {col["name"].lower() for col in tbl_meta.columns}

        # Extract tables and aliases referenced in query
        referenced_tables: set[str] = set()
        alias_map: dict[str, str] = {}
        for tbl_node in root.find_all(exp.Table):
            t_name = tbl_node.name.lower()
            if t_name and t_name not in valid_tables:
                return False, f"Table '{tbl_node.name}' does not exist in schema."
            referenced_tables.add(t_name)
            if tbl_node.alias:
                alias_map[tbl_node.alias.lower()] = t_name
            alias_map[t_name] = t_name

        # Extract columns referenced in query
        # Collect select-list aliases (e.g. SELECT SUM(...) AS TotalSpent ... ORDER BY TotalSpent)
        select_aliases: set[str] = set()
        for select_expr in root.selects:
            if isinstance(select_expr, exp.Alias):
                select_aliases.add(select_expr.alias.lower())
            elif hasattr(select_expr, "alias") and select_expr.alias:
                select_aliases.add(select_expr.alias.lower())

        # Collect all valid columns across referenced tables (or all tables if no explicit table qualifiers)
        allowed_columns: set[str] = set(select_aliases)
        for t_name in referenced_tables:
            allowed_columns.update(table_columns.get(t_name, set()))
        if not allowed_columns:
            for cols in table_columns.values():
                allowed_columns.update(cols)

        # Standard SQL wildcards and expressions
        for col_node in root.find_all(exp.Column):
            c_name = col_node.name.lower()
            # Skip wildcards (*)
            if c_name == "*" or not c_name:
                continue

            # If column is qualified with table name or alias, e.g. Customer.CustomerId or c.CustomerId
            if col_node.table:
                tbl_qualifier = col_node.table.lower()
                actual_table = alias_map.get(tbl_qualifier, tbl_qualifier)
                if actual_table not in table_columns:
                    return False, f"Table qualifier '{col_node.table}' does not exist in schema."
                if c_name not in table_columns[actual_table]:
                    return False, f"Column '{col_node.name}' does not exist in table '{col_node.table}'."
            else:
                if c_name not in allowed_columns:
                    return False, f"Column '{col_node.name}' does not exist in referenced schema tables."

        # 6. Run SQLite EXPLAIN to catch syntax and execution errors
        try:
            with self._engine.connect() as conn:
                conn.execute(sa.text(f"EXPLAIN {clean_sql}"))
        except Exception as e:
            return False, f"SQLite EXPLAIN validation failed: {str(e)}"

        return True, None


def validate_sql(sql: str, schema_info: SchemaInfo | None = None) -> tuple[bool, str | None]:
    """Convenience function for SQL validation."""
    validator = SQLValidator(schema_info=schema_info)
    return validator.validate(sql)
