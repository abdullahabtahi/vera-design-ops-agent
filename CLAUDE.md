# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Design Ops Navigator** — an AI design co-pilot that connects to Figma, understands a team's design system, and delivers expert-grounded UX critique (citing WCAG, Gestalt, Nielsen heuristics, etc.). Built for the Gemini Live Challenge hackathon.

The system reads existing Figma files (or captures live websites via Playwright) and critiques them against pre-loaded UX research rules. It does not generate designs.

## Repository Structure

```
design-ops-navigator/
  backend/         # Python, Google ADK, FastAPI
  frontend/        # Next.js 15, React 19, Tailwind v4
.env.example       # Copy to backend/.env and frontend/.env.local
research/          # Architecture docs and product spec
```

## Development Commands

### Backend (`design-ops-navigator/backend/`)

Uses `uv` as the package manager. Python 3.12 required.

```bash
# Run FastAPI server (AG-UI SSE endpoint on port 8000)
uv run uvicorn server:app --reload

# Run ADK playground UI (port 8000)
uv run adk web .

# Lint
uv run ruff check .
uv run ruff format .

# Tests
uv run pytest

# Knowledge base operations
uv run python -m knowledge.ingest                            # ingest sources
uv run python -m knowledge.ingest --reset                    # wipe + re-ingest
uv run python -m knowledge.ingest --verify "contrast ratio"  # ingest + test retrieval
uv run python -m knowledge.fetch_sources                     # re-download source .md files
uv run python -m knowledge.user_docs --file path/to/doc.pdf --name "Design System"  # Tier 2 ingest

# ADK evaluation (from backend/ directory)
uv run adk eval agent.py tests/eval/evalsets/critique_quality.json --eval_config_file_path tests/eval/eval_config.json
uv run adk eval agent.py tests/eval/evalsets/route_b_quality.json --eval_config_file_path tests/eval/eval_config_critique.json
```

### Frontend (`design-ops-navigator/frontend/`)

```bash
npm run dev      # dev server on port 3000
npm run build    # production build
npm run test:e2e # Playwright E2E tests (requires both servers running)
```

### Starting Dev Servers

Before starting any server, check for port conflicts and kill them first:

```bash
# Backend (port 8000)
lsof -ti :8000 | xargs kill -9 2>/dev/null; uv run uvicorn server:app --reload

# Frontend (port 3000)
lsof -ti :3000 | xargs kill -9 2>/dev/null; npm run dev
```

Do not suggest restarting a server if the user has just restarted it. Diagnose the root cause instead.

## Architecture

### Agent Hierarchy (Google ADK)

```
root_agent (design_ops_navigator, gemini-2.5-flash)
  tools: [search_knowledge_base]          ← Route B: general UX questions
  sub_agents:
    critique_pipeline (SequentialAgent)   ← Route A (Figma) / Route C (website)
      parallel_research (ParallelAgent)
        retriever_agent  → output_key: retrieved_knowledge
        figma_fetcher_agent  → output_key: figma_context
      critic_agent  → output_key: critique_report
      synthesis_agent  → formats JSON → human-readable response
```

**Routing logic** in `agents/orchestrator_agent.py`:
- `figma.com` in message → delegate to `critique_pipeline`
- `http(s)://` non-Figma URL → delegate to `critique_pipeline` (website screenshot captured via Playwright)
- No URL → answer directly using `search_knowledge_base`

**ADK discovery**: `agents/__init__.py` exports `root_agent`; `agent.py` re-exports it for `adk eval`.

### Embeddings / Vector Store (Two-Tier RAG)

| Tier | Collection | Model | Use |
|---|---|---|---|
| 1 | `ux_knowledge` | `gemini-embedding-001` (768-dim) | Pre-loaded UX knowledge (WCAG, Nielsen, etc.) |
| 2 | `user_knowledge` | `gemini-embedding-2-preview` (768-dim) | User-uploaded PDFs/images |

- Store: Firestore native vector search, field `embedding`, Flat index, COSINE distance
- Retrieval: top-20 fetch → MMR reranking (Python) → top-5 returned
- `search_knowledge_base` ADK tool searches BOTH tiers and merges results
- `DistanceMeasure` import: `from google.cloud.firestore_v1.base_vector_query import DistanceMeasure`

### Server SSE Events (`server.py`)

`POST /api/chat` accepts `{message, session_id?, figma_url?, image_base64?, image_mime_type?}` and streams AG-UI events:

| Event | When |
|---|---|
| `TEXT_MESSAGE_CONTENT` | Streaming text from `design_ops_navigator` or `synthesis_agent` |
| `TOOL_CALL_START` / `TOOL_CALL_END` | Before/after each tool invocation |
| `STATE_DELTA` | When `retrieved_knowledge`, `figma_context`, `critique_report`, `figma_url`, `figma_frame_loaded`, `website_screenshot_loaded` are set |
| `RUN_FINISHED` / `RUN_ERROR` | End of run |

Figma frame PNGs and website screenshots are pre-fetched asynchronously in `_prefetch_figma_image_async()` / `_prefetch_website_screenshot_async()` and attached as `inline_data` (multimodal Part) before the ADK runner starts.

### Frontend Key Files

