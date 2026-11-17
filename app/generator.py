"""SQL Generator module for SchemaScout.

Generates safe, precise SQLite SQL queries using a local Ollama LLM.
Accepts retrieved schema documents, join hints, and value hints.
Strips markdown code fences and returns pure SQL strings.
"""

import re
from typing import Any
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from app import config


SYSTEM_PROMPT = """You are an expert SQL assistant. Your task is to generate a single, valid, read-only SQLite SQL query that answers the user's question.

Rules you MUST strictly follow:
1. Output ONLY the raw SQL query. Do NOT include markdown code fences (no ```sql or ```), explanations, comments, or extra text.
2. Generate ONLY a single SELECT query. Do NOT use INSERT, UPDATE, DELETE, DROP, ALTER, PRAGMA, or multiple statements.
3. Use ONLY the tables and columns provided in the Schema Context below. Never invent or assume tables or columns not listed.
4. Ensure all column references match the table definitions.
{join_hints_instruction}
{value_hints_instruction}

Schema Context:
{schema_context}
"""

USER_PROMPT = """Question: {question}

SQL Query:"""


def strip_code_fences(text: str) -> str:
    """Removes markdown code fences (```sql ... ```) and leading/trailing whitespace."""
    cleaned = text.strip()
    # Match ```sql ... ``` or ``` ... ```
    match = re.search(r"```(?:sql)?\s*(.*?)\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()
    # Remove any trailing semicolons or redundant whitespace
    return cleaned.strip()


class SQLGenerator:
    """Generates SQL queries from natural language questions using local Ollama LLMs."""

    def __init__(self, model_name: str | None = None, temperature: float = 0.0) -> None:
        self.model_name = model_name or config.LLM_MODEL
        self.temperature = temperature
        self._llm = self._init_llm()

    def _init_llm(self) -> ChatOllama:
        """Initializes ChatOllama with configured model or local fallback."""
        return ChatOllama(
            model=self.model_name,
            base_url=config.OLLAMA_BASE_URL,
            temperature=self.temperature,
        )

    def generate(
        self,
        question: str,
        schema_docs: list[str],
        join_hints: list[str] | None = None,
        value_hints: list[str] | None = None,
    ) -> str:
        """Generates a clean SQL query string.

        Args:
            question: User's natural language question.
            schema_docs: List of schema document strings for relevant tables.
            join_hints: Optional list of foreign-key join hints (e.g. "Invoice.CustomerId = Customer.CustomerId").
            value_hints: Optional list of column value hints (e.g. "Genre.Name = 'Rock'").

        Returns:
            Pure SQL query string without markdown fences.
        """
        schema_context = "\n".join(schema_docs)

        join_hints_instruction = ""
        if join_hints:
            hints_str = "\n".join(f"- {h}" for h in join_hints)
            join_hints_instruction = f"Join Hints (Use these foreign key conditions to join tables):\n{hints_str}\n"

        value_hints_instruction = ""
        if value_hints:
            v_hints_str = "\n".join(f"- {vh}" for vh in value_hints)
            value_hints_instruction = (
                f"Value Hints (Use exact value strings from these hints in WHERE clauses):\n{v_hints_str}\n"
            )

        prompt_template = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", USER_PROMPT),
        ])

        formatted_messages = prompt_template.format_messages(
            schema_context=schema_context,
            join_hints_instruction=join_hints_instruction,
            value_hints_instruction=value_hints_instruction,
            question=question,
        )

        try:
            response = self._llm.invoke(formatted_messages)
            raw_content = response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            # If the configured model (e.g. 14b) is not yet available, try local fallback qwen2.5:3b
            if "not found" in str(e).lower() and self.model_name != "qwen2.5:3b":
                fallback_llm = ChatOllama(
                    model="qwen2.5:3b",
                    base_url=config.OLLAMA_BASE_URL,
                    temperature=self.temperature,
                )
                response = fallback_llm.invoke(formatted_messages)
                raw_content = response.content if hasattr(response, "content") else str(response)
            else:
                raise e

        return strip_code_fences(raw_content)


def generate_sql(
    question: str,
    schema_docs: list[str],
    join_hints: list[str] | None = None,
    value_hints: list[str] | None = None,
    model_name: str | None = None,
) -> str:
    """Convenience function to generate SQL."""
    generator = SQLGenerator(model_name=model_name)
    return generator.generate(
        question=question,
        schema_docs=schema_docs,
        join_hints=join_hints,
        value_hints=value_hints,
    )
