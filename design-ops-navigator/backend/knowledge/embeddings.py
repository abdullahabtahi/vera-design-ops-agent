"""
Embedding and chunking utilities for the knowledge base.

Key design decisions (from reality check):
- Semantic chunking by markdown section (## heading), not fixed token windows.
  Each section is self-contained (one WCAG SC, one heuristic, one principle).
- text-embedding-004 produces 768-dimensional vectors.
- MMR (Maximal Marginal Relevance) implemented in Python over Firestore top-K results
  since Firestore vector search does not natively support MMR.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from google import genai
from google.genai import types
import numpy as np

from config import settings

# Embedding model selection: gemini-embedding-001 on Vertex AI (prod),
# gemini-embedding-2-preview on AI Studio (local dev, multimodal).
# gemini-embedding-2-preview is AI Studio only — 404 on Vertex AI.
import os as _os
_use_vertex = _os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() == "true"
EMBEDDING_MODEL = "gemini-embedding-001" if _use_vertex else "gemini-embedding-2-preview"
EMBEDDING_MODEL_MULTIMODAL = "gemini-embedding-001" if _use_vertex else "gemini-embedding-2-preview"
EMBEDDING_DIM = 768
OUTPUT_DIMENSIONALITY = 768  # forced via output_dimensionality; matches Firestore index

# Chunking config
MAX_CHUNK_TOKENS = 600   # conservative cap; most semantic chunks are well under this
OVERLAP_LINES = 2        # carry last N lines of previous chunk into next (for context)


# ── Data models ───────────────────────────────────────────────────────────────


@dataclass
class Chunk:
    """A single embeddable unit of knowledge."""
    chunk_id: str                  # e.g. "wcag_2_2__sc_1_4_3"
    source_file: str               # e.g. "wcag_2_2.md"
    source_name: str               # e.g. "WCAG 2.2"
    category: str                  # e.g. "Accessibility"
    section_title: str             # e.g. "SC 1.4.3 — Contrast (Minimum) (Level AA)"
    text: str                      # full text of this chunk (heading + body)
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None


# ── Frontmatter parsing ───────────────────────────────────────────────────────


def _parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Extract YAML-like frontmatter between --- delimiters."""
    meta: dict[str, str] = {}
    if not content.startswith("---"):
        return meta, content

    end = content.find("---", 3)
    if end == -1:
        return meta, content

    fm_block = content[3:end].strip()
    body = content[end + 3:].strip()

    for line in fm_block.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip()

    return meta, body


# ── Semantic chunking ─────────────────────────────────────────────────────────


def chunk_document(file_path) -> list[Chunk]:
    """
    Split a markdown knowledge file into semantic chunks by ## heading.
    Each ## section becomes exactly one chunk, preserving context.

    Falls back to paragraph-based chunking if no ## headings exist.
    """
    from pathlib import Path

    path = Path(file_path)
    content = path.read_text(encoding="utf-8")

    meta, body = _parse_frontmatter(content)
    source_name = meta.get("source", path.stem.replace("_", " ").title())
    category = meta.get("category", "General")
    source_file = path.name

    # Extract document-level title (# heading) for context injection
    doc_title = ""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            doc_title = stripped[2:].strip()
            break

    chunks: list[Chunk] = []

    # Split on ## headings — each section is one chunk
    sections = re.split(r"(?m)^(## .+)$", body)
    # sections alternates: [preamble, heading, body, heading, body, ...]

    # sections[0] is the preamble (document intro)
    # Contextual Chunk Headers (Anthropic 2024): prepend a context header to each chunk
    # before embedding. This situates every chunk in its knowledge domain, improving recall
    # for vague or under-specified queries (49% reduction in retrieval failure per paper).
    doc_preamble = sections[0].strip() if sections else ""
    # Trim preamble to first 300 chars for the context header (enough for embedding signal)
    preamble_snippet = doc_preamble[:300].rstrip(".").strip() if doc_preamble else ""
    context_header = f"Source: {source_name} | Category: {category}"
    if preamble_snippet:
        context_header += f"\n{preamble_snippet}"

    pairs = list(zip(sections[1::2], sections[2::2]))

    if not pairs:
        # No ## sections — treat whole document as one chunk
        chunk_id = _make_chunk_id(source_file, doc_title or "full")
        chunks.append(Chunk(
            chunk_id=chunk_id,
            source_file=source_file,
            source_name=source_name,
            category=category,
            section_title=doc_title or source_name,
            text=body[:MAX_CHUNK_TOKENS * 4],  # ~600 tokens
            metadata={"url": meta.get("url", "")},
        ))
        return chunks

    for heading, section_body in pairs:
        heading_text = heading.strip()
        section_text = section_body.strip()

        # Contextual Chunk Headers: context_header situates each chunk in its domain
        embed_text = f"{context_header}\n\n{heading_text}\n\n{section_text}"

        # Trim if over cap (rare for semantic sections)
        if len(embed_text) > MAX_CHUNK_TOKENS * 5:
            embed_text = embed_text[: MAX_CHUNK_TOKENS * 5]

        chunk_id = _make_chunk_id(source_file, heading_text)

        chunks.append(Chunk(
            chunk_id=chunk_id,
            source_file=source_file,
            source_name=source_name,
            category=category,
            section_title=heading_text.lstrip("# ").strip(),
            text=embed_text,
            metadata={
                "url": meta.get("url", ""),
                "heading": heading_text.lstrip("# ").strip(),
            },
        ))

    return chunks


