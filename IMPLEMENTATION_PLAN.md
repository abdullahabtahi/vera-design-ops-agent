# Design Ops Navigator — Implementation Plan

> Target: Gemini Live Agent Challenge hackathon submission
> Stack: Google ADK 1.27.1 · Gemini 2.0 Flash · Firestore · Next.js 15 · CopilotKit/AG-UI · Cloud Run · Vercel
> Working dir: repo root (this file lives here)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Next.js 15 Frontend (Vercel)                               │
│  CopilotKit UI ←→ AG-UI SSE protocol                        │
│  Components: DesignCopilot | AgentTimeline | CritiqueView   │
└──────────────────────────┬──────────────────────────────────┘
                           │ SSE (AG-UI events)
┌──────────────────────────▼──────────────────────────────────┐
│  FastAPI + ADK Server (Cloud Run)                           │
│                                                             │
│  Orchestrator Agent                                         │
│      │                                                      │
│      ├── ParallelAgent                                      │
│      │     ├── Retriever Agent ──→ Firestore vector search  │
│      │     └── Critic Agent    ──→ Figma REST API + Gemini  │
│      │                              multimodal              │
│      └── Evaluator Agent (autorater/judge)                  │
│                                                             │
└────────────┬──────────────────────────┬─────────────────────┘
             │                          │
     Firestore (vectors)          GCS (screenshots)
     Gemini Embeddings 2          Figma REST API
```

### 4-Agent Roles

| Agent | Pattern | Model | Responsibility |
|---|---|---|---|
| **Orchestrator** | ADK `Agent` (supervisor) | Gemini 2.0 Flash | Parses intent, routes to sub-agents, synthesizes final response, emits AG-UI events |
| **Retriever** | ADK `Agent` (worker) | Gemini 2.0 Flash | Agentic RAG: broad search → MMR reranking → optional refinement pass |
| **FigmaFetcher** | ADK `Agent` (worker) | Gemini 2.0 Flash | Fetches frame PNG + node tree from Figma — purely data collection, no analysis |
| **Critic** | ADK `Agent` (worker) | Gemini 2.0 Flash (multimodal) | Two-pass visual analysis using BOTH retrieved knowledge + fetched Figma frame |
| **Evaluator** | ADK `Agent` (judge) | Gemini 2.0 Flash | Checks grounding, scores suggestions, filters low-confidence items — autorater pattern |

### Execution Stages (replaces single ParallelAgent)

```
Orchestrator
  ↓
Stage 1 — ParallelAgent([Retriever, FigmaFetcher])
  Retriever:     knowledge search (3-5s)    ─┐
  FigmaFetcher:  frame PNG + node tree (3s) ─┘ → both complete before Stage 2
  ↓
Stage 2 — Critic
  Receives: retrieved_knowledge + image_bytes + figma_context
  Runs: two-pass multimodal analysis → structured JSON critique
  ↓
Stage 3 — Evaluator
  Receives: critique_items → scores, filters, annotates
  ↓
Orchestrator synthesizes final response
```

**Why this is correct**: Retriever and FigmaFetcher are truly independent (different data sources, no shared state). Critic is *dependent* on both — it can't analyze without knowledge snippets (no grounding) and can't analyze without the image (nothing to see). Running Stage 1 in parallel saves ~3-5 seconds of wall-clock time.

### Per-Agent Tool Assignment

> Rule: give each agent only the tools it needs. Lean tool sets = less hallucinated tool calls.

| Agent | ADK Built-in | FunctionTools | MCPToolset |
|---|---|---|---|
| **Orchestrator** | — | `parse_figma_url` | — |
| **Retriever** | `google_search` | `search_knowledge_base`, `index_team_knowledge`, `fetch_web_content` | `filesystem` (read design docs from GCS/disk) |
| **FigmaFetcher** | — | `get_figma_frame_image`, `get_figma_file_context` | `figma_mcp` (official MCP — variants, tokens, layout) |
| **Critic** | — | `check_wcag_contrast`, `generate_spec_json`, `generate_test_script` | — |
| **Evaluator** | `google_search` | — | — |

> `analyze_visual_design` is **not a FunctionTool** — it is called directly by the Critic's execution code after receiving the session state outputs from Stage 1. The Critic agent's native multimodal capability (Gemini 2.0 Flash) processes the image bytes directly.

**Why `google_search` on Retriever?**
The knowledge base is pre-loaded but frozen. Live search lets the Retriever augment with current WCAG errata, NNg articles, and platform guidelines — without re-indexing.

**Why Figma MCP on Critic (not just REST API)?**
REST `/images` gives PNG. REST `/files` gives raw JSON tree. The official Figma MCP (`@figma/mcp`) exposes higher-level tools: component variants, resolved styles, design tokens, layout constraints — all structured and named. The Critic gets richer context about *what* it's looking at.

**Why `check_wcag_contrast` as a FunctionTool (not LLM)?**
Contrast ratios are math, not reasoning. Delegating to the LLM produces hallucinated ratios. A deterministic Python function gives exact WCAG 2.2 pass/fail — the Critic can cite `"actual ratio: 3.8:1, required: 4.5:1"` with confidence.

**Why `filesystem` MCP on Retriever?**
Allows the Retriever to read Tier 2 team docs (design system markdown, Notion exports, past specs) directly from a mounted path or GCS FUSE — without embedding everything upfront.

### AG-UI Event Stream

Define exactly these SSE event types (emit from Orchestrator as sub-agents progress):

```
agent_routing          → Orchestrator decided routing plan
knowledge_retrieved    → Retriever returned N snippets
figma_frame_loaded     → Critic received PNG from Figma API
critique_generated     → Critic produced structured JSON
evaluation_complete    → Evaluator scored and filtered
response_ready         → Final synthesized response
```

---

## Directory Structure

```
design-ops-navigator/
├── backend/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── orchestrator.py       # Supervisor agent
│   │   ├── retriever.py          # Agentic RAG agent
│   │   ├── critic.py             # Multimodal critic agent
│   │   └── evaluator.py          # Judge/autorater agent
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── figma_tools.py        # Figma REST API wrappers (frame image, node tree)
│   │   ├── rag_tools.py          # Firestore vector search + MMR reranking
│   │   ├── spec_tools.py         # Spec JSON + test script generation
│   │   ├── wcag_tools.py         # Deterministic WCAG contrast checker (no LLM)
│   │   ├── web_tools.py          # httpx-based web content fetcher
│   │   └── mcp_tools.py          # MCPToolset factories (Figma MCP, filesystem MCP)
│   ├── knowledge/
│   │   ├── ingest.py             # Document ingestion pipeline
│   │   ├── embeddings.py         # Gemini embedding helpers
│   │   └── sources/              # Pre-loaded UX knowledge (markdown files)
│   │       ├── wcag_2_2.md
│   │       ├── gestalt.md
│   │       ├── nielsen_heuristics.md
│   │       ├── fitts_hick_miller.md
│   │       ├── material_design_3.md
│   │       └── apple_hig.md
│   ├── agentops/
│   │   ├── logger.py             # Trajectory logging to Firestore
│   │   └── metrics.py            # Goal completion, grounding rate, tool efficiency
│   ├── server.py                 # FastAPI app + ADK runner + SSE endpoint
│   ├── config.py                 # All env vars in one place
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx              # Main copilot interface
│   │   └── api/
│   │       └── copilotkit/
│   │           └── route.ts      # CopilotKit runtime + ADK bridge
│   ├── components/
│   │   ├── DesignCopilot.tsx     # Main panel with CopilotKit chat
│   │   ├── AgentTimeline.tsx     # Live AG-UI event feed
│   │   ├── CritiqueView.tsx      # Structured critique renderer
│   │   ├── SpecDownload.tsx      # Spec JSON download + preview
│   │   └── FeedbackBar.tsx       # 👍/👎 per review
│   ├── lib/
│   │   └── agui-events.ts        # AG-UI event type definitions
│   ├── package.json
│   └── next.config.ts
├── CLAUDE.md
├── IMPLEMENTATION_PLAN.md
└── .env.example
```

---

## Environment Variables

Create `.env.example` at root and `.env` locally (never commit `.env`):

```bash
# Google Cloud
GOOGLE_API_KEY=                    # Gemini API key (for local dev)
GOOGLE_CLOUD_PROJECT=              # GCP project ID
GOOGLE_APPLICATION_CREDENTIALS=   # Path to service account JSON (local only)