| File | Purpose |
|---|---|
| `app/page.tsx` | Main layout: project context panel, design URL field (Figma or website), workspace picker, playbook banner, chat + agent activity sidebar |
| `app/hooks/useAgentStream.ts` | SSE consumer — parses events, manages `Message[]` / `AgentEvent[]`, localStorage session/workspace persistence |
| `app/components/ChatWindow.tsx` | Chat message list + input (supports image upload) |
| `app/components/ActivityFeed.tsx` | Live agent event timeline in sidebar |
| `app/components/CritiqueReport.tsx` | Structured critique card renderer |
| `app/components/Sidebar.tsx` | Navigation sidebar |
| `app/lib/playbooks.ts` | Pre-defined critique prompt templates (accessibility audit, cognitive load, etc.) |
| `app/history/page.tsx` | Session history browser |
| `app/knowledge/page.tsx` | Knowledge base management (upload, list sources) |

Backend URL is set via `NEXT_PUBLIC_BACKEND_URL` (defaults to `http://localhost:8000`).

## Environment Setup

Copy `.env.example` to `backend/.env`. Required variables:

```
GOOGLE_API_KEY=              # Gemini AI Studio key (local dev)
GOOGLE_CLOUD_PROJECT=        # GCP project ID
GOOGLE_CLOUD_LOCATION=us-central1
FIGMA_ACCESS_TOKEN=          # Figma PAT (Settings > Security)
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json  # local dev only
AUTH_REQUIRED=false          # set false to skip Firebase token verification in local dev
```

`GOOGLE_GENAI_USE_VERTEXAI=false` uses AI Studio (dev); set `true` for Vertex AI (prod).

### Authentication Flow

- **Backend**: `auth/firebase_auth.py` — FastAPI dependency `require_auth` verifies Firebase ID tokens. Controlled by `AUTH_REQUIRED` env var (set `false` for local dev / `adk web .`).
- **Frontend**: `app/lib/firebase.ts` + `app/auth/AuthContext.tsx` handle Firebase client auth. After sign-in, the ID token is POSTed to `/api/auth/session` which sets an HttpOnly `don_session` cookie.
- **Middleware**: `middleware.ts` protects all routes except `/auth`, `/api/waitlist`, `/api/auth/session` — redirects unauthenticated users to `/auth`.

## MCP & Plugin Setup

MCP server config goes in `.mcp.json` (project-level) or `~/.claude/settings.json` (global) — never in the project `settings.json`. Verify the server name and config format before applying. When a new MCP server is added, confirm it appears in `/mcp` before proceeding.

## Stack Boundaries

Backend code is **Python only** (`design-ops-navigator/backend/`). Frontend code is **TypeScript/React only** (`design-ops-navigator/frontend/`). Never write Python in the frontend directory or TypeScript in the backend directory.

## Bug Fix Workflow

After fixing any bug:
1. Run `uv run pytest` (backend) or `npm test` (frontend) immediately
2. Verify no regressions before declaring the fix complete
3. Check that new code doesn't introduce wrong parameter names, schema mismatches, or broken test assertions — these were the top recurring secondary-bug pattern in this project

## Design & Figma Work

When using Figma MCP tools:
- Provide explicit constraints upfront: icon library (Lucide only — no emoji), grid spacing (8px/16px), color palette, and component hierarchy
- If generation produces low-quality output on the first attempt, do **not** retry the same approach — pivot to providing a structured spec (component tree, spacing values, hex colors) and regenerate once with full constraints
- If Playwright screenshots come out blank, check that `playwright install chromium` has been run

## Critical Gotchas

- **Model name**: use `gemini-2.5-flash`. `gemini-2.0-flash` returns 404 NOT_FOUND on Vertex AI.
- **Embedding model on Vertex AI**: use `gemini-embedding-001`. `gemini-embedding-2-preview` is AI Studio only (404 on Vertex AI).
- **ADK agent instances cannot share parents** — each `Agent` instance can only have one parent in the hierarchy.
- **`load_dotenv()` must run before any `google.adk` imports** in `server.py` — ADK reads env at import time. `pydantic-settings` does not set `os.environ`.
- **Firestore vector indices** must be created manually in GCP Console before first ingest: both `ux_knowledge` and `user_knowledge` collections need field `embedding`, dimension 768, Flat type.
- **Figma node-id**: URL uses `-` separator (e.g. `node-id=1-2`) but the REST API requires `:` (e.g. `1:2`). Conversion happens in `server.py:_prefetch_figma_image_async` and `figma_tools.py`.
- **`google.genai` not `google.generativeai`**: embeddings use `from google import genai`; the deprecated `google.generativeai` package should not be used.
- **`_get_client()` in `embeddings.py`**: must NOT pass `api_key=` when `GOOGLE_GENAI_USE_VERTEXAI=true`.
- **`GOOGLE_APPLICATION_CREDENTIALS`** must be in pydantic `Settings` class — `os.getenv()` does not read `.env`.
- **Synthesis agent**: the orchestrator does NOT regain a turn after transferring to `critique_pipeline`. `synthesis_agent` is the final step and produces the user-facing response from `{critique_report}` in session state.
- **Live website critique**: requires `playwright` to be installed with Chromium (`playwright install chromium`).
