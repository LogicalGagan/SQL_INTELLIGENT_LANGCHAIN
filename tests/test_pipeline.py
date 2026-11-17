"""Unit and integration tests for the TextToSQL pipeline."""

import pytest
from app.pipeline import TextToSQLPipeline, PipelineResult


@pytest.fixture(scope="module")
def pipeline():
    return TextToSQLPipeline()


def test_pipeline_question_1_simple_select(pipeline):
    """End-to-end test: Simple single-table query."""
    question = "List the first 5 customers"
    result: PipelineResult = pipeline.run(question, top_k=3)

    assert result.validation_ok is True, f"Validation failed with error: {result.error}"
    assert "Customer" in result.retrieved_tables
    assert "SELECT" in result.sql.upper()
    assert len(result.rows) > 0
    assert len(result.rows) <= 5
    assert "total_ms" in result.timings


def test_pipeline_question_2_aggregation(pipeline):
    """End-to-end test: Aggregation query."""
    question = "What is the total invoice amount for customer 1?"
    result: PipelineResult = pipeline.run(question, top_k=3)

    assert result.validation_ok is True, f"Validation failed with error: {result.error}"
    assert "Invoice" in result.retrieved_tables
    assert "SELECT" in result.sql.upper()
    assert "SUM" in result.sql.upper() or "TOTAL" in result.sql.upper()
    assert len(result.rows) == 1
    assert result.rows[0][0] is not None


def test_pipeline_question_3_join_query(pipeline):
    """End-to-end test: Multi-table join query."""
    question = "Which customers spent the most? Show their names and total spending."
    result: PipelineResult = pipeline.run(question, top_k=4)

    assert result.validation_ok is True, f"Validation failed with error: {result.error}"
    assert "Customer" in result.retrieved_tables or "Invoice" in result.retrieved_tables
    assert "SELECT" in result.sql.upper()
    assert len(result.rows) > 0