# Firestore
FIRESTORE_DATABASE=                # Default: "(default)"
FIRESTORE_COLLECTION_KNOWLEDGE=ux_knowledge
FIRESTORE_COLLECTION_SESSIONS=agent_sessions
FIRESTORE_COLLECTION_TRAJECTORIES=trajectories

# GCS
GCS_BUCKET_SCREENSHOTS=design-ops-screenshots

# Figma
FIGMA_ACCESS_TOKEN=                # Personal Access Token from Figma settings

# CopilotKit
COPILOTKIT_API_KEY=                # From copilotkit.ai

# GitHub (optional — for Retriever to read team design system repos)
GITHUB_TOKEN=                      # PAT with repo:read scope

# Team docs mount path (for filesystem MCP)
TEAM_DOCS_PATH=./backend/knowledge/team_docs   # local; use GCS FUSE path in Cloud Run

# 21st.dev (for Magic MCP)
MAGIC_API_KEY=

# Backend URL (used by frontend)
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000   # Cloud Run URL in prod
```

---

## Phase 0 — Project Scaffold

**Goal**: Runnable skeleton, all dependencies installed, dev servers start cleanly.

### 0.1 Backend scaffold

```bash
cd design-ops-navigator/backend
uv init --python 3.12      # Hard requirement: ADK tested on 3.9–3.12; Cloud Run base image is 3.12
uv add google-adk google-generativeai google-cloud-firestore \
        google-cloud-storage fastapi uvicorn python-dotenv httpx \
        pydantic-settings beautifulsoup4 numpy
uv add --dev pytest pytest-asyncio ruff
```

`pyproject.toml` must pin: `python = ">=3.12,<3.13"` (Cloud Run base image compatibility).

> **Python version lock**: Always use the `.venv` created here (`uv venv --python 3.12`), not the system 3.14. The two are incompatible for Cloud Run deployment.

`config.py`:
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    google_api_key: str
    google_cloud_project: str
    firestore_collection_knowledge: str = "ux_knowledge"
    firestore_collection_sessions: str = "agent_sessions"
    firestore_collection_trajectories: str = "trajectories"
    gcs_bucket_screenshots: str = "design-ops-screenshots"
    figma_access_token: str
    copilotkit_api_key: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
```

### 0.2 Frontend scaffold

```bash
cd design-ops-navigator/frontend
npx create-next-app@latest . --typescript --tailwind --app --src-dir=no
npm install @copilotkit/react-core @copilotkit/react-ui @copilotkit/runtime
npm install lucide-react
```

### 0.3 Local dev check

- `cd backend && uv run uvicorn server:app --reload` → 200 on `GET /health`
- `cd frontend && npm run dev` → Next.js loads on port 3000

---

## Phase 1 — Knowledge Base Ingestion

**Goal**: Pre-load Tier 1 UX knowledge into Firestore with vector embeddings. This is the foundation — knowledge quality = output quality.

### 1.1 Write source documents

In `backend/knowledge/sources/`, create markdown files for each knowledge source. Format each chunk with frontmatter:

```markdown
---
source: "WCAG 2.2"
category: "accessibility"
rule_id: "1.4.3"
severity_applies: ["critical", "high"]
---
## Contrast Minimum (Level AA)
The visual presentation of text and images of text has a contrast ratio of at least 4.5:1...
```

Keep each file focused on one domain. The ingest pipeline will chunk them.

### 1.2 Embedding pipeline (`knowledge/embeddings.py`)

```python
import google.generativeai as genai
from google.cloud import firestore
import hashlib

genai.configure(api_key=settings.google_api_key)

def embed_text(text: str) -> list[float]:
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=text,
        task_type="RETRIEVAL_DOCUMENT"
    )
    return result["embedding"]

def chunk_document(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    # Token-aware chunking: split on paragraphs first, then by size
    # Return list of chunk strings
    ...
```

### 1.3 Ingest script (`knowledge/ingest.py`)

```python
def ingest_document(filepath: str, tier: int = 1):
    """
    1. Parse frontmatter metadata
    2. Chunk document (800 tokens, 100 overlap)
    3. Embed each chunk with text-embedding-004
    4. Write to Firestore with vector field
    5. Skip if doc_id already exists (idempotent)
    """
    db = firestore.Client(project=settings.google_cloud_project)
    collection = db.collection(settings.firestore_collection_knowledge)

    for chunk in chunks:
        doc_id = hashlib.sha256(chunk.encode()).hexdigest()[:16]
        embedding = embed_text(chunk)

        doc_ref = collection.document(doc_id)
        if doc_ref.get().exists:
            continue  # idempotent

        doc_ref.set({
            "text": chunk,
            "embedding": firestore.VectorValue(embedding),  # Firestore native vector
            "metadata": {...},  # frontmatter + filepath + tier
            "tier": tier,
            "ingested_at": firestore.SERVER_TIMESTAMP
        })
```

Run: `uv run python -m knowledge.ingest` — must complete without errors before Phase 2.

### 1.4 Create Firestore vector index

In Firestore console (or via `gcloud`):

```bash
gcloud firestore indexes composite create \
  --collection-group=ux_knowledge \
  --field-config field-path=embedding,vector-config='{"dimension":768,"flat":{}}' \
  --project=$GOOGLE_CLOUD_PROJECT
```

Dimension is 768 for `text-embedding-004`.

### 1.5 Verify retrieval

