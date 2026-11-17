"""LangGraph workflow for SchemaScout.

This graph implements the self‑repair pipeline with additional nodes for:
- memory lookup (already used elsewhere)
- ambiguity detection
- confidence calculation
- plain‑English explanation of the final SQL
"""

from __future__ import annotations

from typing import Any, Dict, List

from langgraph.graph import StateGraph, START, END

from app import config
from app.schema_loader import load_schema, SchemaInfo
from app.retriever import SchemaRetriever
try:
    from app.hybrid_retriever import HybridRetriever  # may fallback to SchemaRetriever if not present
except ImportError:
    HybridRetriever = None  # fallback will be handled in node_retrieval
from app.memory import search_notes  # placeholder import, will be defined later
from app.ambiguity import detect_ambiguity
from app.generator import SQLGenerator
from app.validator import SQLValidator
from app.executor import SQLExecutor
from app.confidence import compute_confidence
from app.explanation import generate_explanation  # we will create a tiny wrapper

# Define state shape
class State(Dict):
    """A simple dict‑based state used by LangGraph.
    Keys used:
    - question: str
    - retrieved: list[dict]  # from retriever
    - ambiguous: bool
    - clarification: dict | None
    - sql: str
    - validation_ok: bool
    - error: str | None
    - dry_run_rows: int | None
    - repair_used: bool
    - confidence: int | None
    - confidence_reason: str | None
    - explanation: str | None
    - history: list[dict]  # each attempt record
    """
    pass

# Node implementations
def node_memory_lookup(state: dict) -> dict:
    notes = search_notes(state["question"])  # returns list of strings
    state["memory_hints"] = notes
    return state

def node_retrieval(state: dict) -> dict:
    # Use HybridRetriever if available, else SchemaRetriever
    retriever = HybridRetriever() if hasattr(__import__("app"), "HybridRetriever") else SchemaRetriever()
    retrieval = retriever.retrieve(question=state["question"], k=None)
    # Normalise to list of dicts (already the case for both retrievers)
    state["retrieved"] = retrieval
    return state

def node_ambiguity(state: dict) -> dict:
    ambiguous, payload = detect_ambiguity(state["question"], state["retrieved"])
    state["ambiguous"] = ambiguous
    state["clarification"] = payload
    if ambiguous and payload:
        # For now automatically pick the first option to continue.
        chosen = payload.get("options", [""])[0]
        # Append chosen clarification to the question for downstream nodes.
        state["question"] = f"{state["question"]} (clarified: {chosen})"
    return state

def node_generation(state: dict) -> dict:
    gen = SQLGenerator()
    docs = [item["document"] for item in state["retrieved"]]
    join_hints = state.get("join_hints", [])
    value_hints = state.get("value_hints", [])
    memory_hints = state.get("memory_hints", [])
    sql = gen.generate(
        question=state["question"],
        schema_docs=docs,
        join_hints=join_hints,
        value_hints=value_hints,
    )
    # prepend memory hints as comments (LLM will ignore but we keep for future use)
    if memory_hints:
        sql = f"-- Memory hints: {', '.join(memory_hints)}\n" + sql
    state["sql"] = sql
    return state

def node_validation(state: dict) -> dict:
    validator = SQLValidator(schema_info=load_schema())
    ok, err = validator.validate(state["sql"])
    state["validation_ok"] = ok
    state["error"] = err
    return state

def node_dry_run(state: dict) -> dict:
    executor = SQLExecutor()
    try:
        cols, rows = executor.execute(state["sql"], limit=5)  # dry‑run limited rows
        state["dry_run_rows"] = len(rows)
        state["dry_run_columns"] = cols
        state["dry_run_rows_data"] = rows
        state["dry_run_error"] = None
    except Exception as e:
        state["dry_run_rows"] = None
        state["dry_run_columns"] = []
        state["dry_run_rows_data"] = []
        state["dry_run_error"] = str(e)
        state["validation_ok"] = False
        state["error"] = f"Dry‑run error: {e}"
    return state

def node_repair(state: dict) -> dict:
    # Simple repair: ask the same generator again with added instruction that previous failed
    # In a real system we would craft a repair prompt, but for brevity we just retry generation.
    # Record attempt
    attempt = {"sql": state.get("sql"), "error": state.get("error")}
    state.setdefault("history", []).append(attempt)
    # Mark repair used
    state["repair_used"] = True
    # Re‑generate (could add more context, omitted here)
    gen = SQLGenerator()
    docs = [item["document"] for item in state["retrieved"]]
    sql = gen.generate(
        question=state["question"],
        schema_docs=docs,
        join_hints=state.get("join_hints", []),
        value_hints=state.get("value_hints", []),
    )
    state["sql"] = sql
    # Re‑validate
    validator = SQLValidator(schema_info=load_schema())
    ok, err = validator.validate(sql)
    state["validation_ok"] = ok
    state["error"] = err
    return state

def node_finalize(state: dict) -> dict:
    # Compute confidence
    retrieval_scores = [item.get("score", 0.0) for item in state.get("retrieved", [])]
    confidence, reason = compute_confidence(
        retrieval_scores=retrieval_scores,
        repair_used=state.get("repair_used", False),
        dry_run_row_count=state.get("dry_run_rows"),
    )
    state["confidence"] = confidence
    state["confidence_reason"] = reason
    # Generate plain‑English explanation if final SQL is valid
    if state.get("validation_ok"):
        explanation = generate_explanation(state["sql"])
        state["explanation"] = explanation
    return state

# Build graph
workflow = StateGraph(State)
workflow.add_node("memory_lookup", node_memory_lookup)
workflow.add_node("retrieve", node_retrieval)
workflow.add_node("ambiguity", node_ambiguity)
workflow.add_node("generate", node_generation)
workflow.add_node("validate", node_validation)
workflow.add_node("dry_run", node_dry_run)
workflow.add_node("repair", node_repair)
workflow.add_node("finalize", node_finalize)

workflow.add_edge(START, "memory_lookup")
workflow.add_edge("memory_lookup", "retrieve")
workflow.add_edge("retrieve", "ambiguity")
workflow.add_edge("ambiguity", "generate")
workflow.add_edge("generate", "validate")
workflow.add_edge("validate", "dry_run")
workflow.add_edge("dry_run", "finalize")
# Conditional edges for repair loop
workflow.add_conditional_edges(
    "validate",
    lambda state: not state["validation_ok"],
    {True: "repair", False: "dry_run"},
)
workflow.add_conditional_edges(
    "dry_run",
    lambda state: state.get("dry_run_error") is not None or (state.get("dry_run_rows", 0) == 0 and not state.get("ambiguous", False)),
    {True: "repair", False: "finalize"},
)
# Repair back to validation, but stop after max attempts
workflow.add_conditional_edges(
    "repair",
    lambda state: len(state.get("history", [])) < config.MAX_REPAIRS,
    {True: "validate", False: "finalize"},
)

workflow.set_entry_point(START)
workflow.set_finish_point("finalize")

# Export compiled graph for external use
app = workflow.compile()
