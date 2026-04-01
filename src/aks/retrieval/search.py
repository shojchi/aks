"""Assemble retrieved context for agent prompts."""
from __future__ import annotations

from aks.knowledge.store import KnowledgeStore, SearchResult
from aks.utils.config import system_config


def retrieve_context(query: str, store: KnowledgeStore) -> str:
    """Return a formatted context block from the knowledge store."""
    cfg = system_config()
    limit = cfg["retrieval"]["max_chunks"]

    results: list[SearchResult] = store.search(query, limit=limit)
    if not results:
        return ""

    lines = ["## Retrieved Knowledge\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"### [{i}] {r.note.title}")
        lines.append(f"*Source: {r.note.path.name} | relevance: {r.score:.2f}*\n")
        lines.append(r.snippet)
        lines.append("")

    return "\n".join(lines)