Quick sanity test before building agents:
```python
# Test: embed a query, run vector search, print top 3 results
def test_retrieval(query: str, top_k: int = 5) -> list[dict]:
    query_embedding = genai.embed_content(
        model="models/text-embedding-004",
        content=query,
        task_type="RETRIEVAL_QUERY"
    )["embedding"]

    results = db.collection("ux_knowledge").find_nearest(
        vector_field="embedding",
        query_vector=firestore.VectorValue(query_embedding),
        distance_measure=firestore.DistanceMeasure.COSINE,
        limit=top_k
    ).get()

    return [{"text": r.get("text"), "source": r.get("metadata", {}).get("source")}
            for r in results]
```

---

## Phase 2 — ADK Tools

**Goal**: All tools are standalone, testable functions wrapped in ADK `FunctionTool`. No agent logic yet.

### 2.0 Required helper implementations (specify before using)

These are referenced across multiple phases. Implement them first in `tools/helpers.py`:

```python
import base64
from google.cloud import storage
from google.cloud import firestore as fs
import google.generativeai as genai
import numpy as np
from config import settings

# ── GCS ──────────────────────────────────────────────────────────────────────

def upload_to_gcs(png_bytes: bytes, file_key: str, node_id: str) -> str:
    """Upload PNG bytes to GCS. Returns gs:// URI."""
    client = storage.Client(project=settings.google_cloud_project)
    bucket = client.bucket(settings.gcs_bucket_screenshots)
    blob_name = f"{file_key}/{node_id.replace(':', '-')}.png"
    blob = bucket.blob(blob_name)
    blob.upload_from_string(png_bytes, content_type="image/png")
    return f"gs://{settings.gcs_bucket_screenshots}/{blob_name}"

def download_from_gcs(gcs_uri: str) -> bytes:
    """Download file from gs:// URI. Returns raw bytes."""
    client = storage.Client(project=settings.google_cloud_project)
    bucket_name, blob_name = gcs_uri[5:].split("/", 1)
    return client.bucket(bucket_name).blob(blob_name).download_as_bytes()

def image_to_base64(png_bytes: bytes) -> str:
    return base64.b64encode(png_bytes).decode("utf-8")

# ── Embeddings ────────────────────────────────────────────────────────────────

def embed_query(text: str) -> list[float]:
    """Embed a search query (task_type=RETRIEVAL_QUERY)."""
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=text,
        task_type="RETRIEVAL_QUERY"
    )
    return result["embedding"]

# ── MMR Reranking ─────────────────────────────────────────────────────────────

def _mmr_rerank(
    docs: list,
    query_embedding: list[float],
    top_k: int,
    lambda_: float = 0.5
) -> list[dict]:
    """
    Maximal Marginal Relevance reranking.
    Balances relevance to query vs. diversity between results.
    lambda_=1.0 → pure relevance, lambda_=0.0 → pure diversity.
    """
    if not docs:
        return []

    q = np.array(query_embedding)
    doc_vecs = [np.array(d.get("embedding", [0] * len(q))) for d in docs]

    selected_indices = []
    remaining = list(range(len(docs)))

    while len(selected_indices) < top_k and remaining:
        mmr_scores = []
        for i in remaining:
            relevance = float(np.dot(q, doc_vecs[i]) /
                              (np.linalg.norm(q) * np.linalg.norm(doc_vecs[i]) + 1e-9))
            if not selected_indices:
                redundancy = 0.0
            else:
                sims = [float(np.dot(doc_vecs[i], doc_vecs[j]) /
                              (np.linalg.norm(doc_vecs[i]) * np.linalg.norm(doc_vecs[j]) + 1e-9))
                        for j in selected_indices]
                redundancy = max(sims)
            mmr_scores.append(lambda_ * relevance - (1 - lambda_) * redundancy)
        best = remaining[int(np.argmax(mmr_scores))]
        selected_indices.append(best)
        remaining.remove(best)

    return [_doc_to_dict(docs[i]) for i in selected_indices]

def _doc_to_dict(doc) -> dict:
    """Convert Firestore DocumentSnapshot to plain dict."""
    data = doc.to_dict()
    return {
        "text": data.get("text", ""),
        "source": data.get("metadata", {}).get("source", ""),
        "rule_id": data.get("metadata", {}).get("rule_id", ""),
        "category": data.get("metadata", {}).get("category", ""),
        "tier": data.get("tier", 1),
        "embedding": data.get("embedding", []),   # needed for MMR
    }

# ── Figma node condensing ─────────────────────────────────────────────────────

def _extract_design_context(figma_nodes_response: dict) -> dict:
    """
    Condense raw Figma /files/{key}/nodes JSON into a concise context object.
    Extracts: component names, text content, color fills, layout type.
    Strips raw coordinate data — the Critic gets semantics, not pixel positions.
    """
    nodes = figma_nodes_response.get("nodes", {})
    result = {"components": [], "text_content": [], "color_fills": [], "layout": "unknown"}
    for node_id, node_data in nodes.items():
        doc = node_data.get("document", {})
        result["components"].append(doc.get("name", ""))
        _walk_node(doc, result)
    return result

def _walk_node(node: dict, result: dict):
    """Recursive DFS to extract text and color data."""
    if node.get("type") == "TEXT":
        result["text_content"].append(node.get("characters", ""))
    fills = node.get("fills", [])
    for fill in fills:
        if fill.get("type") == "SOLID" and "color" in fill:
            c = fill["color"]
            hex_color = "#{:02x}{:02x}{:02x}".format(
                int(c["r"] * 255), int(c["g"] * 255), int(c["b"] * 255)
            )
            result["color_fills"].append(hex_color)
    for child in node.get("children", []):
        _walk_node(child, result)
```

### 2.1 Figma tools (`tools/figma_tools.py`)

```python
import httpx
from google.adk.tools import FunctionTool

FIGMA_BASE = "https://api.figma.com/v1"

async def get_figma_frame_image(file_key: str, node_id: str) -> dict:
    """
    Fetch a Figma frame as PNG via REST API.

    Args:
        file_key: Figma file key (from URL: figma.com/design/{file_key}/...)
        node_id: Node ID (from URL: ?node-id=1-2, convert - to :)

    Returns:
        dict with 'image_url' (GCS path after upload) and 'node_id'
    """
    headers = {"X-Figma-Token": settings.figma_access_token}

    # 1. Get render URL from Figma
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{FIGMA_BASE}/images/{file_key}",
            params={"ids": node_id, "format": "png", "scale": 2},
            headers=headers
        )
    resp.raise_for_status()
    image_url = resp.json()["images"][node_id]

    # 2. Download PNG
    async with httpx.AsyncClient() as client:
        img_resp = await client.get(image_url)
    png_bytes = img_resp.content

    # 3. Upload to GCS
    gcs_path = upload_to_gcs(png_bytes, file_key, node_id)

    return {"image_url": gcs_path, "node_id": node_id, "file_key": file_key}


async def get_figma_file_context(file_key: str, node_id: str) -> dict:
    """
    Fetch structured node data: component names, variants, styles, tokens.
    Returns a condensed JSON with design system context for the given frame.
    """
    headers = {"X-Figma-Token": settings.figma_access_token}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{FIGMA_BASE}/files/{file_key}/nodes",
            params={"ids": node_id, "depth": 3},
            headers=headers
        )
    resp.raise_for_status()
    # Extract: component names, text content, color styles, layout
    return _extract_design_context(resp.json())
```

