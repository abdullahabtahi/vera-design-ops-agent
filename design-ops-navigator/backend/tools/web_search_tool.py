"""
Web search fallback tool using DuckDuckGo (no API key required).

Why not google_search (ADK built-in):
  Gemini API rejects agents that mix built-in search tools (google_search)
  with custom function tools on the same agent (400 INVALID_ARGUMENT).
  A plain Python function tool has no such restriction.

Usage:
  Called by root_agent when search_knowledge_base returns count=0,
  or when the user asks for current/recent information.
"""

from __future__ import annotations


def web_search(query: str, max_results: int = 5) -> dict:
    """
    Search the web for current UX, design, or accessibility information.

    Use this when search_knowledge_base returns no results (count=0) or when
    the user explicitly asks for recent/current information (e.g. "latest iOS 18
    guidelines", "new WCAG 3.0 updates", "2026 design trends").

    Args:
        query: The search query, ideally the user's question rephrased as a
               concise web search (e.g. "iOS 18 HIG design guidelines").
        max_results: Number of results to return (default 5, max 10).

    Returns:
        dict with keys:
          - status: "ok" or "error"
          - results: list of dicts, each with title, url, body (snippet)
          - query: the query that was searched
          - source: "web_search"
    """
    max_results = max(1, min(max_results, 10))

    try:
        from ddgs import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")[:400],
                })

        if not results:
            return {
                "status": "ok",
                "results": [],
                "query": query,
                "source": "web_search",
                "note": "No web results found for this query.",
            }

        return {
            "status": "ok",
            "results": results,
            "query": query,
            "source": "web_search",
        }

    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "query": query,
            "source": "web_search",
        }
