"""
RAG tool for the Retriever agent.

Exposes `search_knowledge_base` as an ADK-compatible function tool.
The function is a plain Python callable — ADK wraps it as FunctionTool automatically.

Dual-tier search:
  Tier 1 — `ux_knowledge` (WCAG, Nielsen, Gestalt, Material Design, cognitive laws)
            Embedded with gemini-embedding-001. Queried with the same model.
  Tier 2 — `user_knowledge` (team-uploaded PDFs and images)
            Embedded with gemini-embedding-2-preview. Queried with the same model.

RAG improvements:
  HyDE (Hypothetical Document Embeddings, Gao et al. 2022):
    Before embedding the user query, generate a short hypothetical expert answer using
    Gemini Flash. The hypothetical document lives in the same dense embedding space as
    our knowledge chunks → retrieval accuracy improves dramatically for vague or
    conversational queries, bridging the vocabulary gap between questions and answers.
    Falls back to original query if generation fails.
"""

from __future__ import annotations

import os
import time
from functools import lru_cache

from google.cloud import firestore

from knowledge.ingest import get_db, search_knowledge
from knowledge.user_docs import list_user_sources, search_user_knowledge

# ── Team preference cache ───────────────────────────────────────────────────────
# Mutable dict so we can update without a `global` statement.
# Keys: "ts" (float, monotonic time of last fetch), "value" (str).
_team_prefs_cache: dict[str, object] = {"ts": 0.0, "value": ""}
_TEAM_PREFS_TTL = 300  # seconds


def _load_team_preferences() -> str:
    """
    Read recent 'wont_fix' feedback signals from Firestore to derive team rule preferences.
    Returns a brief context string for the reranking prompt, or "" on any failure.

    Cached for 5 minutes to avoid per-request Firestore reads.
    """
    now = time.monotonic()
    if now - float(_team_prefs_cache["ts"]) < _TEAM_PREFS_TTL:
        return str(_team_prefs_cache["value"])

    try:
        docs = (
            _db()
            .collection("issue_feedback")
            .where("status", "==", "wont_fix")
            .limit(60)
            .get()
        )
        citations: dict[str, int] = {}
        for doc in docs:
            data = doc.to_dict()
            cite = (data.get("rule_citation") or "").strip()
            if cite:
                citations[cite] = citations.get(cite, 0) + 1

        if not citations:
            _team_prefs_cache["ts"] = now
            _team_prefs_cache["value"] = ""
            return ""

        top = sorted(citations.items(), key=lambda x: x[1], reverse=True)[:3]
        lines = "\n".join(f'- "{c}" (skipped {n}×)' for c, n in top)
        result = (
            "Team has repeatedly marked these rules as 'won't fix' "
            "(de-prioritize these passages slightly):\n" + lines
        )
        _team_prefs_cache["ts"] = now
        _team_prefs_cache["value"] = result
        return result
    except Exception:
        _team_prefs_cache["ts"] = now
        _team_prefs_cache["value"] = ""
        return ""


@lru_cache(maxsize=1)
def _db() -> firestore.Client:
    """Cached Firestore client (one connection per process)."""
    return get_db()


def _hyde_expand_query(query: str, tier_filter: str = "both") -> str:
    """
    HyDE: generate a hypothetical expert answer, then use it (appended to the original
    query) as the actual search string. This aligns the query embedding with the dense
    text of knowledge-base chunks rather than with the sparse question vocabulary.

    tier_filter controls the vocabulary register of the generated hypothetical:
      - "tier1_only" / "both" → cite WCAG/Nielsen/Gestalt standards (Tier 1 vocabulary)
      - "tier2_only"           → write in design-system/brand-token vocabulary (Tier 2 vocabulary)

    Uses gemini-2.5-flash with a very short prompt for minimal latency overhead.
    Falls back to the original query on any error.
    """
    try:
        from google import genai

        if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() == "true":
            client = genai.Client()
        else:
            from config import settings
            client = genai.Client(api_key=settings.google_api_key)

        if tier_filter == "tier2_only":
            # For Tier 2 (design systems / brand guidelines), generate vocabulary that
            # matches team-uploaded docs: tokens, component names, brand patterns.
            system_ctx = (
                "You are a design system engineer writing internal documentation. "
                "Answer the following question using design system terminology: "
                "tokens, components, variants, spacing scales, brand colors, typography scales, "
                "interaction states, grid systems, and component specs. "
                "Do NOT cite WCAG or Nielsen — focus on how a design system document would describe this. "
                "Be concise (2-3 sentences)."
            )
        else:
            system_ctx = (
                "You are a senior UX designer and accessibility expert. "
                "Write a 2-3 sentence expert answer that directly addresses the following "
                "design or UX question. Cite specific standards or heuristics where relevant "
                "(WCAG success criteria, Nielsen heuristics, Gestalt principles, cognitive laws). "
                "Be concise and factual."
            )

        prompt = f"{system_ctx}\n\nQuestion: {query}\n\nAnswer:"
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        hypothetical = response.text.strip()
        if hypothetical:
            # Combine: original query + hypothetical answer
            # Embedding of this combined text bridges question-vocabulary gap
            return f"{query}\n\n{hypothetical}"
    except Exception:
        pass  # Graceful fallback — never block retrieval on HyDE failure
    return query