### 2.2 RAG tools (`tools/rag_tools.py`)

```python
async def search_knowledge_base(query: str, top_k: int = 5, tier: int | None = None) -> list[dict]:
    """
    Search UX knowledge base using Firestore vector similarity.

    Args:
        query: Natural language search query
        top_k: Number of results to return (default 5)
        tier: 1 = universal UX knowledge, 2 = team-specific, None = both

    Returns:
        List of dicts: {text, source, rule_id, category, score}

    Apply MMR reranking to ensure result diversity — avoid 5 WCAG chunks
    when we also have Gestalt and Nielsen results for the same topic.
    """
    query_embedding = embed_query(query)

    query_ref = db.collection("ux_knowledge")
    if tier is not None:
        query_ref = query_ref.where("tier", "==", tier)

    raw_results = query_ref.find_nearest(
        vector_field="embedding",
        query_vector=firestore.VectorValue(query_embedding),
        distance_measure=firestore.DistanceMeasure.COSINE,
        limit=top_k * 3  # over-fetch for MMR
    ).get()

    # Apply MMR reranking
    return _mmr_rerank(raw_results, query_embedding, top_k, lambda_=0.5)


async def index_team_knowledge(text: str, metadata: dict) -> str:
    """
    Index a new team-specific document (design system notes, past critiques).
    Returns the document ID.
    Tier 2 knowledge — stored alongside Tier 1 but queryable separately.
    """
    ...
```

### 2.3 Spec tools (`tools/spec_tools.py`)

```python
def generate_spec_json(critique_items: list[dict], figma_context: dict) -> dict:
    """
    Generate Figma-ready spec JSON from critique items.

    Output schema:
    {
      "spec_version": "1.0",
      "file_key": str,
      "node_id": str,
      "changes": [
        {
          "element": str,        # Component name or CSS selector
          "issue": str,          # What's wrong
          "rule": str,           # WCAG 1.4.3 / Nielsen #4 / etc.
          "fix": str,            # Specific actionable change
          "severity": "critical|high|medium|low",
          "copy_replacement": str | null,
          "color_change": {"from": str, "to": str} | null
        }
      ],
      "generated_at": str
    }
    """
    ...

def generate_test_script(spec: dict) -> str:
    """
    Generate a usability test script or QA checklist from the spec.
    Returns markdown string.
    """
    ...
```

### 2.4 WCAG contrast tool — deterministic (`tools/wcag_tools.py`)

```python
from google.adk.tools import FunctionTool

def check_wcag_contrast(foreground_hex: str, background_hex: str) -> dict:
    """
    Calculate WCAG 2.2 contrast ratio between two colors. Pure math, no LLM.

    Args:
        foreground_hex: Hex color of text/icon (e.g. "#A0A0A0")
        background_hex: Hex color of background (e.g. "#FFFFFF")

    Returns:
        {
          "ratio": float,                  # e.g. 3.82
          "ratio_display": "3.82:1",
          "aa_normal_text": bool,          # >= 4.5:1
          "aa_large_text": bool,           # >= 3:1
          "aaa_normal_text": bool,         # >= 7:1
          "aaa_large_text": bool,          # >= 4.5:1
          "verdict": "PASS AA" | "FAIL AA",
          "fix_suggestion": str            # e.g. "Darken to #767676 for 4.54:1"
        }
    """
    def _relative_luminance(hex_color: str) -> float:
        hex_color = hex_color.lstrip("#")
        r, g, b = [int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4)]
        def _linearize(c):
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)

    l1 = _relative_luminance(foreground_hex)
    l2 = _relative_luminance(background_hex)
    lighter, darker = max(l1, l2), min(l1, l2)
    ratio = (lighter + 0.05) / (darker + 0.05)

    aa_pass = ratio >= 4.5
    return {
        "ratio": round(ratio, 2),
        "ratio_display": f"{ratio:.2f}:1",
        "aa_normal_text": aa_pass,
        "aa_large_text": ratio >= 3.0,
        "aaa_normal_text": ratio >= 7.0,
        "aaa_large_text": ratio >= 4.5,
        "verdict": "PASS AA" if aa_pass else "FAIL AA",
        "fix_suggestion": "" if aa_pass else _suggest_darker_hex(foreground_hex, background_hex)
    }
```

### 2.5 Web content fetcher (`tools/web_tools.py`)

```python
import httpx
from bs4 import BeautifulSoup

async def fetch_web_content(url: str, max_chars: int = 3000) -> dict:
    """
    Fetch and extract text from a web page for Retriever to read live docs.

    Use cases:
    - WCAG 2.2 success criteria pages (w3.org)
    - Nielsen Norman Group articles (nngroup.com)
    - Material Design / Apple HIG docs

    Returns: {"url": str, "title": str, "content": str (truncated)}
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
        resp = await client.get(url, headers={"User-Agent": "DesignOpsNavigator/1.0"})
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    # Remove nav, footer, scripts
    for tag in soup(["nav", "footer", "script", "style", "aside"]):
        tag.decompose()

    title = soup.title.string if soup.title else url
    text = soup.get_text(separator="\n", strip=True)[:max_chars]

    return {"url": url, "title": title, "content": text}
```

Add to `pyproject.toml`: already in the Phase 0 `uv add` command.

Also add `_suggest_darker_hex` helper to `tools/wcag_tools.py`:
```python
def _suggest_darker_hex(fg_hex: str, bg_hex: str, target_ratio: float = 4.5) -> str:
    """Binary search for darkest fg that achieves target_ratio on given bg."""
    fg_hex = fg_hex.lstrip("#")
    r, g, b = [int(fg_hex[i:i+2], 16) for i in (0, 2, 4)]
    # Step down in increments of 5 until we hit the target ratio
    for step in range(0, 256, 5):
        nr, ng, nb = max(0, r - step), max(0, g - step), max(0, b - step)
        candidate = f"#{nr:02x}{ng:02x}{nb:02x}"
        result = check_wcag_contrast(candidate, bg_hex)
        if result["ratio"] >= target_ratio:
            return f"Change to {candidate} (achieves {result['ratio_display']})"
    return f"No simple darkening achieves {target_ratio}:1 — consider a different color"
```

### 2.6 MCPToolset factories (`tools/mcp_tools.py`)

ADK connects to MCP servers via `MCPToolset`. Each factory returns an async context manager that the agent uses to access MCP tools.

