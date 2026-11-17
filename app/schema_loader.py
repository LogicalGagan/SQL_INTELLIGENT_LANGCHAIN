"""Schema loader module for SchemaScout.

Reflects SQLite/SQLAlchemy database schemas to extract tables, columns,
data types, primary keys, and foreign keys. Produces textual schema documents
for vector embeddings and extracts FK relationship tuples for graph construction.
"""

from dataclasses import dataclass, field
from typing import Any
import sqlalchemy as sa
from sqlalchemy import inspect
from app import config


@dataclass
class TableSchema:
    """Represents reflected metadata and schema text for a single database table."""
    table_name: str
    columns: list[dict[str, Any]]
    primary_keys: list[str]
    foreign_keys: list[dict[str, Any]]
    document: str


@dataclass
class SchemaInfo:
    """Container for the complete reflected database schema."""
    tables: dict[str, TableSchema] = field(default_factory=dict)
    documents: list[str] = field(default_factory=list)
    fk_relationships: list[tuple[str, str, str, str]] = field(default_factory=list)

    def get_table_names(self) -> list[str]:
        """Return list of table names."""
        return list(self.tables.keys())

    def get_document(self, table_name: str) -> str | None:
        """Return schema document text for a given table name."""
        tbl = self.tables.get(table_name)
        return tbl.document if tbl else None


def format_table_document(
    table_name: str,
    columns: list[dict[str, Any]],
    primary_keys: list[str],
    foreign_keys: list[dict[str, Any]],
) -> str:
    """Formats table metadata into a structured schema document string.

    Example output:
        Table: Invoice | Columns: InvoiceId (INTEGER, PK), CustomerId (INTEGER, FK -> Customer.CustomerId), Total (NUMERIC)
    """
    col_descriptions: list[str] = []
    
    # Map column names to FK target strings
    fk_map: dict[str, str] = {}
    for fk in foreign_keys:
        referred_table = fk.get("referred_table", "")
        constrained_cols = fk.get("constrained_columns", [])
        referred_cols = fk.get("referred_columns", [])
        for c_col, r_col in zip(constrained_cols, referred_cols):
            fk_map[c_col] = f"{referred_table}.{r_col}"

    for col in columns:
        col_name = col["name"]
        col_type = str(col["type"])
        qualifiers: list[str] = []

        if col_name in primary_keys:
            qualifiers.append("PK")
        if col_name in fk_map:
            qualifiers.append(f"FK -> {fk_map[col_name]}")

        if qualifiers:
            col_descriptions.append(f"{col_name} ({col_type}, {', '.join(qualifiers)})")
        else:
            col_descriptions.append(f"{col_name} ({col_type})")

    cols_str = ", ".join(col_descriptions)
    return f"Table: {table_name} | Columns: {cols_str}"


def load_schema(db_url: str | None = None) -> SchemaInfo:
    """Inspects a database and constructs structured SchemaInfo with documents and FKs.

    Args:
        db_url: Optional database connection URL. Defaults to config.DB_URL.

    Returns:
        SchemaInfo instance containing table details, schema docs, and FK tuples.
    """
    target_url = db_url or config.DB_URL
    engine = sa.create_engine(target_url)
    inspector = inspect(engine)

    schema_info = SchemaInfo()
    table_names = inspector.get_table_names()

    for table_name in table_names:
        # Ignore SQLite internal tables
        if table_name.startswith("sqlite_"):
            continue

        columns = inspector.get_columns(table_name)
        pk_constraint = inspector.get_pk_constraint(table_name)
        pks = pk_constraint.get("constrained_columns", []) if pk_constraint else []
        fks = inspector.get_foreign_keys(table_name)

        doc = format_table_document(table_name, columns, pks, fks)

        table_schema = TableSchema(
            table_name=table_name,
            columns=columns,
            primary_keys=pks,
            foreign_keys=fks,
            document=doc,
        )

        schema_info.tables[table_name] = table_schema
        schema_info.documents.append(doc)

        # Extract (table_a, col_a, table_b, col_b)
        for fk in fks:
            referred_table = fk.get("referred_table")
            constrained_cols = fk.get("constrained_columns", [])
            referred_cols = fk.get("referred_columns", [])
            if referred_table:
                for c_col, r_col in zip(constrained_cols, referred_cols):
                    schema_info.fk_relationships.append(
                        (table_name, c_col, referred_table, r_col)
                    )

    return schema_info
