"""
Tier 2 knowledge ingestion — user-uploaded PDFs and images.

Pipeline:
  Uploaded file (PDF or image)
    → extract pages / decode image
    → embed each chunk with gemini-embedding-2-preview (multimodal)
    → write to Firestore `user_knowledge` collection

The `user_knowledge` collection uses DIFFERENT embeddings (gemini-embedding-2-preview)
from the `ux_knowledge` collection (gemini-embedding-001), so they must be queried
separately — see search_user_knowledge() below.

Run standalone (for testing):
    uv run python -m knowledge.user_docs --file path/to/doc.pdf --name "Design System"
"""

from __future__ import annotations

import hashlib
import io
import time

from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector

from knowledge.embeddings import (
    Chunk,
    embed_image_bytes,
    embed_text_multimodal,
    mmr_rerank,
)
from knowledge.ingest import get_db

# Firestore collection for Tier 2 user-uploaded knowledge
COLLECTION_USER = "user_knowledge"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _chunk_id(filename: str, label: str) -> str:
    """Stable, filesystem-safe chunk ID for user docs."""
    base = filename.replace(".", "_").replace(" ", "_")[:30]
    slug = label.lower().replace(" ", "_").replace("/", "_")[:30]
    return f"user__{base}__{slug}"


def _short_hash(data: bytes) -> str:
    """8-char content hash for deduplication."""
    return hashlib.sha256(data).hexdigest()[:8]


# ── PDF processing ─────────────────────────────────────────────────────────────


def _pdf_to_page_images(file_bytes: bytes) -> list[tuple[bytes, int]]:
    """
    Render each PDF page as a PNG image.

    Returns list of (png_bytes, page_number_1indexed).
    Falls back gracefully if pypdf/PIL rendering fails.
    """
    try:
        from PIL import Image
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        pages: list[tuple[bytes, int]] = []

        for page_num, page in enumerate(reader.pages, start=1):
            # Try to extract embedded images from the page
            page_images = list(page.images)
            if page_images:
                # Use the first image on the page as visual representative
                img_data = page_images[0].data
                img = Image.open(io.BytesIO(img_data)).convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                pages.append((buf.getvalue(), page_num))
            else:
                # No embedded images — we'll use text-only embedding for this page
                pages.append((b"", page_num))

        return pages
    except Exception:
        return []


def _extract_pdf_text_pages(file_bytes: bytes) -> list[tuple[str, int]]:
    """
    Extract text from each PDF page.

    Returns list of (text, page_number_1indexed).
    """
    try:
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        return [
            (page.extract_text() or "", page_num)
            for page_num, page in enumerate(reader.pages, start=1)
        ]
    except Exception as exc:
        raise ValueError(f"Failed to parse PDF: {exc}") from exc