```python
from google.adk.tools.mcp_tool import MCPToolset, StdioServerParameters, SseServerParams
from config import settings

def get_figma_mcp_tools() -> MCPToolset:
    """
    Official Figma MCP server — exposes richer structured data than REST alone.
    Tools available: get_figma_data (node tree, variants, tokens, resolved styles).
    Used by: Critic agent for design system context.
    """
    return MCPToolset(
        connection_params=StdioServerParameters(
            command="npx",
            args=["-y", "@figma/mcp"],
            env={"FIGMA_ACCESS_TOKEN": settings.figma_access_token}
        )
        # No tool_filter — include all Figma MCP tools
    )

def get_filesystem_mcp_tools(docs_path: str | None = None) -> MCPToolset:
    """
    Filesystem MCP — lets Retriever read team design docs directly.
    Scoped to TEAM_DOCS_PATH only. In Cloud Run, mount GCS bucket via FUSE.
    Used by: Retriever agent for Tier 2 knowledge (design system docs, past specs).
    """
    path = docs_path or settings.team_docs_path
    return MCPToolset(
        connection_params=StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", path]
        )
    )
```

**MCPToolset lifecycle — per-request, not per-app**

MCPToolsets in ADK are async context managers that manage a subprocess (the MCP server). The subprocess connection is only valid inside the `async with` block — you cannot store it in `app.state` across requests.

Use a per-request context manager pattern via a factory function:

```python
# In agents/orchestrator.py — build_orchestrator() factory
from contextlib import asynccontextmanager
from tools.mcp_tools import get_figma_mcp_tools, get_filesystem_mcp_tools

@asynccontextmanager
async def build_orchestrator():
    """
    Builds the full agent graph with MCP servers started for the duration
    of a single request. Call as: async with build_orchestrator() as orch: ...
    """
    async with get_figma_mcp_tools() as figma_tools, \
               get_filesystem_mcp_tools() as fs_tools:

        figma_fetcher = Agent(
            name="figma_fetcher",
            ...,
            tools=[FunctionTool(get_figma_frame_image),
                   FunctionTool(get_figma_file_context),
                   figma_tools]          # MCPToolset live for this request
        )
        retriever = Agent(
            name="retriever",
            ...,
            tools=[google_search,
                   FunctionTool(search_knowledge_base),
                   FunctionTool(index_team_knowledge),
                   FunctionTool(fetch_web_content),
                   fs_tools]             # MCPToolset live for this request
        )
        # ... build critic, evaluator, orchestrator
        yield orchestrator_agent

# In server.py — use per request
@app.post("/analyze")
async def analyze(request: Request):
    async with build_orchestrator() as orchestrator:
        runner = Runner(agent=orchestrator, ...)
        # ... run pipeline
```

**Add to `pyproject.toml`**: No extra Python packages needed — MCPToolset is bundled with `google-adk`. The MCP servers themselves run as Node.js processes via `npx`.

### 2.7 ADK built-in `google_search`

```python
from google.adk.tools import google_search

# Use directly in agent tools list — no wrapper needed
retriever_agent = Agent(
    ...,
    tools=[
        google_search,                      # ADK built-in, grounded with Google Search API
        FunctionTool(search_knowledge_base),
        FunctionTool(index_team_knowledge),
        FunctionTool(fetch_web_content),
        fs_mcp_tools,                       # filesystem MCPToolset
    ]
)

evaluator_agent = Agent(
    ...,
    tools=[google_search]   # For verifying rule citations exist — e.g. check a WCAG rule ID
)
```

`google_search` requires the `GOOGLE_API_KEY` to have Search API enabled, or use Vertex AI grounding. Check ADK docs for the exact quota requirements.

---

## Phase 3 — ADK Agents

**Goal**: Four working agents that can be unit-tested independently.

### 3.1 Retriever Agent (`agents/retriever.py`)

```python
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from tools.rag_tools import search_knowledge_base, index_team_knowledge

RETRIEVER_SYSTEM_PROMPT = """
You are a UX knowledge retrieval specialist. Your job is to find the most
relevant design principles, accessibility rules, and patterns for a given
design critique request.

Behavior:
1. First broad search: search for the general topic (e.g., "onboarding UX patterns")
2. Evaluate results quality — if they are generic, do a refinement search
   (e.g., "B2B SaaS onboarding password field trust indicators")
3. Return exactly the snippets that will help the Critic agent ground its feedback

ALWAYS include the source and rule_id for each returned snippet.
NEVER fabricate rules or cite sources not in your search results.
Return results as a JSON array.
"""

retriever_agent = Agent(
    name="retriever",
    model="gemini-2.0-flash",
    description="Retrieves relevant UX knowledge for design critique grounding.",
    instruction=RETRIEVER_SYSTEM_PROMPT,
    tools=[
        google_search,                         # ADK built-in — live UX research
        FunctionTool(search_knowledge_base),   # Firestore vector RAG
        FunctionTool(index_team_knowledge),    # Tier 2 doc indexing
        FunctionTool(fetch_web_content),       # Scrape WCAG/NNg pages on demand
        # fs_mcp_tools added at request time from app.state
    ]
)
```

### 3.2 Critic Agent (`agents/critic.py`)

```python
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from tools.figma_tools import get_figma_frame_image, get_figma_file_context
from tools.spec_tools import generate_spec_json, generate_test_script
import google.generativeai as genai

CRITIC_SYSTEM_PROMPT = """
You are a senior UX critic. You analyze design screens against proven UX principles.

Two-pass analysis process:
PASS 1 — DESCRIBE: What do you see? Identify screen type, key UI elements,
          copy, hierarchy, interactive components, and visual flow.

PASS 2 — EVALUATE: For each element in PASS 1, evaluate against the provided
          knowledge snippets. Every critique MUST cite a specific rule from
          the retrieved knowledge (format: "[Source: WCAG 1.4.3]").

Output format — return ONLY valid JSON, no prose:
{
  "screen_type": str,
  "elements_identified": [str],
  "critique_items": [
    {
      "element": str,
      "issue": str,
      "rule_citation": str,      // "[Source: WCAG 1.4.3]" format
      "severity": "critical|high|medium|low",
      "fix": str,                // Specific, actionable (hex codes, exact copy)
      "copy_replacement": str | null,
      "color_change": {"from": str, "to": str} | null
    }
  ]
}

NEVER add critique items without a rule citation from the provided knowledge.
"""

async def analyze_visual_design(
    image_gcs_path: str,
    retrieved_knowledge: list[dict],
    figma_context: dict
) -> dict:
    """
    Core multimodal analysis: pass PNG + knowledge snippets to Gemini.
    Returns structured critique dict.
    """
    model = genai.GenerativeModel("gemini-2.0-flash")

    # Download image from GCS
    image_bytes = download_from_gcs(image_gcs_path)

    knowledge_block = "\n\n".join([
        f"[{s['source']} / {s.get('rule_id','')}]: {s['text']}"
        for s in retrieved_knowledge
    ])

    prompt = f"""
    Design context (from Figma): {figma_context}

    Retrieved UX knowledge (use these to ground your critique):
    {knowledge_block}

    {CRITIC_SYSTEM_PROMPT}
    """

    response = model.generate_content(
        [prompt, {"mime_type": "image/png", "data": image_bytes}],
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json"
        )
    )
    return json.loads(response.text)


critic_agent = Agent(
    name="critic",
    model="gemini-2.0-flash",
    description="Multimodal UX critic that analyzes Figma frames against retrieved knowledge.",
    instruction=CRITIC_SYSTEM_PROMPT,
    tools=[
        FunctionTool(get_figma_frame_image),   # Figma REST → PNG → GCS
        FunctionTool(get_figma_file_context),  # Figma REST → node tree (condensed)
        FunctionTool(check_wcag_contrast),     # Deterministic contrast math
        FunctionTool(analyze_visual_design),   # Gemini multimodal two-pass
        FunctionTool(generate_spec_json),      # Structured spec output
        FunctionTool(generate_test_script),    # Usability test / QA checklist
        # figma_mcp_tools added at request time from app.state (richer variants/tokens)
    ]
)
```

