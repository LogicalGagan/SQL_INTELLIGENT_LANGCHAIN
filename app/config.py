"""Configuration module for SchemaScout.

Centralizes paths, models, database URLs, and retrieval/execution parameters.
Values can be overridden using environment variables.
"""

from pathlib import Path
import os

# Base paths
BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = BASE_DIR / "data"
CHROMA_PATH: Path = DATA_DIR / "chroma"
DB_PATH: Path = DATA_DIR / "chinook.db"

# Database URLs
DB_URL: str = os.getenv("SCHEMASCOUT_DB_URL", f"sqlite:///{DB_PATH.as_posix()}")
DB_READ_ONLY_URL: str = os.getenv(
    "SCHEMASCOUT_DB_READ_ONLY_URL",
    f"sqlite:///file:{DB_PATH.as_posix()}?mode=ro&uri=true"
)

# Ollama Models & Endpoint
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL: str = os.getenv("SCHEMASCOUT_LLM_MODEL", "qwen2.5-coder:14b")
EMBEDDING_MODEL: str = os.getenv("SCHEMASCOUT_EMBEDDING_MODEL", "nomic-embed-text")

# Retrieval & Execution settings
TOP_K_TABLES: int = int(os.getenv("TOP_K_TABLES", "4"))
MAX_TABLES_AFTER_EXPANSION: int = int(os.getenv("MAX_TABLES_AFTER_EXPANSION", "6"))
MAX_ROWS: int = int(os.getenv("MAX_ROWS", "100"))

# Ambiguity detection settings
AMBIGUITY_MARGIN: float = float(os.getenv("AMBIGUITY_MARGIN", "0.1"))  # score diff threshold
VAGUE_TERMS: list[str] = ["best", "top", "most", "largest", "smallest", "recent", "first", "last", "highest", "lowest"]

# Confidence calculation weights (out of 100)
CONFIDENCE_WEIGHT_RETRIEVAL: int = int(os.getenv("CONFIDENCE_WEIGHT_RETRIEVAL", "40"))
CONFIDENCE_WEIGHT_REPAIR: int = int(os.getenv("CONFIDENCE_WEIGHT_REPAIR", "30"))
CONFIDENCE_WEIGHT_ROW_COUNT: int = int(os.getenv("CONFIDENCE_WEIGHT_ROW_COUNT", "30"))
