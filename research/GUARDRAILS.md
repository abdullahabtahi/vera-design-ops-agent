# Vera — Guardrails Inventory

Full inventory of safety, security, and quality guardrails implemented across the Vera codebase. 54 guardrails across 7 categories.

---

## Output Quality (8)

| Guardrail | File | What it does |
|---|---|---|
| Measurement token enforcement | `backend/tools/critic_tools.py:354` | Rejects fixes without `#hex`, `px`, `rem`, `:1` ratio — regex check, no LLM judgment |
| Issue inflation detection | `backend/tools/critic_tools.py:405` | Flags reports with >7 issues |
| Monotone citation detection | `backend/tools/critic_tools.py:412` | Flags when >70% of issues cite the same rule prefix |
| Gaming risk score | `backend/tools/critic_tools.py:371` | Returns `low/medium/high` gaming risk on every parsed critique |
| Constitutional QA | `backend/agents/orchestrator_agent.py:265` | `self_critic_agent` checks 8 rules: fix specificity, rule citation accuracy, severity calibration, duplicates, director summary, positive observations, vague directives, overcritique |
| Revision skip callback | `backend/agents/orchestrator_agent.py:345` | Zero LLM cost if `revision_needed: false` — skips `critic_revision_agent` entirely |
| State compression | `backend/agents/orchestrator_agent.py:92` | After synthesis, compresses `retrieved_knowledge` and `figma_context` ~80–95% to prevent token overflow on multi-turn sessions |
| Markdown fence stripping | `backend/server.py:603` + `frontend/app/hooks/useAgentStream.ts:371` | Strips ` ```json ` wrappers from LLM responses before parsing |

---

## Input Validation (9)

| Guardrail | File | What it does |
|---|---|---|
| Message length limit | `backend/server.py:376` | Caps incoming chat messages at 8000 characters |
| Figma URL length limit | `backend/server.py:378` | Restricts Figma URLs to 2048 characters |
| Session ID length limit | `backend/server.py:377` | Caps session ID at 128 characters |
| Image MIME type whitelist | `backend/server.py:90` | Allows only PNG, JPEG, WebP, GIF for uploaded images |
| Image size guard — server | `backend/server.py:91` | Rejects base64-decoded images larger than 10 MB |
| Image size guard — client | `frontend/app/hooks/useAgentStream.ts:263` | Rejects images >10 MB on the frontend before encoding to base64 |
| File upload size limit | `backend/server.py:857` | Caps Tier 2 knowledge uploads at 20 MB |
| Magic byte file verification | `backend/server.py:860` | Checks actual file header signatures (PDF `%PDF`, PNG `\x89PNG`, JPEG `\xff\xd8\xff`); rejects if detected MIME ≠ declared Content-Type — blocks disguised executables |
| RAG `top_k` clamping | `backend/tools/rag_tools.py:252` | Clamps `top_k` to [1, 10]; `tier_filter` validated against allowed values |

---

## Auth & Security (8)

| Guardrail | File | What it does |
|---|---|---|
| Firebase ID token verification | `backend/auth/firebase_auth.py:51` | Validates Firebase ID token with `check_revoked=True`; raises 401 on invalid/expired tokens |
| Bearer token format validation | `backend/auth/firebase_auth.py:66` | Rejects empty or malformed Authorization headers |
| Auth bypass for local dev | `backend/auth/firebase_auth.py:62` | `AUTH_REQUIRED=false` returns stable `dev-user` UID; never active in production |
| CORS origin whitelist | `backend/server.py:128` | Restricts cross-origin requests to `settings.allowed_origins` |
| SSRF protection — website URLs | `backend/server.py:80` | Validates external URLs before Playwright fetch; blocks private/loopback/link-local IP ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8, ::1) |
| SSRF protection — Figma URLs | `backend/server.py:355` | Same `_validate_external_url()` check applied before Figma image pre-fetch |
| Path traversal prevention | `backend/server.py:946` | Blocks `..` and validates source file identifiers against safe regex `^[\w\-. /%@?=&:+]+$` before deletion |
| HTTPS enforcement | `backend/server.py:990` | Requires HTTPS for URL-based knowledge ingestion; `require_https=True` passed to URL validator |

---

## HTTP Security Headers (6)

All set in `frontend/next.config.ts`.

| Header | Value | What it prevents |
|---|---|---|
| `Content-Security-Policy` | `default-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'` | XSS, object injection, base tag hijacking |
| `X-Frame-Options` | `DENY` | Clickjacking |
| `X-Content-Type-Options` | `nosniff` | MIME type sniffing |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Referrer information leakage |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Unauthorized browser feature access |
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains; preload` | HTTP downgrade attacks (production only) |

---

## Cost Protection (9)

| Guardrail | File | What it does |
|---|---|---|
| Rate limiting — chat | `backend/server.py:755` | 15 req/min per IP on `/api/chat` via `slowapi` |
| Rate limiting — upload | `backend/server.py:821` | 5 req/min on `/api/knowledge/upload` |
| Rate limiting — fetch URL | `backend/server.py:977` | 10 req/min on `/api/knowledge/fetch-url` |
| Tool call loop detection | `backend/server.py:534` | Aborts the run if any single tool is called >6 times; emits `RUN_ERROR` |
| Auto-eval text trimming | `backend/server.py:664` | Trims critique report to 3000 chars before auto-eval scoring |
| Session metadata cap | `backend/server.py:166` | Caps in-memory session dict at 1000 entries; evicts oldest on overflow |
| Base64 blob scrubbing | `backend/server.py:576` | Removes image base64 from `TOOL_CALL_END` SSE payloads; replaces with char count |
| Figma color extraction cap | `backend/tools/figma_tools.py:44` | Limits recursive extraction to depth 4, 30 unique entries |
| Figma component list cap | `backend/tools/figma_tools.py:118` | Caps returned component list at 50 |

---

## Resource Protection (8)

| Guardrail | File | What it does |
|---|---|---|
| SSE stream abort on unmount | `frontend/app/hooks/useAgentStream.ts:215` | Aborts in-flight SSE stream when component unmounts; prevents memory leaks |
| Stop button | `frontend/app/hooks/useAgentStream.ts:407` | User-triggered mid-run abort |
| Team preferences cache TTL | `backend/tools/rag_tools.py:36` | 5-min TTL on Firestore preference reads |
| Figma API timeout | `backend/tools/figma_tools.py:20` | 30-second timeout on Figma REST API calls |
| Playwright timeout | `backend/server.py:363` | 20-second timeout on website screenshot capture |
| Figma prefetch HTTP timeout | `backend/server.py:220` | 20-second timeout on async Figma image pre-fetch |
| Eval score clamping | `backend/server.py:703` | Clamps auto-eval scores to [0.0, 1.0] |
| Session eviction on overload | `backend/server.py:185` | Graceful degradation when session dict exceeds 1000 entries |

---

## Robustness & Fallbacks (6)

| Guardrail | File | What it does |
|---|---|---|
| HyDE query expansion fallback | `backend/tools/rag_tools.py:144` | Falls back to original query if HyDE expansion fails; never blocks retrieval |
| Gemini reranking fallback | `backend/tools/rag_tools.py:216` | Falls back to top-k results in original order if reranking fails |
| Set-of-Marks annotation fallback | `backend/server.py:342` | Returns original image unchanged if annotation fails; logged as non-critical |
| Playwright screenshot fallback | `backend/server.py:367` | Returns `None` on any screenshot failure; critique continues without image |
| Auto-eval fire-and-forget | `backend/server.py:616` | LLM-as-Judge runs in background task; never blocks user response |
| Malformed revision feedback fallback | `backend/agents/orchestrator_agent.py` | Graceful fallback if `self_critic_agent` returns unparseable JSON |

---

## Summary

| Category | Count |
|---|---|
| Output Quality | 8 |
| Input Validation | 9 |
| Auth & Security | 8 |
| HTTP Security Headers | 6 |
| Cost Protection | 9 |
| Resource Protection | 8 |
| Robustness & Fallbacks | 6 |
| **Total** | **54** |