### 3.3 Evaluator Agent (`agents/evaluator.py`)

```python
EVALUATOR_SYSTEM_PROMPT = """
You are a UX critique quality judge. You receive critique items from the Critic
agent and evaluate each one using this rubric:

RUBRIC (score each 1-5):
1. Grounding: Is there a valid rule citation from the knowledge base? (1=none, 5=precise WCAG/heuristic ID)
2. Specificity: Is the fix actionable? (1=vague "improve this", 5=exact hex/copy/measurement)
3. Universality: Is this a widely-accepted UX principle or just subjective preference? (1=opinion, 5=established standard)
4. Actionability: Can a designer act on this in under 30 minutes without external help? (1=no, 5=yes)

FILTER RULES:
- DROP any item with Grounding score < 3 (ungrounded critique is hallucination)
- DROP any item with Specificity score < 2
- KEEP all Critical and High severity items even if other scores are imperfect
- ANNOTATE each kept item with its rubric scores

Return ONLY valid JSON:
{
  "kept_items": [{...original_item, "rubric": {"grounding": N, "specificity": N, ...}}],
  "dropped_items": [{...item, "drop_reason": str}],
  "overall_quality_score": float,  // 0-1, weighted average
  "grounded_suggestion_rate": float  // kept_with_citation / total
}
"""

evaluator_agent = Agent(
    name="evaluator",
    model="gemini-2.0-flash",
    description="Autorater that checks critique grounding, specificity, and consistency.",
    instruction=EVALUATOR_SYSTEM_PROMPT,
    tools=[
        google_search,   # Verify rule citations exist (e.g. "WCAG 2.2 SC 1.4.3" → confirm wording)
    ]
)
```

### 3.4 Orchestrator Agent (`agents/orchestrator.py`)

The Orchestrator is the supervisor. It:
1. Parses the user's intent and Figma URL
2. Runs Retriever + Critic in **parallel** (they are independent)
3. Passes their outputs to Evaluator
4. Synthesizes the final response
5. Emits AG-UI SSE events at each stage

```python
from google.adk.agents import Agent, ParallelAgent
from google.adk.tools import FunctionTool, google_search
from google.adk.tools.mcp_tool import MCPToolset
from agents.retriever import retriever_agent
from agents.critic import critic_agent
from agents.evaluator import evaluator_agent

ORCHESTRATOR_SYSTEM_PROMPT = """
You are the Design Ops Navigator orchestrator. You coordinate a team of specialized
AI agents to deliver expert UX critique.

WORKFLOW (always follow this order):
1. Parse the user's Figma URL → extract file_key and node_id
   (URL format: figma.com/design/{file_key}/...?node-id={node-id})
   Convert node-id from "1-2" format to "1:2" format.
2. Understand their question/concern (or default to "full UX review")
3. Emit: {"event": "agent_routing", "message": "Routing to Retriever and Critic..."}
4. Run Retriever and Critic IN PARALLEL:
   - Retriever: search for relevant UX knowledge based on the design context
   - Critic: load the Figma frame and do two-pass visual analysis
5. Emit: {"event": "knowledge_retrieved", "count": N, "sources": [...]}
6. Emit: {"event": "figma_frame_loaded", "node_id": "..."}
7. Pass both outputs to Evaluator
8. Emit: {"event": "critique_generated", "items_count": N}
9. After Evaluator: emit {"event": "evaluation_complete", "kept": N, "dropped": N, "quality_score": X}
10. Synthesize final response:
    - Summary of the screen and main issues
    - Numbered critique items (kept items only) with severity badges
    - Spec JSON ready for download
    - Optional test script
11. Emit: {"event": "response_ready"}

CRITICAL: Use the forward_message pattern for final responses.
Do NOT paraphrase sub-agent outputs — pass them through with fidelity.
Only synthesize the top-level summary.
"""

def parse_figma_url(url: str) -> dict:
    """Extract file_key and node_id from a Figma URL."""
    import re
    match = re.search(r"figma\.com/design/([^/]+)", url)
    file_key = match.group(1) if match else None
    node_match = re.search(r"node-id=([^&]+)", url)
    node_id = node_match.group(1).replace("-", ":") if node_match else None
    return {"file_key": file_key, "node_id": node_id}

# Parallel step: Retriever + Critic run simultaneously
parallel_analyze = ParallelAgent(
    name="parallel_analyze",
    sub_agents=[retriever_agent, critic_agent]
)

orchestrator = Agent(
    name="orchestrator",
    model="gemini-2.0-flash",
    description="Design Ops Navigator orchestrator. Coordinates UX critique pipeline.",
    instruction=ORCHESTRATOR_SYSTEM_PROMPT,
    sub_agents=[parallel_analyze, evaluator_agent],
    tools=[FunctionTool(parse_figma_url)]
)
```

---

## Phase 4 — FastAPI Server + ADK Runner

**Goal**: HTTP server that accepts requests, runs the 4-agent pipeline, streams AG-UI events via SSE.

### 4.1 Server (`server.py`)

