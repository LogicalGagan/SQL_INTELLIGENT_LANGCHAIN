'''Ambiguity detection utilities for SchemaScout.

This module provides functions to detect whether a user's natural language
question is ambiguous with respect to the retrieved schema tables and
vague wording. If ambiguity is detected the LLM is asked to generate a short
clarifying question together with 2‑3 suggested answer options.
''' 

import re
from typing import Any, Dict, List, Tuple

from app import config
from app.generator import LLMChat  # internal helper that wraps ChatOllama (see generator.py)


def contains_vague_terms(question: str) -> bool:
    """Return True if any of the configured vague terms appear in the question.
    Matching is case‑insensitive and looks for whole words.
    """
    pattern = r"\\b(" + "|".join(map(re.escape, config.VAGUE_TERMS)) + r")\\b"
    return bool(re.search(pattern, question, flags=re.IGNORECASE))


def score_margin_ambiguous(scores: List[float]) -> bool:
    """Return True if the top two retrieval scores are within the margin.
    ``scores`` must be sorted descending (as returned by the retriever).
    """
    if len(scores) < 2:
        return False
    return (scores[0] - scores[1]) < config.AMBIGUITY_MARGIN


def detect_ambiguity(
    question: str,
    retrieval_output: List[Dict[str, Any]],
) -> Tuple[bool, Dict[str, Any] | None]:
    """Detect ambiguity.

    Parameters
    ----------
    question: str
        User question.
    retrieval_output: list of dicts with keys ``table_name`` and ``score``.

    Returns
    -------
    (is_ambiguous, clarification_payload)
        * ``is_ambiguistic`` – bool flag.
        * ``clarification_payload`` – dict with keys ``question`` and ``options``
          (list of strings) if ambiguous, otherwise ``None``.
    """
    # 1️⃣ vague wording check
    vague = contains_vague_terms(question)
    # 2️⃣ score margin check
    scores = [item.get("score", 0.0) for item in retrieval_output]
    margin = score_margin_ambiguous(sorted(scores, reverse=True))
    is_ambiguous = vague or margin

    if not is_ambiguous:
        return False, None

import json
from app.generator import SQLGenerator

# ... (rest unchanged) ...
    # Ask the LLM for a clarifying question + options (JSON output)
    system_prompt = (
        "You are a helpful assistant that resolves ambiguities in natural language "
        "questions for a Text‑to‑SQL system. Generate **ONE** short clarifying question "
        "that would make the intent unambiguous, and provide **2‑3** concise answer "
        "options. Respond **ONLY** with a JSON object of the form:"
        "\n{\n  \"question\": \"...\",\n  \"options\": [\"opt1\", \"opt2\", ...]\n}\n"
        "Do not add any additional commentary."
    )
    # Use the generator's LLM directly for a simple chat.
    llm = SQLGenerator()._llm  # reuse the initialized ChatOllama instance
    user_msg = (
        f"Question: {question}\n"
        f"Retrieved tables (with scores): {', '.join([f"{t['table_name']}({t['score']:.3f})" for t in retrieval_output])}"
    )
    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg},
    ])
    raw = response.content if hasattr(response, "content") else str(response)
    try:
        payload = json.loads(raw.strip())
    except Exception:
        payload = {
            "question": "Could you clarify the metric you want to use?",
            "options": ["Top", "Bottom", "All"],
        }
    return True, payload

        "You are a helpful assistant that resolves ambiguities in natural language "
        "questions for a Text‑to‑SQL system. Generate **ONE** short clarifying question "
        "that would make the intent unambiguous, and provide **2‑3** concise answer "
        "options. Respond **ONLY** with a JSON object of the form:"
        "\n{\n  \"question\": \"...\",\n  \"options\": [\"opt1\", \"opt2\", ...]\n}\n"
        "Do not add any additional commentary."
    )
    # We reuse the generator's LLMChat wrapper for a direct call.
    llm = LLMChat()
    user_msg = (
        f"Question: {question}\n"
        f"Retrieved tables (with scores): {', '.join([f"{t['table_name']}({t['score']:.3f})" for t in retrieval_output])}"
    )
    response = llm.chat(messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_msg}])
    # The response may contain surrounding whitespace; attempt to parse JSON.
    try:
        import json
        payload = json.loads(response.strip())
    except Exception as exc:
        # Fallback: return a simple generic payload.
        payload = {
            "question": "Could you clarify the metric you want to use?",
            "options": ["Top", "Bottom", "All"],
        }
    return True, payload