def chunk_uploaded_pdf(
    file_bytes: bytes,
    filename: str,
    source_name: str = "",
    category: str = "Team Docs",
) -> list[Chunk]:
    """
    Process a PDF into embeddable Chunks — one chunk per page.

    Each chunk is embedded with:
    - gemini-embedding-2-preview (multimodal) if the page has a visual
    - gemini-embedding-2-preview (text) otherwise

    Args:
        file_bytes: Raw PDF bytes.
        filename: Original filename (e.g. "design-system-v2.pdf").
        source_name: Human-readable name shown in citations (e.g. "Acme Design System").
        category: Knowledge category tag.

    Returns:
        List of Chunk objects with embeddings attached.
    """
    if not source_name:
        source_name = filename.rsplit(".", 1)[0].replace("-", " ").replace("_", " ").title()

    text_pages = _extract_pdf_text_pages(file_bytes)
    image_pages = _pdf_to_page_images(file_bytes)

    # Build lookup: page_num → png_bytes (empty bytes = no visual)
    image_lookup: dict[int, bytes] = {pg: img for img, pg in image_pages if img}

    chunks: list[Chunk] = []

    for page_text, page_num in text_pages:
        section_title = f"Page {page_num}"
        chunk_id = _chunk_id(filename, f"page_{page_num}")

        # Prefer visual embedding if page image is available
        png_bytes = image_lookup.get(page_num, b"")
        if png_bytes:
            embedding = embed_image_bytes(png_bytes, mime_type="image/png")
            content_type = "pdf_page_visual"
            # If the page has no extractable text, generate a Gemini Vision caption
            # so the LLM can describe what it sees when this chunk is retrieved.
            if page_text.strip():
                embed_text = page_text[:1000]
            else:
                embed_text = _generate_image_caption(png_bytes, "image/png", f"{source_name} p{page_num}")
        else:
            # Text-only page: embed using multimodal model for same vector space
            embed_text = f"{source_name}\n\n{section_title}\n\n{page_text[:1500]}"
            embedding = embed_text_multimodal(embed_text, task_type="RETRIEVAL_DOCUMENT")
            content_type = "pdf_page_text"

        chunk = Chunk(
            chunk_id=chunk_id,
            source_file=filename,
            source_name=source_name,
            category=category,
            section_title=section_title,
            text=page_text[:2000] if page_text.strip() else embed_text,
            metadata={
                "tier": 2,
                "content_type": content_type,
                "page": page_num,
                "total_pages": len(text_pages),
                "has_visual": bool(png_bytes),
            },
            embedding=embedding,
        )
        chunks.append(chunk)
        print(f"  Embedded page {page_num}/{len(text_pages)} ({content_type})")

    return chunks


# ── Gemini Vision captioning ───────────────────────────────────────────────────


def _generate_image_caption(image_bytes: bytes, mime_type: str, source_name: str = "") -> str:
    """
    Use Gemini Flash (multimodal) to generate a descriptive text caption for an image.

    The caption is stored in the chunk's `text` field so the LLM can read it when the
    chunk is retrieved, and it provides textual signal for hybrid BM25 re-ranking.
    The visual embedding is still used for vector search (cross-modal retrieval).

    Falls back to a minimal placeholder on any error — never blocks ingestion.
    """
    import os
    from google import genai
    from google.genai import types as _gtypes

    try:
        if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() == "true":
            client = genai.Client()
        else:
            from config import settings
            client = genai.Client(api_key=settings.google_api_key)

        image_part = _gtypes.Part(
            inline_data=_gtypes.Blob(mime_type=mime_type, data=image_bytes)
        )
        ctx = f"'{source_name}' " if source_name else ""
        prompt = (
            f"You are analysing a design document image {ctx}for a UX knowledge base. "
            "Describe its content specifically and concisely for text-based retrieval. "
            "Include: color values or palettes shown, typography choices, spacing scales, "
            "component names, interaction states (hover/active/disabled/error/success), "
            "design tokens or variables, layout patterns, and any UX rules or guidelines visible. "
            "Write 4-6 sentences. Be precise — a designer should be able to find this image "
            "by searching for any element it contains."
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[image_part, prompt],
        )
        caption = response.text.strip()
        return caption if caption else f"[Visual: {source_name}]"
    except Exception:
        return f"[Visual: {source_name}]"


# ── Image processing ───────────────────────────────────────────────────────────


def chunk_uploaded_image(
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    source_name: str = "",
    category: str = "Team Docs",
) -> list[Chunk]:
    """
    Process a single image into an embeddable Chunk.

    Embeds the image directly with gemini-embedding-2-preview multimodal.

    Args:
        file_bytes: Raw image bytes.
        filename: Original filename (e.g. "color-palette.png").
        mime_type: MIME type (e.g. "image/png", "image/jpeg").
        source_name: Human-readable name for citations.
        category: Knowledge category tag.

    Returns:
        Single-element list containing the embedded Chunk.
    """
    if not source_name:
        source_name = filename.rsplit(".", 1)[0].replace("-", " ").replace("_", " ").title()

    # Generate a descriptive text caption using Gemini Vision.
    # Stored in `text` so the LLM can read it when the chunk is retrieved.
    # The visual embedding (below) handles cross-modal vector similarity.
    print(f"  Generating caption for {filename}...")
    caption = _generate_image_caption(file_bytes, mime_type, source_name)

    embedding = embed_image_bytes(file_bytes, mime_type=mime_type)
    chunk_id = _chunk_id(filename, "image")

    chunk = Chunk(
        chunk_id=chunk_id,
        source_file=filename,
        source_name=source_name,
        category=category,
        section_title=source_name,
        text=caption,
        metadata={
            "tier": 2,
            "content_type": "image",
            "mime_type": mime_type,
            "file_size_bytes": len(file_bytes),
            "content_hash": _short_hash(file_bytes),
        },
        embedding=embedding,
    )
    return [chunk]


