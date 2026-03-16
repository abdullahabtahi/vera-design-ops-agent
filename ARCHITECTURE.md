# Vera — Agent Architecture

## Mermaid Diagram

> Paste the block below into [mermaid.live](https://mermaid.live) → export as PNG/SVG for submission.

```mermaid
flowchart TD
    classDef agent     fill:#1e1b4b,stroke:#6366f1,color:#e0e7ff,rx:8
    classDef tool      fill:#052e16,stroke:#4ade80,color:#bbf7d0
    classDef store     fill:#1c1400,stroke:#f59e0b,color:#fef3c7
    classDef infra     fill:#0f172a,stroke:#64748b,color:#cbd5e1
    classDef parallel  fill:#0c1a2e,stroke:#38bdf8,color:#bae6fd
    classDef seq       fill:#130f26,stroke:#a78bfa,color:#ede9fe

    %% ── Entry points ──────────────────────────────────────────────────
    USER(["👤 Designer\nFigma URL · Website URL · UX Question"])

    subgraph FE["⚡ Next.js Frontend  ·  Firebase Auth"]
        STREAM["AG-UI SSE Consumer\nuseAgentStream.ts"]
    end

    subgraph SRV["☁️ FastAPI  ·  Google Cloud Run"]
        API["POST /api/chat\nSSE Stream"]
        PW["🎭 Playwright\nWebsite Screenshot"]
        FP["📐 Figma PNG\nAsync Prefetch"]
    end

    %% ── Root agent ────────────────────────────────────────────────────
    subgraph ROOT["🤖 root_agent · design_ops_navigator · gemini-2.5-flash"]

        ORCH(["Orchestrator\n4-Route Router"]):::agent

        subgraph TOOLS_O["Direct Tools  (Route B / D)"]
            direction LR
            TO1(["search_knowledge_base"]):::tool
            TO2(["list_knowledge_sources"]):::tool
            TO3(["web_search"]):::tool
        end

        %% ── Pipeline ──────────────────────────────────────────────────
        subgraph SEQ["critique_pipeline · SequentialAgent"]:::seq

            subgraph PAR["parallel_research · ParallelAgent  🔀"]:::parallel
                direction LR

                subgraph RET_BOX["retriever_agent · gemini-2.5-flash"]
                    RET(["RAG Retriever"]):::agent
                    subgraph TOOLS_R["Tools"]
                        direction LR
                        TR1(["search_knowledge_base"]):::tool
                        TR2(["list_knowledge_sources"]):::tool
                    end
                end

                subgraph FFG_BOX["figma_fetcher_agent · gemini-2.5-flash"]
                    FFG(["Figma Fetcher"]):::agent
                    subgraph TOOLS_F["Tools"]
                        direction LR
                        TF1(["get_figma_node_tree"]):::tool
                        TF2(["get_figma_frame_image"]):::tool
                    end
                end
            end

            subgraph CRT_BOX["critic_agent · gemini-2.5-flash  🖼️ Multimodal Vision"]
                CRT(["UX Critic\n— sees embedded PNG\n— reads retrieved_knowledge\n— reads figma_context"]):::agent
                subgraph TOOLS_C["Tools"]
                    direction LR
                    TC1(["get_critique_schema"]):::tool
                    TC2(["parse_critique_json"]):::tool
                    TC3(["compute_contrast_ratio"]):::tool
                end
            end

            QA(["self_critic_agent · gemini-2.5-flash\n🔍 Constitutional QA  ·  8-Rule Check\nFIX_SPECIFICITY · RULE_CITATION · SEVERITY_ACCURACY\nDUPLICATE_ELEMENTS · OVERCRITIQUE · VAGUE_DIRECTIVE"]):::agent

            REV(["critic_revision_agent · gemini-2.5-flash\n⚡ Skip if clean  —  zero LLM cost\nFixes only flagged issue indices"]):::agent

            SYN(["synthesis_agent · gemini-2.5-flash\n🎨 Design Director Voice\n15 yrs · ex-Google · ex-Figma\nCompresses state after output"]):::agent
        end
    end

    %% ── Knowledge store ───────────────────────────────────────────────
    subgraph FS["🗄️ Firestore Vector Search  ·  768-dim · Flat · COSINE"]
        T1[("Tier 1 · ux_knowledge\nWCAG 2.2  ·  Nielsen 10 Heuristics\nGestalt Principles  ·  Cognitive Laws\nMaterial Design 3")]:::store
        T2[("Tier 2 · user_knowledge\nTeam Design System\nBrand Guidelines  ·  Component Specs\nInternal Style Guides")]:::store
    end

    %% ── Edges ─────────────────────────────────────────────────────────

    USER --> STREAM
    STREAM <-->|"HTTP · SSE events"| API
    API -->|"non-Figma URL"| PW
    API -->|"figma URL"| FP

    API --> ORCH

    ORCH -->|"Route B — UX question\nRAG → answer"| TO1
    ORCH -->|"Route B — recency signal\nweb fallback"| TO3
    ORCH -->|"Route D — knowledge audit"| TO2
    ORCH -->|"Route A — Figma critique\nRoute C — Website critique"| SEQ

    RET --> TR1 & TR2
    TR1 -->|"3 searches · tier_filter"| T1 & T2
    TR2 --> T2

    FFG --> TF1 & TF2

    PAR -->|"retrieved_knowledge ──────────────────"| CRT
    PAR -->|"figma_context ─────────────────────────"| CRT
    FP  -->|"inline PNG  🖼️"| CRT
    PW  -->|"inline PNG  🖼️"| CRT

    CRT -->|"critique_report JSON"| QA
    QA  -->|"critique_revision_feedback\nrevision_needed: true/false"| REV
    REV -->|"critique_report  revised or unchanged"| SYN

    SYN -->|"TEXT_MESSAGE_CONTENT\nSSE stream"| STREAM
    STREAM --> USER
```

---

## Session State Flow

```
Input state:      figma_url · project_context · som_node_map · search_mode
                                    │
              ┌─────────────────────┴──────────────────────┐
              ▼                                             ▼
    retrieved_knowledge                              figma_context
    (Tier 1 + Tier 2 chunks)               (node tree · styles · components)
              │                                             │
              └────────────────────┬───────────────────────┘
                                   ▼
                          critique_report  (CritiqueReport JSON)
                          ┌─────────────────────────────────┐
                          │ issues[]          severity ranks │
                          │ director_summary[]               │
                          │ positive_observations[]          │
                          │ flow_issues[]                    │
                          │ trust_safety[]                   │
                          │ recommended_experiments[]        │
                          │ context_alignment_score          │
                          └─────────────────────────────────┘
                                   │
                                   ▼
                    critique_revision_feedback  (QA JSON)
                    { revision_needed, feedback[], issues_to_revise[] }
                                   │
                                   ▼
                          critique_report  (revised or same)
                                   │
                                   ▼
                    [Final human-readable response]
                    + state compressed  (~80-95% token reduction)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent Framework | Google ADK (SequentialAgent, ParallelAgent, Agent) |
| LLM | Gemini 2.5 Flash (all agents) |
| Embeddings | Gemini Embedding 001 (768-dim) |
| Vector Store | Firestore Native Vector Search (Flat · COSINE) |
| Vision | Gemini multimodal — inline PNG |
| Web Capture | Playwright (Chromium) |
| Design API | Figma REST API v1 |
| Server | FastAPI · AG-UI SSE protocol |
| Deployment | Google Cloud Run |
| Frontend | Next.js 15 · React 19 · Tailwind v4 |
| Auth | Firebase Authentication + Firestore |