```python
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from agents.orchestrator import build_orchestrator   # factory function, not singleton
from agentops.logger import TrajectoryLogger
import asyncio, json
from uuid import uuid4

# NOTE: InMemorySessionService does not survive Cloud Run restarts/scale-out.
# For production, replace with DatabaseSessionService backed by Firestore.
# For hackathon demo with a single instance, InMemorySessionService is fine.
app = FastAPI()
session_service = InMemorySessionService()

# CORS — required for Next.js frontend on Vercel to reach this server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # tighten to Vercel domain before production
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok", "adk_version": "1.27.1"}

@app.post("/analyze")
async def analyze(request: Request):
    body = await request.json()
    user_message = body["message"]      # e.g. "Analyze this: figma.com/design/..."
    session_id = body.get("session_id", str(uuid4()))

    runner = Runner(
        agent=orchestrator,
        app_name="design-ops-navigator",
        session_service=session_service
    )

    session = await session_service.create_session(
        app_name="design-ops-navigator",
        user_id=body.get("user_id", "anonymous"),
        session_id=session_id
    )

    logger = TrajectoryLogger(session_id=session_id)

    async def event_stream():
        async for event in runner.run_async(
            user_id=session.user_id,
            session_id=session_id,
            new_message=Content(parts=[Part(text=user_message)])
        ):
            # Log every event for AgentOps
            await logger.log_event(event)

            # Translate ADK events to AG-UI SSE format
            if event.is_final_response():
                payload = {
                    "event": "response_ready",
                    "content": event.content.parts[0].text
                }
            elif event.content and event.content.parts:
                # Pass through all streaming content
                payload = {
                    "event": "token",
                    "content": event.content.parts[0].text
                }
            else:
                continue

            yield f"data: {json.dumps(payload)}\n\n"

        # Log session completion metrics — pass Evaluator output parsed from session state
        evaluator_output = runner.session_service.get_session(
            app_name="design-ops-navigator",
            user_id=body.get("user_id", "anonymous"),
            session_id=session_id
        ).state.get("evaluator_output")
        await logger.finalize(evaluator_output=evaluator_output)

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.post("/feedback")
async def feedback(request: Request):
    """Receive 👍/👎 feedback from frontend."""
    body = await request.json()
    # Store in Firestore trajectories collection
    ...
```

---

## Phase 5 — AgentOps Layer

**Goal**: Real trajectory logging and the 4 metrics from the initial plan.

### 5.1 Trajectory Logger (`agentops/logger.py`)

```python
from google.cloud import firestore
from datetime import datetime

class TrajectoryLogger:
    """
    Logs agent execution trajectory to Firestore.
    One document per session with subcollection of events.
    """
    def __init__(self, session_id: str):
        self.db = firestore.AsyncClient()
        self.session_id = session_id
        self.start_time = datetime.utcnow()
        self.event_count = 0
        self.tool_calls = []
        self.grounded_items = 0
        self.total_items = 0

    async def log_event(self, event):
        """Log each ADK event with timestamp and type."""
        self.event_count += 1
        doc = {
            "session_id": self.session_id,
            "event_index": self.event_count,
            "event_type": event.__class__.__name__,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "agent_name": getattr(event, 'author', 'unknown'),
        }
        if hasattr(event, 'tool_calls'):
            self.tool_calls.extend(event.tool_calls)
            doc["tool_calls"] = [t.function.name for t in event.tool_calls]

        await self.db.collection("trajectories").document(self.session_id)\
            .collection("events").add(doc)

    async def finalize(self, evaluator_output: dict | None = None):
        """
        Write session summary metrics to Firestore.
        Call at end of every /analyze request, passing the Evaluator's output dict.
        evaluator_output keys: kept_items, dropped_items, grounded_suggestion_rate, overall_quality_score
        """
        duration_ms = (datetime.utcnow() - self.start_time).total_seconds() * 1000

        # Derive grounding rate from Evaluator output (authoritative source)
        grounded_rate = (evaluator_output or {}).get("grounded_suggestion_rate", 0.0)
        kept = len((evaluator_output or {}).get("kept_items", []))
        goal_complete = kept > 0 and duration_ms < 60_000

        await self.db.collection("trajectories").document(self.session_id).set({
            "session_id": self.session_id,
            "started_at": self.start_time.isoformat(),
            "duration_ms": duration_ms,
            "total_events": self.event_count,
            "total_tool_calls": len(self.tool_calls),   # raw count per session (target: < 8)
            "tool_names_called": list({t for t in self.tool_calls}),
            "grounded_suggestion_rate": grounded_rate,
            "goal_complete": goal_complete,              # full critique in < 60s
            "kept_critique_items": kept,
            "status": "complete"
        }, merge=True)
```

### 5.2 Metrics (`agentops/metrics.py`)

Track these 4 metrics per session (query from Firestore for dashboard):

```python
METRICS = {
    "goal_completion_rate": "% of sessions producing a full critique within 60s",
    "grounded_suggestion_rate": "% of critique items with at least one rule citation",
    "tool_efficiency": "avg tool calls per full review (target: < 8)",
    "user_feedback_score": "👍 / (👍 + 👎) per session",
}
```

---

## Phase 6 — Frontend (Next.js 15 + CopilotKit)

**Goal**: Working UI with live agent timeline, critique view, spec download, and feedback.

### 6.1 CopilotKit runtime bridge (`app/api/copilotkit/route.ts`)

> **Integration note**: CopilotKit's `remoteActions` expects its own HTTP Action protocol (OpenAI function-calling compatible), not ADK's raw SSE stream. The ADK backend must be wrapped in a CopilotKit Action that the frontend can invoke. Two valid approaches:

**Option A (recommended for hackathon)**: Use CopilotKit's `useCopilotAction` on the frontend to call the ADK backend directly, bypassing the CopilotKit runtime for the heavy lifting. CopilotKit handles the chat UI; the action calls ADK directly.

```typescript
// app/api/copilotkit/route.ts — minimal runtime for chat UI only
import {
  CopilotRuntime,
  GoogleGenerativeAIAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { NextRequest } from "next/server";
import { GoogleGenerativeAI } from "@google/generative-ai";

const genai = new GoogleGenerativeAI(process.env.GOOGLE_API_KEY!);

const runtime = new CopilotRuntime({
  // No remoteActions — the frontend useCopilotAction hook calls ADK directly
});

export const POST = async (req: NextRequest) => {
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter: new GoogleGenerativeAIAdapter({ model: genai.getGenerativeModel({ model: "gemini-2.0-flash" }) }),
    req,
    endpoint: "/api/copilotkit",
  });
  return handleRequest(req);
};
```

```typescript
// In DesignCopilot.tsx — useCopilotAction hooks ADK backend
import { useCopilotAction, useCopilotReadable } from "@copilotkit/react-core";

useCopilotAction({
  name: "analyzeDesign",
  description: "Analyze a Figma design frame for UX issues",
  parameters: [
    { name: "figmaUrl", type: "string", description: "Figma URL with node-id" },
    { name: "question", type: "string", description: "What to focus on" },
  ],
  handler: async ({ figmaUrl, question }) => {
    // Call ADK backend SSE endpoint directly
    const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: `${figmaUrl} — ${question}` }),
    });
    // Parse SSE stream → update AgentTimeline events → update CritiqueView
    await readSSEStream(response, setAguiEvents, setCritique);
    return "Analysis complete — see the critique panel";
  },
});
```

**Option B**: Use CopilotKit's full `remoteEndpoint` pattern with a custom adapter that wraps ADK — more complex, implement only if Option A has chat UX gaps.

### 6.2 AG-UI Event Types (`lib/agui-events.ts`)