def _make_chunk_id(source_file: str, heading: str) -> str:
    """Create a stable, filesystem-safe chunk ID."""
    base = source_file.replace(".md", "")
    slug = re.sub(r"[^a-z0-9]+", "_", heading.lower()).strip("_")[:50]
    return f"{base}__{slug}"


# ── Embedding ─────────────────────────────────────────────────────────────────


def _get_client() -> genai.Client:
    """Return a configured google.genai client (respects GOOGLE_GENAI_USE_VERTEXAI)."""
    import os
    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() == "true":
        return genai.Client()  # uses service account / ADC
    return genai.Client(api_key=settings.google_api_key)


def embed_texts(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """
    Embed a batch of texts using text-embedding-004.

    task_type:
      "RETRIEVAL_DOCUMENT" — for indexing knowledge base chunks
      "RETRIEVAL_QUERY"    — for embedding user queries at retrieval time
    """
    client = _get_client()

    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=OUTPUT_DIMENSIONALITY,
        ),
    )
    return [e.values for e in response.embeddings]


def embed_chunk(chunk: Chunk) -> Chunk:
    """Embed a single chunk and attach the vector."""
    vectors = embed_texts([chunk.text], task_type="RETRIEVAL_DOCUMENT")
    chunk.embedding = vectors[0]
    return chunk


def embed_chunks_batch(chunks: list[Chunk], batch_size: int = 20) -> list[Chunk]:
    """Embed all chunks in batches to avoid API limits."""
    _get_client()
    embedded: list[Chunk] = []

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c.text for c in batch]
        vectors = embed_texts(texts, task_type="RETRIEVAL_DOCUMENT")
        for chunk, vector in zip(batch, vectors):
            chunk.embedding = vector
            embedded.append(chunk)

        print(f"  Embedded {min(i + batch_size, len(chunks))}/{len(chunks)} chunks")

    return embedded


def embed_query(query: str) -> list[float]:
    """Embed a user query for retrieval against Tier 1 (ux_knowledge) collection."""
    vectors = embed_texts([query], task_type="RETRIEVAL_QUERY")
    return vectors[0]


def embed_image_bytes(image_bytes: bytes, mime_type: str = "image/png") -> list[float]:
    """
    Embed an image using gemini-embedding-2-preview multimodal embeddings.

    Use for indexing user-uploaded images and PDF page renders into Tier 2 (user_knowledge).
    The resulting 768-dim vector can be searched with embed_text_multimodal() queries.

    Args:
        image_bytes: Raw image bytes (PNG, JPEG, WEBP, etc.)
        mime_type: MIME type of the image, e.g. "image/png", "image/jpeg"

    Returns:
        768-dimensional embedding vector.
    """
    client = _get_client()
    image_part = types.Part(
        inline_data=types.Blob(mime_type=mime_type, data=image_bytes)
    )
    response = client.models.embed_content(
        model=EMBEDDING_MODEL_MULTIMODAL,
        contents=[image_part],
        config=types.EmbedContentConfig(output_dimensionality=OUTPUT_DIMENSIONALITY),
    )
    return response.embeddings[0].values


def embed_text_multimodal(text: str, task_type: str = "RETRIEVAL_QUERY") -> list[float]:
    """
    Embed text using gemini-embedding-2-preview for cross-modal search.

    Use for querying Tier 2 (user_knowledge) collection — the query vector must be
    from the same model as the indexed documents to ensure cosine similarity is valid.

    Args:
        text: Query or document text.
        task_type: "RETRIEVAL_QUERY" for queries, "RETRIEVAL_DOCUMENT" for indexing.

    Returns:
        768-dimensional embedding vector.
    """
    client = _get_client()
    response = client.models.embed_content(
        model=EMBEDDING_MODEL_MULTIMODAL,
        contents=[text],
        config=types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=OUTPUT_DIMENSIONALITY,
        ),
    )
    return response.embeddings[0].values


