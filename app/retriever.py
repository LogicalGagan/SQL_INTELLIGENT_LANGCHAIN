"""Schema Retriever module for SchemaScout.

Indexes database table schema documents into Chroma using Ollama embeddings
(nomic-embed-text) and retrieves the top-k most relevant tables for a natural language question.
"""

from typing import Any
from pathlib import Path
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from app.schema_loader import SchemaInfo, load_schema
from app import config


class SchemaRetriever:
    """Retriever that indexes and matches database schema documents using vector embeddings."""

    def __init__(
        self,
        chroma_path: Path | str | None = None,
        embedding_model: str | None = None,
        rebuild: bool = False,
        schema_info: SchemaInfo | None = None,
    ) -> None:
        self.chroma_path = str(chroma_path or config.CHROMA_PATH)
        self.embedding_model = embedding_model or config.EMBEDDING_MODEL
        self.schema_info = schema_info or load_schema()
        
        self.embeddings = OllamaEmbeddings(
            model=self.embedding_model,
            base_url=config.OLLAMA_BASE_URL,
        )
        
        self.vector_store = Chroma(
            collection_name="schema_tables",
            embedding_function=self.embeddings,
            persist_directory=self.chroma_path,
        )

        # Check if index needs building or rebuilding
        count = self.vector_store._collection.count()
        if count == 0 or rebuild:
            self.build_index()

    def build_index(self) -> None:
        """Embeds all reflected schema documents and stores them in Chroma."""
        # Clear existing entries in collection if present
        if self.vector_store._collection.count() > 0:
            existing_ids = self.vector_store._collection.get().get("ids", [])
            if existing_ids:
                self.vector_store._collection.delete(ids=existing_ids)

        docs: list[Document] = []
        ids: list[str] = []
        for tbl_name, tbl_meta in self.schema_info.tables.items():
            docs.append(
                Document(
                    page_content=tbl_meta.document,
                    metadata={"table_name": tbl_name},
                )
            )
            ids.append(tbl_name)

        if docs:
            self.vector_store.add_documents(documents=docs, ids=ids)

    def retrieve(self, question: str, k: int | None = None) -> list[dict[str, Any]]:
        """Retrieves top-k relevant table documents for a natural language question.

        Args:
            question: The natural language user query.
            k: Number of tables to retrieve. Defaults to config.TOP_K_TABLES.

        Returns:
            List of dicts: [{"table_name": str, "document": str, "score": float}]
        """
        top_k = k or config.TOP_K_TABLES
        results_with_scores = self.vector_store.similarity_search_with_score(
            query=question,
            k=top_k,
        )

        retrieved: list[dict[str, Any]] = []
        for doc, score in results_with_scores:
            tbl_name = doc.metadata.get("table_name", "")
            retrieved.append({
                "table_name": tbl_name,
                "document": doc.page_content,
                "score": float(score),
            })

        return retrieved


def retrieve_tables(question: str, k: int | None = None, rebuild: bool = False) -> list[dict[str, Any]]:
    """Convenience helper to retrieve relevant schema tables."""
    retriever = SchemaRetriever(rebuild=rebuild)
    return retriever.retrieve(question=question, k=k)