def _gemini_rerank(query: str, results: list[dict], top_k: int) -> list[dict]:
    """
    Cross-encoder re-ranking: Gemini scores each retrieved chunk as a (query, passage) pair.

    Unlike BM25 (exact terms) or vector search (independent embeddings), Gemini sees the
    full pair together — capturing paraphrasing, negation, and concept-vs-citation cases
    that both sparse and dense retrieval miss.

    All passages are scored in a single batched call to keep latency minimal (~300ms).
    Falls back to original order on any error — never blocks retrieval.

    Args:
        query: Original user query (pre-HyDE) — Gemini scores against what the user asked.
        results: Candidate chunks (dicts with 'text', 'source_name', 'section_title').
        top_k: Number of top-ranked chunks to return.
    """
    if not results or len(results) <= top_k:
        return results

    try:
        import json as _json
        from google import genai

        if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() == "true":
            client = genai.Client()
        else:
            from config import settings as _settings
            client = genai.Client(api_key=_settings.google_api_key)

        passages = "\n\n".join(
            f"[{i}] {r['source_name']} — {r['section_title']}\n{r['text'][:250]}"
            for i, r in enumerate(results)
        )

        team_ctx = _load_team_preferences()
        pref_block = f"\n{team_ctx}\n" if team_ctx else ""
        prompt = (
            "You are a UX knowledge retrieval expert.\n"
            "Score how relevant each passage is for answering the query. "
            "Use 0.0 (irrelevant) to 1.0 (directly and completely answers the query).\n"
            f"{pref_block}\n"
            f"Query: {query}\n\n"
            f"Passages:\n{passages}\n\n"
            'Return ONLY valid JSON with no explanation: {"scores": [<float for [0]>, <float for [1]>, ...]}'
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        raw = response.text.strip()
        # Strip markdown fences if the model added them despite instructions
        if raw.startswith("```"):
            raw = raw[raw.find("{"):]
            if "```" in raw:
                raw = raw[: raw.rfind("```")]
        data = _json.loads(raw.strip())
        scores = data.get("scores", [])

        if len(scores) != len(results):
            return results[:top_k]

        ranked = sorted(range(len(results)), key=lambda i: scores[i], reverse=True)
        return [results[i] for i in ranked[:top_k]]

    except Exception:
        return results[:top_k]  # graceful fallback: return original order


def search_knowledge_base(
    query: str,
    top_k: int = 5,
    tier_filter: str = "both",
) -> dict:
    """
    Search the UX knowledge base for guidelines relevant to the query.

    Args:
        query: Natural-language search query describing the design concern.
               Examples: "contrast ratio for text on white background",
                         "navigation menu cognitive load",
                         "button tap target size mobile"
        top_k: Total number of chunks to return (1–10). Default 5.
        tier_filter: Which knowledge tier(s) to search.
               "both"      — search Tier 1 (WCAG/Nielsen/Gestalt/etc.) AND Tier 2 (team docs). Default.
               "tier2_only"— search ONLY team-uploaded design system docs / brand guidelines.
                             Use when the user explicitly asks for team-specific or Tier 2 feedback.
               "tier1_only"— search ONLY universal UX rules (WCAG, Nielsen, Gestalt, etc.).

    Returns:
        dict with keys:
          - results: list of knowledge chunks, each with:
              - source_name: e.g. "WCAG 2.2" or "Acme Design System"
              - section_title: e.g. "SC 1.4.3 — Contrast (Minimum) (Level AA)"
              - category: e.g. "Accessibility" or "Team Docs"
              - text: full chunk text (up to 500 chars shown)
              - url: reference URL if available
              - tier: 1 (universal) or 2 (team-uploaded)
          - count: number of results returned
          - status: "ok" or "error"
          - tier_filter: echoes back the filter used
    """
    top_k = max(1, min(top_k, 10))  # clamp
    tier_filter = tier_filter.lower().strip()
    if tier_filter not in ("both", "tier1_only", "tier2_only"):
        tier_filter = "both"

    # HyDE: expand query with a hypothetical expert answer before embedding.
    # Pass tier_filter so the hypothetical uses vocabulary matching the target tier.
    search_query = _hyde_expand_query(query, tier_filter=tier_filter)

    tier1_results: list[dict] = []
    tier2_results: list[dict] = []
    errors: list[str] = []

    if tier_filter in ("both", "tier1_only"):
        # Fetch 2× the budget so Gemini re-ranking has a meaningful pool to work with
        tier1_k_fetch = min(top_k * 2, 10)
        try:
            tier1_results = search_knowledge(
                db=_db(),
                query=search_query,       # HyDE-expanded for vector search
                top_k_fetch=20,           # wider Firestore pool for RRF
                top_k_return=tier1_k_fetch,
                keyword_query=query,      # original query for BM25 exact-term signal
            )
            for r in tier1_results:
                r.setdefault("tier", 1)
        except Exception as exc:
            errors.append(f"Tier 1 search error: {exc}")

    if tier_filter in ("both", "tier2_only"):
        # tier2_only gets the full top_k budget; "both" gives it 3 dedicated slots
        tier2_k = top_k if tier_filter == "tier2_only" else min(3, top_k)
        try:
            tier2_results = search_user_knowledge(
                db=_db(),
                query=search_query,
                top_k_fetch=10,
                top_k_return=tier2_k,
            )
            for r in tier2_results:
                r.setdefault("tier", 2)
        except Exception as exc:
            errors.append(f"Tier 2 search error: {exc}")

    # Merge: Tier 1 first (more authoritative), Tier 2 appended
    # Deduplicate by chunk_id
    seen_ids: set[str] = set()
    merged: list[dict] = []
    for result in tier1_results + tier2_results:
        cid = result.get("chunk_id", result.get("section_title", ""))
        if cid not in seen_ids:
            seen_ids.add(cid)
            merged.append(result)

    if errors and not merged:
        return {
            "status": "error",
            "error": "; ".join(errors),
            "count": 0,
            "results": [],
        }

    # Gemini cross-encoder re-ranking: score each (query, passage) pair as a unit.
    # Uses the original query (pre-HyDE) so Gemini sees exactly what the user asked.
    merged = _gemini_rerank(query, merged, top_k)

    result: dict = {
        "status": "ok",
        "count": len(merged),
        "results": merged,
        "tier_filter": tier_filter,
    }
    if errors:
        result["warnings"] = errors
    return result


def list_knowledge_sources() -> dict:
    """
    List all knowledge sources currently loaded in the knowledge base.

    Returns Tier 1 sources dynamically discovered from Firestore (whatever is actually
    ingested) and any Tier 2 documents the team has uploaded.

    Use this when the user asks what sources, documents, or knowledge the system has access to.

    Returns:
        dict with keys:
          - tier1: list of ingested sources, each with source_name and category
          - tier2: list of team-uploaded sources, each with source_name, category,
                   chunk_count, content_type, and ingested_at
          - tier2_count: number of team-uploaded documents
    """
    from config import settings as _settings

    # Tier 1: discover dynamically from Firestore so new source files
    # are always reflected without changing code.
    _FALLBACK_TIER1 = [
        {"source_name": "WCAG 2.2", "category": "Accessibility"},
        {"source_name": "Nielsen Heuristics", "category": "Usability"},
        {"source_name": "Gestalt Principles", "category": "Visual Design"},
        {"source_name": "Material Design 3", "category": "Design Systems"},
        {"source_name": "Cognitive Laws", "category": "Cognitive Psychology"},
    ]
    try:
        db = _db()
        collection = db.collection(_settings.firestore_collection_knowledge)
        # Project only source_name + category to minimise bandwidth
        docs = collection.select(["source_name", "category"]).get()
        seen: dict[str, str] = {}
        for doc in docs:
            data = doc.to_dict()
            name = data.get("source_name", "")
            cat = data.get("category", "General")
            if name and name not in seen:
                seen[name] = cat
        tier1 = [{"source_name": k, "category": v} for k, v in seen.items()] or _FALLBACK_TIER1
    except Exception:
        tier1 = _FALLBACK_TIER1

    try:
        tier2 = list_user_sources(_db())
    except Exception as exc:
        return {
            "status": "ok",
            "tier1": tier1,
            "tier2": [],
            "tier2_count": 0,
            "tier2_error": str(exc),
        }

    return {
        "status": "ok",
        "tier1": tier1,
        "tier2": tier2,
        "tier2_count": len(tier2),
    }
