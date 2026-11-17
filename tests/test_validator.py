"""Unit tests for SQL validator and executor."""

import pytest
from app.validator import validate_sql
from app.executor import execute_sql


def test_validator_accepts_valid_query():
    """Verify that a legitimate SELECT query passes validation."""
    valid_sql = "SELECT CustomerId, FirstName, LastName FROM Customer WHERE Country = 'USA';"
    ok, err = validate_sql(valid_sql)
    assert ok is True, f"Expected valid query to pass, got error: {err}"
    assert err is None


def test_validator_rejects_drop_table():
    """Verify that DROP TABLE is rejected."""
    bad_sql = "DROP TABLE Customer;"
    ok, err = validate_sql(bad_sql)
    assert ok is False
    assert err is not None
    assert "Only SELECT" in err or "Forbidden" in err


def test_validator_rejects_multiple_statements():
    """Verify that multiple statements (e.g. SELECT followed by DELETE) are rejected."""
    bad_sql = "SELECT 1; DELETE FROM Customer;"
    ok, err = validate_sql(bad_sql)
    assert ok is False
    assert err is not None
    assert "Multiple SQL statements" in err


def test_validator_rejects_nonexistent_column():
    """Verify that references to nonexistent columns are rejected."""
    bad_sql = "SELECT fake_column_xyz FROM Customer;"
    ok, err = validate_sql(bad_sql)
    assert ok is False
    assert err is not None
    assert "fake_column_xyz" in err


def test_validator_rejects_nonexistent_table():
    """Verify that references to nonexistent tables are rejected."""
    bad_sql = "SELECT * FROM FakeNonexistentTable;"
    ok, err = validate_sql(bad_sql)
    assert ok is False
    assert err is not None
    assert "FakeNonexistentTable" in err


def test_validator_accepts_alias_in_order_by_and_table_alias():
    """Verify that table aliases and select aliases in ORDER BY pass validation."""
    query = "SELECT c.FirstName, SUM(i.Total) AS TotalSpent FROM Customer c JOIN Invoice i ON c.CustomerId = i.CustomerId GROUP BY c.CustomerId ORDER BY TotalSpent DESC LIMIT 5;"
    ok, err = validate_sql(query)
    assert ok is True, f"Expected alias query to pass, got error: {err}"
    assert err is None


def test_executor_read_only_execution():
    """Verify that read-only execution runs and limits rows."""
    sql = "SELECT CustomerId, FirstName, LastName FROM Customer LIMIT 5;"
    cols, rows = execute_sql(sql)
    assert cols == ["CustomerId", "FirstName", "LastName"]
    assert len(rows) == 5
