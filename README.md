# SchemaScout (Phase 1: Base)

A local Text-to-SQL assistant using LangChain with schema-aware retrieval.
Given a natural language question, SchemaScout retrieves only relevant database schema segments, generates a safe SQL query using a local Ollama LLM (`qwen2.5-coder:14b`), validates query safety using `sqlglot`, executes it strictly read-only on SQLite (`Chinook`), and presents results in a Streamlit interface.

---

## Architecture Overview

- **LLM**: Local Ollama model (`qwen2.5-coder:14b` default, zero cloud APIs)
- **Embeddings**: Local Ollama embeddings (`nomic-embed-text`)
- **Orchestration**: LangChain (`langchain`, `langchain-community`, `langchain-ollama`, `langchain-chroma`)
- **Vector Store**: Chroma (`./data/chroma`)
- **Database Engine**: SQLAlchemy with SQLite (`./data/chinook.db`)
- **SQL Safety**: `sqlglot` for AST parsing, single-statement SELECT validation, and schema checking
- **Execution**: Strict SQLite URI read-only mode (`file:...?mode=ro&uri=true`) with `MAX_ROWS` limit
- **User Interface**: Streamlit

---

## Setup & Installation

### 1. Install & Configure Ollama
Download and install Ollama from [ollama.com](https://ollama.com).

Pull the required local LLM and embedding models:
```bash
ollama pull qwen2.5-coder:14b
ollama pull nomic-embed-text
```

Ensure Ollama is running:
```bash
ollama list
```

### 2. Set Up Python Environment
SchemaScout requires Python 3.11+.

Create and activate a virtual environment:
```bash
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

Install pinned dependencies:
```bash
pip install -r requirements.txt
```

### 3. Verify Configuration
Verify that the configuration imports cleanly:
```bash
python -c "from app import config; print('Config loaded successfully!')"
```

### 4. Running the Application
Launch the Streamlit web interface:
```bash
streamlit run app/main.py
```

### 5. Running Tests
Run test suites using `pytest`:
```bash
pytest tests/ -v
```
