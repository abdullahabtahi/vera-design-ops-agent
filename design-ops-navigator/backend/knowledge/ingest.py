"""
Ingest knowledge sources into Firestore vector store.

Pipeline:
  sources/*.md  →  chunk_document()  →  embed_chunks_batch()  →  Firestore

Run:
    uv run python -m knowledge.ingest

For a fresh re-ingest (wipes existing collection):
    uv run python -m knowledge.ingest --reset

Firestore vector index must exist before first run.
Create it in GCP Console:
  Firestore → Indexes → Composite → Add index
    Collection: ux_knowledge
    Field: embedding  Type: Vector  Dimension: 768  Index: Flat

Or via gcloud (if installed):
  gcloud firestore indexes composite create \
    --collection-group=ux_knowledge \
    --query-scope=COLLECTION \
    --field-config=field-path=embedding,vector-config='{"dimension":768,"flat":{}}' \
    --project=YOUR_PROJECT
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from google.cloud import firestore
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector
from google.oauth2 import service_account

from config import settings
from knowledge.embeddings import Chunk, chunk_document, embed_chunks_batch, embed_query, mmr_rerank, rrf_rerank

SOURCES_DIR = Path(__file__).parent / "sources"


# ── Firestore client ──────────────────────────────────────────────────────────


def get_db() -> firestore.Client:
    """
    Build Firestore client.
    Auth priority:
      1. settings.google_application_credentials → service account JSON path
      2. Application Default Credentials (gcloud auth application-default login)
    """
    creds_path = settings.google_application_credentials
    if creds_path:
        creds = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return firestore.Client(
            project=settings.google_cloud_project,
            database=settings.firestore_database,
            credentials=creds,
        )

    # Fall back to ADC (gcloud auth application-default login)
    return firestore.Client(
        project=settings.google_cloud_project,
        database=settings.firestore_database,
    )


# ── Ingest ────────────────────────────────────────────────────────────────────


def load_all_chunks() -> list[Chunk]:
    """Load and chunk all markdown source files."""
    source_files = sorted(SOURCES_DIR.glob("*.md"))
    if not source_files:
        print(f"ERROR: No .md files found in {SOURCES_DIR}")
        print("Run: uv run python -m knowledge.fetch_sources")
        sys.exit(1)

    all_chunks: list[Chunk] = []
    for path in source_files:
        chunks = chunk_document(path)
        print(f"  {path.name:40s} → {len(chunks):3d} chunks")
        all_chunks.extend(chunks)

    return all_chunks


def write_to_firestore(db: firestore.Client, chunks: list[Chunk]) -> None:
    """Write embedded chunks to Firestore in batches."""
    collection = db.collection(settings.firestore_collection_knowledge)

    # Firestore batch write limit: 500 docs per commit
    BATCH_SIZE = 400

    total = len(chunks)
    written = 0

    for i in range(0, total, BATCH_SIZE):
        batch = db.batch()
        batch_chunks = chunks[i : i + BATCH_SIZE]

        for chunk in batch_chunks:
            if chunk.embedding is None:
                print(f"  SKIP {chunk.chunk_id}: no embedding")
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
        print(f"  Wrote {min(i + BATCH_SIZE, total)}/{total} docs to Firestore")
        time.sleep(0.2)  # avoid write quota burst

    print(f"\n  Total written: {written} documents")


def reset_collection(db: firestore.Client) -> None:
    """Delete all documents in the knowledge collection."""
    collection = db.collection(settings.firestore_collection_knowledge)
    docs = collection.list_documents()
    batch = db.batch()
    count = 0

    for doc in docs:
        batch.delete(doc)
        count += 1
        if count % 400 == 0:
            batch.commit()
            batch = db.batch()
            print(f"  Deleted {count} docs...")

    if count % 400 != 0:
        batch.commit()

    print(f"  Deleted {count} existing documents")


# ── Retrieval (for verification) ──────────────────────────────────────────────


def search_knowledge(
    db: firestore.Client,
    query: str,
    top_k_fetch: int = 20,
    top_k_return: int = 5,
    keyword_query: str | None = None,
) -> list[dict]:
    """
    Search the knowledge base with hybrid BM25 + vector reranking (RRF).

    1. Embed query (may be HyDE-expanded) for vector search
    2. Fetch top_k_fetch candidates from Firestore vector search
    3. RRF-combine vector similarity rank + BM25 rank (exact-term boost)
    4. Return top_k_return results

    Args:
        keyword_query: Original user query (pre-HyDE expansion) for BM25 scoring.
                       If None, falls back to query. Passing the original query
                       lets BM25 reward exact rule citations (e.g. "WCAG 1.4.3",
                       "Hick's Law") even when the HyDE expansion adds prose around them.
    """
    query_embedding = embed_query(query)
    bm25_query = keyword_query if keyword_query is not None else query

    collection = db.collection(settings.firestore_collection_knowledge)

    # Firestore vector similarity search
    results = collection.find_nearest(
        vector_field="embedding",
        query_vector=Vector(query_embedding),
        distance_measure=DistanceMeasure.COSINE,
        limit=top_k_fetch,
    ).get()

    # Reconstruct Chunk objects with embeddings for reranking
    candidates: list[Chunk] = []
    for doc in results:
        data = doc.to_dict()
        embedding = data.get("embedding")
        # Firestore returns Vector object; convert to list
        if hasattr(embedding, "to_map_value"):
            embedding_list = list(embedding)
        elif isinstance(embedding, (list, tuple)):
            embedding_list = list(embedding)
        else:
            embedding_list = None

        chunk = Chunk(
            chunk_id=data["chunk_id"],
            source_file=data["source_file"],
            source_name=data["source_name"],
            category=data["category"],
            section_title=data["section_title"],
            text=data["text"],
            metadata=data.get("metadata", {}),
            embedding=embedding_list,
        )
        candidates.append(chunk)

    # Hybrid RRF reranking: vector similarity + BM25 exact-term signal
    reranked = rrf_rerank(query_embedding, candidates, bm25_query, k=top_k_return)

    return [
        {
            "chunk_id": c.chunk_id,
            "source_name": c.source_name,
            "section_title": c.section_title,
            "category": c.category,
            "text": c.text,  # full text — chunks are bounded at ingest (MAX_CHUNK_TOKENS)
            "url": c.metadata.get("url", ""),
        }
        for c in reranked
    ]


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest knowledge sources into Firestore")
    parser.add_argument("--reset", action="store_true", help="Delete existing docs before ingesting")
    parser.add_argument("--verify", type=str, default=None,
                        help="After ingesting, run a test query (e.g. --verify 'contrast ratio')")
    args = parser.parse_args()

    # Validate config
    if not settings.google_cloud_project:
        print("ERROR: GOOGLE_CLOUD_PROJECT not set in .env")
        sys.exit(1)
    if not settings.google_api_key:
        print("ERROR: GOOGLE_API_KEY not set in .env")
        sys.exit(1)

    db = get_db()

    if args.reset:
        print("\nResetting knowledge collection...")
        reset_collection(db)

    print(f"\nLoading chunks from {SOURCES_DIR}...")
    chunks = load_all_chunks()
    print(f"\nTotal chunks to embed: {len(chunks)}")

    print(f"\nEmbedding {len(chunks)} chunks with gemini-embedding-2-preview...")
    chunks = embed_chunks_batch(chunks, batch_size=20)

    print(f"\nWriting to Firestore [{settings.firestore_collection_knowledge}]...")
    write_to_firestore(db, chunks)

    # Optional verification query
    verify_query = args.verify or "contrast ratio WCAG accessibility"
    print(f"\n── Verification query: '{verify_query}' ──")
    try:
        results = search_knowledge(db, verify_query, top_k_fetch=20, top_k_return=5)
        for i, r in enumerate(results, 1):
            print(f"\n  [{i}] {r['source_name']} › {r['section_title']}")
            print(f"       {r['text'][:200]}...")
    except Exception as e:
        print(f"  Retrieval verification failed: {e}")
        print("  (This is expected if the Firestore vector index hasn't been created yet)")
        print("  Create it with:")
        print("  gcloud firestore indexes composite create \\")
        print(f"    --collection-group={settings.firestore_collection_knowledge} \\")
        print("    --query-scope=COLLECTION \\")
        print("    --field-config=field-path=embedding,vector-config='{\"dimension\":768,\"flat\":{}}' \\")
        print(f"    --project={settings.google_cloud_project}")

    print("\nIngestion complete.")


if __name__ == "__main__":
    main()