# ── Firestore write ────────────────────────────────────────────────────────────


def write_user_chunks(db: firestore.Client, chunks: list[Chunk]) -> int:
    """
    Write user-uploaded chunks to the `user_knowledge` Firestore collection.

    Returns number of documents written.
    """
    collection = db.collection(COLLECTION_USER)
    BATCH_SIZE = 400
    written = 0

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = db.batch()
        for chunk in chunks[i : i + BATCH_SIZE]:
            if chunk.embedding is None:
                continue
            doc_ref = collection.document(chunk.chunk_id)
            batch.set(doc_ref, {
                "chunk_id": chunk.chunk_id,
                "source_file": chunk.source_file,
                "source_name": chunk.source_name,
                "category": chunk.category,
                "section_title": chunk.section_title,
                "text": chunk.text,
                "metadata": chunk.metadata,
                "embedding": Vector(chunk.embedding),
                "ingested_at": firestore.SERVER_TIMESTAMP,
            })
            written += 1
        batch.commit()
        time.sleep(0.1)

    return written


# ── Retrieval ─────────────────────────────────────────────────────────────────


def search_user_knowledge(
    db: firestore.Client,
    query: str,
    top_k_fetch: int = 15,
    top_k_return: int = 3,
) -> list[dict]:
    """
    Search Tier 2 user-uploaded knowledge with gemini-embedding-2-preview.

    The query is embedded with the SAME model used to index user documents
    (gemini-embedding-2-preview), ensuring valid cosine similarity.

    Args:
        db: Firestore client.
        query: Natural-language search query.
        top_k_fetch: Candidates to fetch before MMR.
        top_k_return: Final results after MMR reranking.

    Returns:
        List of result dicts (same schema as search_knowledge() in ingest.py).
    """
    from google.cloud.firestore_v1.base_vector_query import DistanceMeasure

    query_embedding = embed_text_multimodal(query, task_type="RETRIEVAL_QUERY")

    collection = db.collection(COLLECTION_USER)
    results = collection.find_nearest(
        vector_field="embedding",
        query_vector=Vector(query_embedding),
        distance_measure=DistanceMeasure.COSINE,
        limit=top_k_fetch,
    ).get()

    candidates: list[Chunk] = []
    for doc in results:
        data = doc.to_dict()
        embedding = data.get("embedding")
        if hasattr(embedding, "to_map_value"):
            embedding_list = list(embedding)
        elif isinstance(embedding, (list, tuple)):
            embedding_list = list(embedding)
        else:
            embedding_list = None

        candidates.append(Chunk(
            chunk_id=data["chunk_id"],
            source_file=data["source_file"],
            source_name=data["source_name"],
            category=data["category"],
            section_title=data["section_title"],
            text=data["text"],
            metadata=data.get("metadata", {}),
            embedding=embedding_list,
        ))

    reranked = mmr_rerank(query_embedding, candidates, k=top_k_return)

    return [
        {
            "chunk_id": c.chunk_id,
            "source_name": c.source_name,
            "section_title": c.section_title,
            "category": c.category,
            "text": c.text,  # full text — captions and page text are already bounded at ingest
            "url": c.metadata.get("url", ""),
            "tier": 2,
        }
        for c in reranked
    ]


# ── List / stats ──────────────────────────────────────────────────────────────


