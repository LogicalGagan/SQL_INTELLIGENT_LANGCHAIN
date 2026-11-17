"""End-to-end Text-to-SQL Pipeline module for SchemaScout.

Coordinates: Question -> Retrieval -> SQL Generation -> Safety Validation -> Execution.
Returns structured PipelineResult with timings and execution details.
"""

from dataclasses import dataclass, field
import time
from typing import Any
from app.retriever import SchemaRetriever
from app.generator import SQLGenerator
from app.validator import SQLValidator
from app.executor import SQLExecutor
from app.schema_loader import load_schema, SchemaInfo
from app import config


@dataclass
class PipelineResult:
    """Encapsulates all intermediate and final outputs of the Text-to-SQL pipeline."""
    question: str
    retrieved_tables: list[str] = field(default_factory=list)
    table_details: list[dict[str, Any]] = field(default_factory=list)
    join_hints: list[str] = field(default_factory=list)
    value_hints: list[str] = field(default_factory=list)
    sql: str = ""
    validation_ok: bool = False
    error: str | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)


class TextToSQLPipeline:
    """Coordinates retrieval, LLM generation, AST validation, and read-only execution."""

    def __init__(
        self,
        retriever: Any | None = None,
        generator: SQLGenerator | None = None,
        validator: SQLValidator | None = None,
        executor: SQLExecutor | None = None,
        schema_info: SchemaInfo | None = None,
    ) -> None:
        self.schema_info = schema_info or load_schema()
        self.retriever = retriever or SchemaRetriever(schema_info=self.schema_info)
        self.generator = generator or SQLGenerator()
        self.validator = validator or SQLValidator(schema_info=self.schema_info)
        self.executor = executor or SQLExecutor()

    def run(self, question: str, top_k: int | None = None) -> PipelineResult:
        """Executes the complete pipeline for a question.

        Args:
            question: The user's natural language question.
            top_k: Number of tables to retrieve.

        Returns:
            PipelineResult instance with all stage outputs and timings.
        """
        timings: dict[str, float] = {}
        total_start = time.perf_counter()

        result = PipelineResult(question=question)

        # 1. Retrieval
        t0 = time.perf_counter()
        retrieval_output = self.retriever.retrieve(question=question, k=top_k)
        timings["retrieval_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        # Handle both standard retriever and hybrid/graph retriever returns
        if isinstance(retrieval_output, dict):
            # Hybrid retriever dict format
            tables = retrieval_output.get("tables", [])
            docs = retrieval_output.get("documents", [])
            table_details = retrieval_output.get("table_details", [])
            join_hints = retrieval_output.get("join_hints", [])
            value_hints = retrieval_output.get("value_hints", [])
        else:
            # Standard retriever list of dicts format
            table_details = retrieval_output
            tables = [item["table_name"] for item in retrieval_output]
            docs = [item["document"] for item in retrieval_output]
            join_hints = []
            value_hints = []

        result.retrieved_tables = tables
        result.table_details = table_details
        result.join_hints = join_hints
        result.value_hints = value_hints

        # 2. Generation
        t0 = time.perf_counter()
        try:
            sql = self.generator.generate(
                question=question,
                schema_docs=docs,
                join_hints=join_hints,
                value_hints=value_hints,
            )
            result.sql = sql
        except Exception as e:
            result.error = f"SQL Generation error: {str(e)}"
            timings["generation_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            timings["total_ms"] = round((time.perf_counter() - total_start) * 1000, 2)
            result.timings = timings
            return result
        timings["generation_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        # 3. Validation
        t0 = time.perf_counter()
        ok, error_msg = self.validator.validate(result.sql)
        timings["validation_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        result.validation_ok = ok
        result.error = error_msg

        if not ok:
            timings["total_ms"] = round((time.perf_counter() - total_start) * 1000, 2)
            result.timings = timings
            return result

        # 4. Execution
        t0 = time.perf_counter()
        try:
            cols, rows = self.executor.execute(result.sql)
            result.columns = cols
            result.rows = rows
        except Exception as e:
            result.validation_ok = False
            result.error = f"Execution error: {str(e)}"
        timings["execution_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        timings["total_ms"] = round((time.perf_counter() - total_start) * 1000, 2)
        result.timings = timings
        return result
