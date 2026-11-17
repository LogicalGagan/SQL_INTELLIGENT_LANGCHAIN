# Confidence calculation utilities for SchemaScout.

"""Provides a simple function to compute an overall confidence score (0‑100)
for a generated SQL query based on three factors:

1. Retrieval confidence – derived from the top‑k retrieval scores.
2. Repair usage – whether the repair node was required.
3. Dry‑run row count – proportion of rows returned relative to the
   configured ``MAX_ROWS`` (more rows → higher confidence, up to a limit).

The weights for each component are configurable via ``app.config``.
"""

from __future__ import annotations

from typing import Any

from app import config


def normalize_score(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp and linearly map ``value`` from ``[min_val, max_val]`` to ``[0, 1]``.
    Values outside the range are clipped.
    """
    if value <= min_val:
        return 0.0
    if value >= max_val:
        return 1.0
    return (value - min_val) / (max_val - min_val)


def compute_confidence(
    retrieval_scores: list[float] | None,
    repair_used: bool,
    dry_run_row_count: int | None,
) -> tuple[int, str]:
    """Return a confidence percentage and a short human‑readable reason.

    Parameters
    ----------
    retrieval_scores: list of similarity scores (higher = better) returned by the retriever.
    repair_used: ``True`` if the pipeline executed the repair node.
    dry_run_row_count: number of rows returned by the dry‑run execution (``None`` if dry‑run failed).

    Returns
    -------
    (confidence, reason) where ``confidence`` is an integer 0‑100.
    """
    # 1️⃣ Retrieval component – use the top score (or 0 if not available)
    top_score = retrieval_scores[0] if retrieval_scores else 0.0
    retrieval_conf = normalize_score(top_score)

    # 2️⃣ Repair component – penalize if a repair was needed
    repair_conf = 0.0 if repair_used else 1.0

    # 3️⃣ Row‑count component – reward if we got a decent number of rows
    row_conf = 0.0
    if dry_run_row_count is not None and dry_run_row_count >= 0:
        # Normalise against MAX_ROWS (capped at 1.0)
        row_conf = normalize_score(dry_run_row_count / config.MAX_ROWS)

    # Weighted sum (weights sum to 100)
    total = (
        retrieval_conf * config.CONFIDENCE_WEIGHT_RETRIEVAL
        + repair_conf * config.CONFIDENCE_WEIGHT_REPAIR
        + row_conf * config.CONFIDENCE_WEIGHT_ROW_COUNT
    )
    confidence = int(round(total))

    # Build a short reason string
    parts = []
    parts.append(f"retrieval {int(retrieval_conf*100)}%")
    parts.append("repaired" if repair_used else "no repair")
    if dry_run_row_count is not None:
        parts.append(f"rows {dry_run_row_count}/{config.MAX_ROWS}")
    else:
        parts.append("dry‑run failed")
    reason = ", ".join(parts)
    return confidence, reason