def list_user_sources(db: firestore.Client) -> list[dict]:
    """
    List all user-uploaded source files with metadata.

    Groups chunks by source_file and returns one entry per file.
    """
    collection = db.collection(COLLECTION_USER)
    docs = collection.select(["source_file", "source_name", "category", "metadata", "ingested_at"]).stream()

    seen: dict[str, dict] = {}
    for doc in docs:
        data = doc.to_dict()
        fname = data["source_file"]
        if fname not in seen:
            ingested_at = data.get("ingested_at")
            seen[fname] = {
                "source_file": fname,
                "source_name": data["source_name"],
                "category": data["category"],
                "content_type": data.get("metadata", {}).get("content_type", "unknown"),
                "chunk_count": 1,
                "ingested_at": ingested_at.isoformat() if hasattr(ingested_at, "isoformat") else str(ingested_at),
            }
        else:
            seen[fname]["chunk_count"] += 1

    return sorted(seen.values(), key=lambda x: x["ingested_at"], reverse=True)


def delete_user_source(db: firestore.Client, source_file: str) -> int:
    """
    Delete all chunks for a given source_file from user_knowledge.

    Returns number of documents deleted.
    """
    collection = db.collection(COLLECTION_USER)
    docs = collection.where("source_file", "==", source_file).stream()
    batch = db.batch()
    count = 0
    for doc in docs:
        batch.delete(doc.reference)
        count += 1
    if count:
        batch.commit()
    return count


# ── URL ingestion (Jina AI Reader) ────────────────────────────────────────────


def _split_markdown_sections(text: str, max_chars: int = 3000) -> list[str]:
    """
    Split markdown into chunks at ## headings, capping each chunk at max_chars.

    Falls back to paragraph splitting if a section exceeds max_chars.
    """
    sections: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in text.splitlines(keepends=True):
        is_heading = line.startswith("## ") or line.startswith("# ")
        if is_heading and current_len > 100:
            sections.append("".join(current).strip())
            current = []
            current_len = 0

        current.append(line)
        current_len += len(line)

        if current_len >= max_chars:
            sections.append("".join(current).strip())
            current = []
            current_len = 0

    if current:
        tail = "".join(current).strip()
        if tail:
            sections.append(tail)

    return [s for s in sections if len(s) > 50]


def chunk_url_content(
    markdown_text: str,
    url: str,
    source_name: str = "",
    category: str = "Web Resource",
) -> list[Chunk]:
    """
    Chunk Jina-fetched markdown into embeddable Chunks.

    Splits by ## headings (semantic chunking). Each chunk is embedded
    with gemini-embedding-2-preview (same vector space as other Tier 2 docs).

    Args:
        markdown_text: Clean markdown returned by Jina Reader.
        url: Source URL (used as source_file for deduplication/deletion).
        source_name: Human-readable citation name.
        category: Knowledge category tag.

    Returns:
        List of Chunk objects with embeddings attached.
    """
    if not source_name:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        source_name = parsed.netloc.replace("www.", "").split(".")[0].title()

    sections = _split_markdown_sections(markdown_text)
    chunks: list[Chunk] = []

    for i, section_text in enumerate(sections):
        # Extract heading as section title if present
        first_line = section_text.splitlines()[0] if section_text else f"Section {i + 1}"
        section_title = first_line.lstrip("#").strip()[:80] or f"Section {i + 1}"

        chunk_id = _chunk_id(url.replace("://", "__").replace("/", "_")[:40], f"s{i}")
        embed_text = f"{source_name}\n\n{section_title}\n\n{section_text[:1500]}"
        embedding = embed_text_multimodal(embed_text, task_type="RETRIEVAL_DOCUMENT")

        chunk = Chunk(
            chunk_id=chunk_id,
            source_file=url,
            source_name=source_name,
            category=category,
            section_title=section_title,
            text=section_text[:2000],
            metadata={
                "tier": 2,
                "content_type": "url",
                "url": url,
                "chunk_index": i,
                "total_chunks": len(sections),
            },
            embedding=embedding,
        )
        chunks.append(chunk)
        print(f"  Embedded section {i + 1}/{len(sections)}: {section_title[:50]}")

    return chunks


