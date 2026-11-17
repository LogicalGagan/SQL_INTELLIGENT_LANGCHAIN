"""Entry point to run the full SchemaScout application.

- Checks that the Ollama server is reachable.
- Builds (or rebuilds) the Chroma indexes for schema, value hints, and memory.
- Launches the Streamlit UI.

Usage:
    python -m app.run_all
"""

import sys
import subprocess
import time
from pathlib import Path

from app import config

def check_ollama() -> bool:
    """Simple health‑check: try `ollama list` which contacts the local server.
    Returns True if the command succeeds (exit code 0)."""
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, check=True)
        return True
    except Exception as e:
        print(f"Ollama health check failed: {e}")
        return False

def build_indexes():
    """Force rebuilding of all Chroma collections.
    This imports the relevant modules which trigger index building on init.
    """
    # Schema index
    from app.retriever import SchemaRetriever
    SchemaRetriever(rebuild=True)
    # Value index (if the module exists)
    try:
        from app.value_index import ValueIndex
        ValueIndex(rebuild=True)
    except Exception:
        pass
    # Memory index – ensure collection exists
    try:
        from app.memory import MemoryStore
        MemoryStore(init=True)
    except Exception:
        pass
    print("All indexes built/rebuilt.")

def launch_streamlit():
    """Launch Streamlit UI as a background process.
    Streamlit runs a server on port 8501.
    """
    cmd = [sys.executable, "-m", "streamlit", "run", "app/main.py", "--server.port", "8501"]
    # Use subprocess without waiting; let it run independently.
    subprocess.Popen(cmd)
    print("Streamlit UI launched at http://localhost:8501")

if __name__ == "__main__":
    if not check_ollama():
        sys.exit("Ollama is not running. Please start Ollama before proceeding.")
    build_indexes()
    launch_streamlit()
    # Keep the script alive so the background process stays; Ctrl‑C to stop.
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("Shutting down.")
