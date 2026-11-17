"""Unit tests for the schema loader module."""

import pytest
from app.schema_loader import load_schema, format_table_document


def test_schema_loader_chinook():
    """Verify that Chinook schema loads correctly with Invoice and Customer tables and FKs."""
    schema_info = load_schema()
    table_names = schema_info.get_table_names()

    # Assert required tables exist
    assert "Invoice" in table_names, "Expected 'Invoice' table to be reflected."
    assert "Customer" in table_names, "Expected 'Customer' table to be reflected."

    # Assert documents exist and format correctly
    invoice_doc = schema_info.get_document("Invoice")
    customer_doc = schema_info.get_document("Customer")
    assert invoice_doc is not None
    assert customer_doc is not None
    assert "Table: Invoice" in invoice_doc
    assert "InvoiceId" in invoice_doc
    assert "CustomerId" in invoice_doc
    assert "FK -> Customer.CustomerId" in invoice_doc

    # Assert foreign-key relationship detection
    # Format: (table_a, col_a, table_b, col_b)
    invoice_to_customer_fk = ("Invoice", "CustomerId", "Customer", "CustomerId")
    assert invoice_to_customer_fk in schema_info.fk_relationships, (
        f"Expected FK relationship {invoice_to_customer_fk} in {schema_info.fk_relationships}"
    )


def test_format_table_document_synthetic():
    """Verify formatting on a synthetic table definition."""
    columns = [
        {"name": "id", "type": "INTEGER"},
        {"name": "name", "type": "VARCHAR(50)"},
        {"name": "dept_id", "type": "INTEGER"},
    ]
    pks = ["id"]
    fks = [
        {
            "name": "fk_dept",
            "constrained_columns": ["dept_id"],
            "referred_table": "Department",
            "referred_columns": ["id"],
        }
    ]

    doc = format_table_document("Employee", columns, pks, fks)
    assert doc == "Table: Employee | Columns: id (INTEGER, PK), name (VARCHAR(50)), dept_id (INTEGER, FK -> Department.id)"
