"""
LangChain @tool wrapper around the NumPy VectorStore.

The VectorStore singleton is loaded once at import time and stays in memory.
Both Agent 2 (Weakness) and Agent 3 (Counterargument) share this tool.
"""

from langchain_core.tools import tool

from data_collection.vector_store import VectorStore

_vs = None


def _get_store():
    global _vs
    if _vs is None:
        _vs = VectorStore()
    return _vs


@tool
def search_case_law(
    query: str,
    jurisdiction: str = "",
    top_k: int = 8,
) -> str:
    """Search the legal case law knowledge base for relevant precedent.

    Args:
        query: Natural language search query describing the legal issue or claim.
        jurisdiction: Optional jurisdiction filter (e.g. "U.S.", "Tennessee", "TX").
        top_k: Number of results to return (default 8).

    Returns:
        Formatted string of top matching cases with title, court, date, and text snippet.
    """
    vs = _get_store()
    results = vs.search(
        query=query,
        top_k=top_k,
        jurisdiction=jurisdiction if jurisdiction else None,
    )

    if not results:
        return "No relevant cases found for: %s" % query

    parts = []
    for i, (score, meta) in enumerate(results, 1):
        title = meta.get("title", "Unknown")
        court = meta.get("court", "Unknown court")
        date = meta.get("date", "Unknown date")
        text = meta.get("text", "")
        snippet = text[:500].strip()
        if len(text) > 500:
            snippet += "..."

        parts.append(
            "[%d] %s\n"
            "    Court: %s | Date: %s | Relevance: %.3f\n"
            "    %s"
            % (i, title, court, date, score, snippet)
        )

    return "\n\n".join(parts)