```typescript
export type AGUIEventType =
  | "agent_routing"
  | "knowledge_retrieved"
  | "figma_frame_loaded"
  | "critique_generated"
  | "evaluation_complete"
  | "response_ready"
  | "token";

export interface AGUIEvent {
  event: AGUIEventType;
  message?: string;
  count?: number;
  sources?: string[];
  node_id?: string;
  items_count?: number;
  kept?: number;
  dropped?: number;
  quality_score?: number;
  content?: string;
}
```

### 6.3 Main Page (`app/page.tsx`)

```typescript
"use client";
import { CopilotKit } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import { AgentTimeline } from "@/components/AgentTimeline";
import { CritiqueView } from "@/components/CritiqueView";
import { useState } from "react";

export default function Home() {
  const [aguiEvents, setAguiEvents] = useState<AGUIEvent[]>([]);
  const [critique, setCritique] = useState(null);

  return (
    <CopilotKit runtimeUrl="/api/copilotkit" publicApiKey={process.env.NEXT_PUBLIC_COPILOTKIT_KEY}>
      <div className="flex h-screen bg-gray-950 text-white">
        {/* Left: Chat + input */}
        <div className="w-[420px] border-r border-gray-800 flex flex-col">
          <header className="p-4 border-b border-gray-800">
            <h1 className="text-lg font-semibold">Design Ops Navigator</h1>
            <p className="text-xs text-gray-400">Paste a Figma URL to get started</p>
          </header>
          <CopilotChat
            instructions="Help the user analyze their Figma designs. When they provide a Figma URL, trigger the analyze action."
            className="flex-1"
          />
        </div>

        {/* Center: Live agent timeline */}
        <div className="w-[280px] border-r border-gray-800">
          <AgentTimeline events={aguiEvents} />
        </div>

        {/* Right: Critique results */}
        <div className="flex-1 overflow-auto">
          <CritiqueView critique={critique} />
        </div>
      </div>
    </CopilotKit>
  );
}
```

### 6.4 AgentTimeline Component (`components/AgentTimeline.tsx`)

```typescript
// Shows live AG-UI events as the agents work
// Each event type maps to a visual step with icon + label + timestamp
// Events animate in as they arrive via SSE
// Steps: Routing → Retrieval → Frame Load → Critique → Evaluation → Done
```

### 6.5 CritiqueView Component (`components/CritiqueView.tsx`)

```typescript
// Renders the structured critique JSON as cards
// Each card: severity badge (color-coded) | element | issue | rule citation | fix
// "Critical" = red, "High" = orange, "Medium" = yellow, "Low" = blue
// SpecDownload button at bottom
// FeedbackBar (👍/👎) after critique loads
```

---

## Phase 7 — Deployment

### 7.1 Backend — Docker + Cloud Run

`backend/Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev
COPY . .
EXPOSE 8080
CMD ["uv", "run", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
```

Deploy:
```bash
gcloud run deploy design-ops-backend \
  --source backend/ \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_API_KEY=$GOOGLE_API_KEY,FIGMA_ACCESS_TOKEN=$FIGMA_ACCESS_TOKEN \
  --memory 2Gi \
  --concurrency 80
```

Alternatively, use the ADK CLI if available:
```bash
adk deploy cloud_run \
  --project=$GOOGLE_CLOUD_PROJECT \
  --region=us-central1 \
  --service_name=design-ops-backend
```

### 7.2 Frontend — Vercel

```bash
cd frontend
npx vercel --prod
# Set env vars in Vercel dashboard:
# NEXT_PUBLIC_BACKEND_URL = Cloud Run URL
# NEXT_PUBLIC_COPILOTKIT_KEY = (if needed)
```

---

## Phase 8 — Demo Verification Checklist

Before recording the 4-minute demo video, verify the full happy path:

```
[ ] User pastes Figma URL + question into chat
[ ] AgentTimeline shows "agent_routing" event appear
[ ] "knowledge_retrieved" event shows N sources
[ ] "figma_frame_loaded" event shows node_id
[ ] "critique_generated" event appears
[ ] "evaluation_complete" shows kept/dropped counts
[ ] CritiqueView renders cards with severity badges
[ ] Each card has a rule citation (not fabricated)
[ ] Spec JSON downloads correctly
[ ] 👍/👎 feedback logs to Firestore
[ ] Trajectory logged in Firestore with all 4 metrics
[ ] Full pipeline completes in < 60 seconds
```

---

## Implementation Order for Coding Agents

Follow this sequence — each phase depends on the previous:

1. **Phase 0** → scaffold + verify dev servers
2. **Phase 1** → knowledge ingestion + verify retrieval manually
3. **Phase 2** → tools (test each tool function independently)
4. **Phase 3.1** → Retriever agent (test with `adk web` dev server)
5. **Phase 3.2** → Critic agent (test with a real Figma URL)
6. **Phase 3.3** → Evaluator agent (test with mock critique items)
7. **Phase 3.4** → Orchestrator + ParallelAgent wiring
8. **Phase 4** → FastAPI server + SSE streaming
9. **Phase 5** → AgentOps logging (add to server.py)
10. **Phase 6** → Frontend (start with static CritiqueView, then add streaming)
11. **Phase 7** → Deploy backend first, then frontend
12. **Phase 8** → Demo run

**Do not skip Phase 1 verification** — if retrieval returns garbage, all downstream agents produce garbage.

Update implementation order to reflect the 5-agent architecture:

4. **Phase 3.1** → FigmaFetcher agent (simplest — just data collection, test with a real Figma URL)
5. **Phase 3.2** → Retriever agent (test with `adk web` dev server)
6. **Phase 3.3** → Critic agent (test with mock Stage 1 outputs — no live pipeline needed yet)
7. **Phase 3.4** → Evaluator agent (test with mock critique items)
8. **Phase 3.5** → Orchestrator + Stage 1 ParallelAgent([Retriever, FigmaFetcher]) wiring

---

## Critical Constraints (Non-Negotiable)

- **Stage 1 = ParallelAgent([Retriever, FigmaFetcher])** — these are independent; run concurrently
- **Stage 2 = Critic** — must run AFTER Stage 1; receives both knowledge snippets AND image bytes
- **Every critique item must have a `rule_citation`** — Evaluator drops any without one
- **Critic uses Gemini structured JSON output** (`response_mime_type="application/json"`) — never free-form text
- **Retriever uses `RETRIEVAL_QUERY` task type for query embeddings** and `RETRIEVAL_DOCUMENT` for indexing
- **MCPToolset per-request** via `build_orchestrator()` context manager — never stored in `app.state`
- **Forward-message pattern** in Orchestrator — do not paraphrase Critic output, pass critique JSON through with fidelity
- **CORS middleware** must be added before any other middleware in FastAPI
- **Per-session Firestore document** for trajectories — never share state between sessions
- **MMR reranking** in Retriever — prevents 5 WCAG-only results when topic overlaps multiple knowledge areas
- **Python 3.12** everywhere — venv, Dockerfile, pyproject.toml. Do not use system 3.14.
