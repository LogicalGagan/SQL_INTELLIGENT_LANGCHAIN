"""Hybrid retriever fallback.

If the optional hybrid retriever implementation is not present, this module provides
a minimal drop‑in replacement that behaves like the original `SchemaRetriever`
(i.e., pure embedding‑based top‑k table retrieval). It satisfies the same public
interface used by the LangGraph workflow.
"""

from app.retriever import SchemaRetriever

class HybridRetriever(SchemaRetriever):
    """A thin wrapper around `SchemaRetriever`.
    Future versions can add graph‑aware expansion, but for now we simply inherit
    the base class so the rest of the pipeline works unchanged.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    # The `retrieve` method is already provided by `SchemaRetriever`.
    # If additional post‑processing is needed it can be added here.
    
    # Example placeholder for future hybrid logic:
    # def retrieve(self, question: str, k: int | None = None):
    #     # call super().retrieve then expand with graph etc.
    #     return super().retrieve(question, k)