# ── MMR (Maximal Marginal Relevance) ──────────────────────────────────────────


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def mmr_rerank(
    query_embedding: list[float],
    candidates: list[Chunk],
    k: int = 5,
    lambda_mult: float = 0.7,
) -> list[Chunk]:
    """
    Maximal Marginal Relevance reranking.

    Selects k chunks that are relevant to the query AND diverse from each other.
    lambda_mult: 1.0 = pure relevance (like top-k), 0.0 = pure diversity.
    Typically 0.5–0.7 for RAG.

    Requires candidates to have .embedding set.
    """
    if not candidates:
        return []

    if len(candidates) <= k:
        return candidates

    # Compute query-candidate similarities
    query_sims = [
        cosine_similarity(query_embedding, c.embedding)
        for c in candidates
        if c.embedding is not None
    ]

    selected_indices: list[int] = []
    remaining = list(range(len(candidates)))

    for _ in range(k):
        if not remaining:
            break

        best_idx = None
        best_score = float("-inf")

        for idx in remaining:
            relevance = query_sims[idx]

            # Redundancy penalty: max similarity to already-selected chunks
            if selected_indices:
                redundancy = max(
                    cosine_similarity(candidates[idx].embedding, candidates[sel].embedding)
                    for sel in selected_indices
                    if candidates[sel].embedding is not None
                )
            else:
                redundancy = 0.0

            score = lambda_mult * relevance - (1 - lambda_mult) * redundancy
            if score > best_score:
                best_score = score
                best_idx = idx

        if best_idx is not None:
            selected_indices.append(best_idx)
            remaining.remove(best_idx)

    return [candidates[i] for i in selected_indices]


# ── Hybrid BM25 + RRF reranking ───────────────────────────────────────────────


def bm25_scores(query: str, chunks: list[Chunk]) -> list[float]:
    """
    BM25 scores for a query against a list of chunks.

    Uses the candidate set for IDF estimation — not the full corpus, but sufficient
    for reranking a ~20-doc fetch. Exact-term matches (e.g. "WCAG 1.4.3", "Hick's Law")
    are boosted relative to chunks that only match semantically.

    BM25 parameters: k1=1.5, b=0.75 (standard Okapi BM25 defaults).
    """
    query_tokens = re.findall(r'\b\w+\b', query.lower())
    if not query_tokens or not chunks:
        return [0.0] * len(chunks)

    doc_tokens_list = [re.findall(r'\b\w+\b', c.text.lower()) for c in chunks]
    N = len(chunks)
    avgdl = sum(len(d) for d in doc_tokens_list) / N
    k1, b = 1.5, 0.75

    # IDF estimated over the candidate set
    query_set = set(query_tokens)
    idf: dict[str, float] = {}
    for qt in query_set:
        df = sum(1 for d in doc_tokens_list if qt in d)
        idf[qt] = math.log((N - df + 0.5) / (df + 0.5) + 1)

    scores: list[float] = []
    for doc_tokens in doc_tokens_list:
        dl = len(doc_tokens)
        doc_freq: dict[str, int] = {}
        for t in doc_tokens:
            doc_freq[t] = doc_freq.get(t, 0) + 1

        score = 0.0
        for qt in query_tokens:
            if qt in doc_freq:
                tf = doc_freq[qt]
                tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / max(avgdl, 1)))
                score += idf[qt] * tf_norm
        scores.append(score)

    return scores


def rrf_rerank(
    query_embedding: list[float],
    candidates: list[Chunk],
    keyword_query: str,
    k: int = 5,
    rrf_k: int = 60,
) -> list[Chunk]:
    """
    Hybrid reranking via Reciprocal Rank Fusion (vector similarity + BM25).

    Dense retrieval captures semantic intent; BM25 captures exact terminology
    (rule numbers, law names, acronyms). RRF is scale-invariant — no need to
    normalise scores from two different distributions.

    Args:
        query_embedding: Dense vector of the (possibly HyDE-expanded) search query.
        candidates: Fetched chunks with embeddings attached.
        keyword_query: Original user query (pre-HyDE) for BM25 exact-term signal.
        k: Number of chunks to return.
        rrf_k: RRF damping constant (60 is standard; higher = less weight on rank 1).
    """
    if not candidates:
        return []
    valid = [c for c in candidates if c.embedding is not None]
    if not valid:
        return candidates[:k]
    if len(valid) <= k:
        return valid

    # 1. Vector similarity ranking
    vector_sims = [cosine_similarity(query_embedding, c.embedding) for c in valid]
    vector_order = sorted(range(len(valid)), key=lambda i: vector_sims[i], reverse=True)

    # 2. BM25 ranking on original (pre-HyDE) query for exact-term boost
    bm25 = bm25_scores(keyword_query, valid)
    bm25_order = sorted(range(len(valid)), key=lambda i: bm25[i], reverse=True)

    # 3. RRF fusion
    rrf: dict[int, float] = {}
    for rank, idx in enumerate(vector_order):
        rrf[idx] = rrf.get(idx, 0.0) + 1.0 / (rrf_k + rank + 1)
    for rank, idx in enumerate(bm25_order):
        rrf[idx] = rrf.get(idx, 0.0) + 1.0 / (rrf_k + rank + 1)

    final_order = sorted(range(len(valid)), key=lambda i: rrf.get(i, 0.0), reverse=True)
    return [valid[i] for i in final_order[:k]]