def ingest_url_content(
    url: str,
    source_name: str = "",
    category: str = "Web Resource",
    jina_api_key: str = "",
) -> dict:
    """
    Fetch a URL via Jina AI Reader, chunk the markdown, embed, and store in user_knowledge.

    Uses https://r.jina.ai/{url} to get clean markdown from any webpage.

    Args:
        url: The URL to ingest (must be publicly accessible).
        source_name: Citation name (auto-derived from domain if empty).
        category: Knowledge category tag.
        jina_api_key: Jina API key (optional; unauthenticated requests are rate-limited).

    Returns:
        dict with status, chunks_written, source_name, url, content_length
    """
    import httpx

    jina_url = f"https://r.jina.ai/{url}"
    headers = {"Accept": "text/markdown", "X-Return-Format": "markdown"}
    if jina_api_key:
        headers["Authorization"] = f"Bearer {jina_api_key}"

    try:
        resp = httpx.get(jina_url, headers=headers, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        markdown_text = resp.text
    except Exception as exc:
        return {"status": "error", "error": f"Failed to fetch URL via Jina Reader: {exc}", "chunks_written": 0}

    if not markdown_text.strip():
        return {"status": "error", "error": "URL returned empty content", "chunks_written": 0}

    try:
        chunks = chunk_url_content(markdown_text, url, source_name, category)
        if not chunks:
            return {"status": "error", "error": "No content chunks extracted from page", "chunks_written": 0}

        db = get_db()
        written = write_user_chunks(db, chunks)

        return {
            "status": "ok",
            "chunks_written": written,
            "source_name": chunks[0].source_name,
            "category": category,
            "url": url,
            "content_length": len(markdown_text),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc), "chunks_written": 0}


# ── Full ingestion pipeline ────────────────────────────────────────────────────


def ingest_user_doc(
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    source_name: str = "",
    category: str = "Team Docs",
) -> dict:
    """
    Full pipeline: process file → embed → write to Firestore user_knowledge.

    Supports:
      - PDF (application/pdf) — one chunk per page, visual or text embedding
      - Images (image/png, image/jpeg, image/webp, image/gif) — single visual chunk

    Args:
        file_bytes: Raw file bytes.
        filename: Original filename.
        mime_type: MIME type of the upload.
        source_name: Citation name (auto-derived from filename if empty).
        category: Knowledge category shown in citations.

    Returns:
        dict with status, chunks_written, source_name, errors
    """
    db = get_db()
    errors: list[str] = []

    try:
        if mime_type == "application/pdf":
            chunks = chunk_uploaded_pdf(file_bytes, filename, source_name, category)
        elif mime_type.startswith("image/"):
            chunks = chunk_uploaded_image(file_bytes, filename, mime_type, source_name, category)
        else:
            return {
                "status": "error",
                "error": f"Unsupported MIME type: {mime_type}. Supported: PDF, PNG, JPEG, WEBP.",
                "chunks_written": 0,
            }

        if not chunks:
            return {
                "status": "error",
                "error": "No chunks extracted from file.",
                "chunks_written": 0,
            }

        written = write_user_chunks(db, chunks)

        return {
            "status": "ok",
            "chunks_written": written,
            "source_name": chunks[0].source_name,
            "category": category,
            "filename": filename,
            "errors": errors,
        }

    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "chunks_written": 0,
        }


# ── CLI ───────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import argparse
    import mimetypes
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Ingest a user document into Tier 2 knowledge")
    parser.add_argument("--file", required=True, help="Path to PDF or image file")
    parser.add_argument("--name", default="", help="Source name for citations")
    parser.add_argument("--category", default="Team Docs", help="Knowledge category")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"ERROR: File not found: {path}")
        raise SystemExit(1)

    mime_type, _ = mimetypes.guess_type(str(path))
    if not mime_type:
        print(f"ERROR: Could not determine MIME type for {path}")
        raise SystemExit(1)

    print(f"\nIngesting: {path.name} ({mime_type})")
    result = ingest_user_doc(
        file_bytes=path.read_bytes(),
        filename=path.name,
        mime_type=mime_type,
        source_name=args.name,
        category=args.category,
    )

    if result["status"] == "ok":
        print(f"\nIngested {result['chunks_written']} chunks from '{result['source_name']}'")
    else:
        print(f"\nERROR: {result['error']}")
