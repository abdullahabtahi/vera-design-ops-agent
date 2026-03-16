"""
Design Ops Navigator — FastAPI backend with AG-UI SSE event stream.

Endpoints:
  GET  /health                       — liveness probe
  POST /api/chat                     — AG-UI SSE stream for agent responses
  GET  /api/sessions/{session_id}    — retrieve session history

AG-UI event types emitted:
  TEXT_MESSAGE_CONTENT  — streaming text tokens
  TOOL_CALL_START       — agent calling a tool
  TOOL_CALL_END         — tool returned a result
  STATE_DELTA           — session state key updated
  RUN_FINISHED          — agent run complete
  RUN_ERROR             — agent encountered an error

See: https://docs.copilotkit.ai/ag-ui
"""

from __future__ import annotations

import asyncio
import base64
import io
import ipaddress
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()  # must run before any google-adk / google-genai imports

# AgentOps observability — graceful no-op if AGENTOPS_API_KEY is not set
try:
    import os as _os
    _agentops_key = _os.getenv("AGENTOPS_API_KEY", "")
    if _agentops_key:
        import agentops
        agentops.init(
            api_key=_agentops_key,
            trace_name="design-ops-navigator",
            tags=["ux-critique", "adk", "hackathon"],
        )
        logger_bootstrap = __import__("logging").getLogger(__name__)
        logger_bootstrap.info("AgentOps initialized — session replays enabled")
    else:
        agentops = None  # type: ignore[assignment]
except Exception:
    agentops = None  # type: ignore[assignment]

import httpx  # noqa: E402
import json  # noqa: E402

import google.adk  # noqa: E402
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402
from slowapi import Limiter, _rate_limit_exceeded_handler  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402
from slowapi.util import get_remote_address  # noqa: E402
from google.adk.events import Event, EventActions  # noqa: E402
from google.adk.plugins import ReflectAndRetryToolPlugin  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.genai import types as genai_types  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from agents import root_agent  # noqa: E402
from auth.firebase_auth import require_auth  # noqa: E402
from config import settings  # noqa: E402

logger = logging.getLogger(__name__)

# ── Security helpers ───────────────────────────────────────────────────────────

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / GCP metadata
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

_ALLOWED_IMAGE_MIMES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB decoded limit


def _validate_external_url(url: str, require_https: bool = False) -> bool:
    """
    Returns True only if `url` is safe to fetch server-side:
    - Must be http or https (or only https if require_https=True)
    - Hostname must not resolve to a private/loopback/link-local IP range
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ({"https"} if require_https else {"http", "https"}):
            return False
        hostname = parsed.hostname or ""
        if not hostname:
            return False
        try:
            addr = ipaddress.ip_address(hostname)
            if any(addr in net for net in _PRIVATE_NETWORKS):
                return False
        except ValueError:
            # It's a hostname, not a bare IP — block obvious internal names
            if hostname in ("localhost", "metadata.google.internal") or hostname.endswith(".internal"):
                return False
        return True
    except Exception:
        return False


# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(title="Design Ops Navigator", version="0.1.0")

_limiter = Limiter(key_func=get_remote_address)
app.state.limiter = _limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-Session-Id"],
)

# In-memory session service (swap for Firestore in production)
_session_service = InMemorySessionService()

APP_NAME = "design_ops_navigator"

_FIGMA_BASE = "https://api.figma.com/v1"

# ── Project context parsing ────────────────────────────────────────────────────

_CTX_RE = re.compile(r"^\[Project context — ([^\]]*)\]\n\n", re.DOTALL)


def _parse_project_context(message: str) -> str:
    """
    Extract [Project context — Goal: X | Persona: Y | Environment: Z] prefix.

    Returns a clean multi-line string for session state, e.g.:
      Goal: Enable sub-60s hazard reporting
      Persona: Stressed resident, low tech literacy
      Environment: Mobile, outdoor, low light

    Returns "" if no context prefix is present.
    """
    m = _CTX_RE.match(message)
    if not m:
        return ""
    raw = m.group(1)  # "Goal: X | Persona: Y"
    return "\n".join(p.strip() for p in raw.split("|") if p.strip())

# ── Session metadata (lightweight in-memory store for session list UI) ──────────
# Stores: {session_id: {id, title, created_at, updated_at, message_count}}
_session_meta: dict[str, dict] = {}
_MAX_SESSION_META = 1000  # cap to prevent unbounded memory growth (MEDIUM-1)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _upsert_session_meta(session_id: str, first_message: str | None = None) -> None:
    now = _now_iso()
    if session_id not in _session_meta:
        title = (first_message or "New session")[:60]
        _session_meta[session_id] = {
            "id": session_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
            "message_count": 1,
        }
        # Evict oldest entries when over the cap
        if len(_session_meta) > _MAX_SESSION_META:
            oldest = sorted(_session_meta, key=lambda k: _session_meta[k]["updated_at"])
            for key in oldest[: len(_session_meta) - _MAX_SESSION_META]:
                del _session_meta[key]
    else:
        _session_meta[session_id]["updated_at"] = now
        _session_meta[session_id]["message_count"] += 1


# ── Figma image pre-fetch (async, non-blocking) ────────────────────────────────


async def _prefetch_figma_image_async(figma_url: str, figma_token: str | None = None) -> bytes | None:
    """
    Pre-fetch a Figma frame PNG asynchronously.
    Returns raw PNG bytes, or None on any failure (never raises).
    figma_token overrides the server-side settings token when provided.
    """
    token = figma_token or settings.figma_access_token
    if not token:
        return None

    match = re.search(r"/(?:design|file)/([A-Za-z0-9]+)", figma_url)
    file_key = match.group(1) if match else None
    if not file_key:
        return None

    node_match = re.search(r"node-id=([^&]+)", figma_url)
    node_id = node_match.group(1).replace("-", ":") if node_match else None
    if not node_id:
        return None

    headers = {"X-Figma-Token": token}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{_FIGMA_BASE}/images/{file_key}",
                params={"ids": node_id, "format": "png", "scale": 2},
                headers=headers,
            )
            resp.raise_for_status()
            images = resp.json().get("images", {})
            image_url = images.get(node_id) or images.get(node_id.replace(":", "-"))
            if not image_url:
                return None

            img_resp = await client.get(image_url)
            img_resp.raise_for_status()
            return img_resp.content
    except Exception:
        logger.warning("Failed to pre-fetch Figma image", exc_info=True)
        return None


# ── Set-of-Marks annotation ───────────────────────────────────────────────────


async def _annotate_with_som(
    image_bytes: bytes,
    figma_url: str,
    figma_token: str | None = None,
) -> tuple[bytes, str]:
    """
    Overlay numbered circles (Set-of-Marks) on a Figma frame PNG.

    Fetches the frame's immediate children via Figma REST API, projects their
    absolute bounding boxes onto the PNG coordinate space (scale=2 matches the
    pre-fetch call), and draws indigo circles with white labels.

    Returns:
        (annotated_png_bytes, node_map_string)
        On any failure, returns the original image unchanged and an empty map.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont

        match = re.search(r"/(?:design|file)/([A-Za-z0-9]+)", figma_url)
        file_key = match.group(1) if match else None
        node_match = re.search(r"node-id=([^&]+)", figma_url)
        node_id = node_match.group(1).replace("-", ":") if node_match else None
        if not file_key or not node_id:
            return image_bytes, ""

        token = figma_token or settings.figma_access_token
        if not token:
            return image_bytes, ""

        headers = {"X-Figma-Token": token}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{_FIGMA_BASE}/files/{file_key}",
                params={"ids": node_id, "depth": 2},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        frame_node = (data.get("nodes") or {}).get(node_id, {}).get("document") or {}
        if not frame_node:
            return image_bytes, ""

        frame_bb = frame_node.get("absoluteBoundingBox")
        if not frame_bb:
            return image_bytes, ""

        fx, fy = frame_bb["x"], frame_bb["y"]
        scale = 2.0  # matches scale=2 in _prefetch_figma_image_async
        img_w = frame_bb["width"] * scale
        img_h = frame_bb["height"] * scale

        children = frame_node.get("children") or []
        markers: list[dict] = []
        map_lines: list[str] = []
        for i, child in enumerate(children[:12], start=1):
            bb = child.get("absoluteBoundingBox")
            if not bb:
                continue
            cx = (bb["x"] - fx + bb["width"] / 2) * scale
            cy = (bb["y"] - fy + bb["height"] / 2) * scale
            cx = max(14, min(cx, img_w - 14))
            cy = max(14, min(cy, img_h - 14))
            name = child.get("name", f"element {i}")
            markers.append({"n": i, "x": int(cx), "y": int(cy)})
            map_lines.append(f"{i}: {name}")

        if not markers:
            return image_bytes, ""

        node_map = "Element reference (numbers overlaid on image):\n" + "\n".join(map_lines)

        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        try:
            font = ImageFont.load_default(size=14)
        except TypeError:
            font = ImageFont.load_default()

        for m in markers:
            x, y, n = m["x"], m["y"], m["n"]
            r = 13
            draw.ellipse([x - r - 1, y - r - 1, x + r + 1, y + r + 1], fill=(0, 0, 0, 180))
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(99, 102, 241, 220))
            text = str(n)
            try:
                tb = draw.textbbox((0, 0), text, font=font)
                tw, th = tb[2] - tb[0], tb[3] - tb[1]
            except Exception:
                tw = th = 8
            draw.text((x - tw // 2, y - th // 2), text, fill=(255, 255, 255, 255), font=font)

        out = Image.alpha_composite(img, overlay).convert("RGB")
        buf = io.BytesIO()
        out.save(buf, format="PNG")
        return buf.getvalue(), node_map

    except Exception:
        logger.debug("Set-of-Marks annotation failed (non-critical)", exc_info=True)
        return image_bytes, ""


# ── Website screenshot capture ────────────────────────────────────────────────


async def _prefetch_website_screenshot_async(url: str) -> bytes | None:
    """
    Capture a viewport screenshot of a live URL using Playwright headless Chromium.
    Returns raw PNG bytes, or None on any failure (never raises).
    """
    if not _validate_external_url(url):
        logger.warning("SSRF check blocked screenshot URL: %s", url)
        return None
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": 1440, "height": 900})
            await page.goto(url, wait_until="networkidle", timeout=20000)
            screenshot = await page.screenshot(full_page=False)
            await browser.close()
            return screenshot
    except Exception:
        logger.warning("Failed to capture website screenshot for %s", url, exc_info=True)
        return None


# ── Request / Response models ──────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str = Field(max_length=8000)
    session_id: str | None = Field(default=None, max_length=128)
    figma_url: str | None = Field(default=None, max_length=2048)
    image_base64: str | None = None     # optional screenshot (base64-encoded)
    image_mime_type: str | None = Field(default=None, max_length=64)


# ── AG-UI SSE helpers ──────────────────────────────────────────────────────────


def _sse(event_type: str, data: dict) -> str:
    """Format a single Server-Sent Event."""
    payload = json.dumps({"type": event_type, **data})
    return f"data: {payload}\n\n"


async def _run_agent_stream(
    session_id: str,
    user_id: str,
    message: str,
    figma_url: str | None,
    image_base64: str | None = None,
    image_mime_type: str | None = None,
    figma_token: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Run the ADK root_agent and yield AG-UI SSE events.

    Supports two visual input modes (not mutually exclusive):
    - image_base64: a user-uploaded screenshot passed directly as inline_data
    - figma_url: async-fetched Figma frame PNG (never blocks if Figma is slow)

    Event sequence per run:
      TEXT_MESSAGE_CONTENT (streaming tokens)
      TOOL_CALL_START / TOOL_CALL_END (per tool call)
      STATE_DELTA (when session state keys are updated)
      RUN_FINISHED or RUN_ERROR
    """
    # Track session metadata for session list UI
    _upsert_session_meta(session_id, message)

    # Ensure session exists
    session = await _session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    if session is None:
        session = await _session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )

    # Inject user message text into session state so pipeline callbacks can read it
    # (used by _init_pipeline_context to detect tier-filter directives)
    await _session_service.append_event(
        session,
        Event(
            invocation_id=str(uuid.uuid4()),
            author="server",
            actions=EventActions(state_delta={"_user_message": message}),
        ),
    )

    # Inject Figma URL into session state
    if figma_url:
        await _session_service.append_event(
            session,
            Event(
                invocation_id=str(uuid.uuid4()),
                author="server",
                actions=EventActions(state_delta={"figma_url": figma_url}),
            ),
        )
        yield _sse("STATE_DELTA", {"key": "figma_url", "value": figma_url})

    # Inject project_context into session state (parsed from [Project context — ...] prefix)
    project_context = _parse_project_context(message)
    if project_context:
        await _session_service.append_event(
            session,
            Event(
                invocation_id=str(uuid.uuid4()),
                author="server",
                actions=EventActions(state_delta={"project_context": project_context}),
            ),
        )
        yield _sse("STATE_DELTA", {"key": "project_context", "value": project_context})

    # Determine source type
    is_figma = bool(figma_url and "figma.com" in figma_url)
    is_website = bool(figma_url and not is_figma)

    # Build multimodal content parts
    augmented_message = message
    if is_figma:
        augmented_message = f"{message}\n\nFigma URL: {figma_url}"
    elif is_website:
        augmented_message = f"{message}\n\nWebsite URL: {figma_url}"

    parts: list[genai_types.Part] = [genai_types.Part(text=augmented_message)]

    # 1) User-uploaded screenshot (highest priority — always present if user attached)
    if image_base64:
        try:
            img_bytes = base64.b64decode(image_base64)
            if len(img_bytes) > _MAX_IMAGE_BYTES:
                logger.warning("Uploaded image exceeds size limit (%d bytes), skipping", len(img_bytes))
            else:
                mime = image_mime_type if image_mime_type in _ALLOWED_IMAGE_MIMES else "image/png"
                parts.append(
                    genai_types.Part(
                        inline_data=genai_types.Blob(mime_type=mime, data=img_bytes)
                    )
                )
                yield _sse("STATE_DELTA", {"key": "screenshot_loaded", "available": True})
        except Exception:
            logger.warning("Failed to decode image_base64", exc_info=True)

    # 2) Pre-fetch screenshot from source URL (skip if user already uploaded one)
    if figma_url and not image_base64:
        if is_figma:
            image_bytes = await _prefetch_figma_image_async(figma_url, figma_token=figma_token)
            state_key = "figma_frame_loaded"
            # Set-of-Marks: overlay numbered element labels on the Figma PNG
            if image_bytes:
                image_bytes, som_map = await _annotate_with_som(
                    image_bytes, figma_url, figma_token=figma_token
                )
                if som_map:
                    await _session_service.append_event(
                        session,
                        Event(
                            invocation_id=str(uuid.uuid4()),
                            author="server",
                            actions=EventActions(state_delta={"som_node_map": som_map}),
                        ),
                    )
        else:
            image_bytes = await _prefetch_website_screenshot_async(figma_url)
            state_key = "website_screenshot_loaded"

        if image_bytes:
            parts.append(
                genai_types.Part(
                    inline_data=genai_types.Blob(mime_type="image/png", data=image_bytes)
                )
            )
            yield _sse("STATE_DELTA", {"key": state_key, "available": True})
        else:
            yield _sse("STATE_DELTA", {"key": state_key, "available": False})

    user_content = genai_types.Content(role="user", parts=parts)

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=_session_service,
        plugins=[ReflectAndRetryToolPlugin(max_retries=2)],
    )

    # Guard: track tool call count to detect runaway loops
    _tool_call_count: dict[str, int] = {}
    MAX_TOOL_CALLS_PER_NAME = 6  # critic shouldn't call any tool more than 6 times

    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_content,
        ):
            # Text token streaming
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        if event.author in ("design_ops_navigator", "synthesis_agent"):
                            yield _sse("TEXT_MESSAGE_CONTENT", {
                                "agent": event.author,
                                "text": part.text,
                            })

            # Tool call events
            if event.get_function_calls():
                for fc in event.get_function_calls():
                    _tool_call_count[fc.name] = _tool_call_count.get(fc.name, 0) + 1
                    if _tool_call_count[fc.name] > MAX_TOOL_CALLS_PER_NAME:
                        logger.warning(
                            "Tool call loop detected: %s called %d times — aborting run",
                            fc.name, _tool_call_count[fc.name],
                        )
                        yield _sse("RUN_ERROR", {
                            "error": f"Critique aborted: tool '{fc.name}' called too many times ({_tool_call_count[fc.name]}). Try again.",
                            "session_id": session_id,
                        })
                        return
                    yield _sse("TOOL_CALL_START", {
                        "agent": event.author,
                        "tool": fc.name,
                        "args": dict(fc.args) if fc.args else {},
                    })

            if event.get_function_responses():
                for fr in event.get_function_responses():
                    response_preview = fr.response
                    # Scrub large base64 blobs from the SSE payload
                    if isinstance(response_preview, dict) and "image_base64" in response_preview:
                        response_preview = {
                            **response_preview,
                            "image_base64": f"<{len(response_preview['image_base64'])} chars>",
                        }
                    yield _sse("TOOL_CALL_END", {
                        "agent": event.author,
                        "tool": fr.name,
                        "status": response_preview.get("status", "ok") if isinstance(response_preview, dict) else "ok",
                    })

            # State delta — emit lightweight update for key state keys
            if event.actions and event.actions.state_delta:
                for key, value in event.actions.state_delta.items():
                    if key in ("retrieved_knowledge", "figma_context", "critique_report"):
                        payload: dict = {
                            "key": key,
                            "available": True,
                            "preview": str(value)[:100] if value else None,
                        }
                        # Send full JSON for critique_report so frontend can render structured cards
                        if key == "critique_report" and value:
                            if not isinstance(value, str):
                                payload["value"] = value
                            else:
                                # Strip markdown fences that the LLM sometimes adds despite instructions
                                raw = value.strip()
                                stripped = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
                                stripped = re.sub(r"\s*```$", "", stripped).strip()
                                try:
                                    payload["value"] = json.loads(stripped)
                                except Exception:
                                    try:
                                        payload["value"] = json.loads(raw)
                                    except Exception:
                                        payload["value"] = value
                        yield _sse("STATE_DELTA", payload)

        # Fire background auto-eval — non-blocking, never delays the stream
        _task = asyncio.create_task(_auto_eval_critique(session_id, user_id))
        _bg_tasks.add(_task)
        _task.add_done_callback(_bg_tasks.discard)

        yield _sse("RUN_FINISHED", {"session_id": session_id})

    except Exception as exc:
        logger.exception("Agent stream error: %s", exc)
        yield _sse("RUN_ERROR", {"error": f"Agent error: {type(exc).__name__}. Please try again.", "session_id": session_id})


# ── Background auto-eval (LLM-as-Judge) ────────────────────────────────────────

# Strong reference set prevents tasks from being GC'd before they complete.
_bg_tasks: set[asyncio.Task] = set()


async def _auto_eval_critique(session_id: str, user_id: str) -> None:
    """
    Post-run quality scoring using Gemini-as-Judge.

    Scores the critique_report on 4 dimensions (0.0 – 1.0 each):
      fix_specificity     — fixes include hex/px/ratio measurements
      severity_calibration — severity matches actual user impact
      insight_depth       — beyond surface; references root causes
      rule_grounding      — cites specific standard sections correctly

    Results written to Firestore `critique_evals` collection.
    Never raises — completely fire-and-forget.
    """
    try:
        session = await _session_service.get_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )
        if session is None:
            return

        critique_report = session.state.get("critique_report")
        if not critique_report:
            return

        report_text = (
            json.dumps(critique_report)
            if not isinstance(critique_report, str)
            else critique_report
        )
        # Trim to avoid token overflow (first 3000 chars covers most reports)
        report_text = report_text[:3000]

        from google import genai as _genai

        if settings.google_genai_use_vertexai:
            _client = _genai.Client()
        else:
            _client = _genai.Client(api_key=settings.google_api_key)

        prompt = (
            "You are an expert evaluator of UX critique reports.\n"
            "Score the following critique report on FOUR dimensions (each 0.0 – 1.0):\n\n"
            "1. fix_specificity: Do suggested fixes include concrete measurements "
            "(hex color codes, contrast ratios, px/rem values)? "
            "1.0 = every fix has exact values; 0.0 = all fixes are vague.\n"
            "2. severity_calibration: Is severity proportionate to actual user impact? "
            "1.0 = perfectly calibrated; 0.0 = critical issues labelled low or vice-versa.\n"
            "3. insight_depth: Does the critique go beyond surface observations to "
            "identify root causes or systemic issues? 1.0 = deep; 0.0 = surface only.\n"
            "4. rule_grounding: Are rules cited with specific standard sections "
            "(e.g. 'WCAG 2.2 SC 1.4.3', 'Nielsen #4')? 1.0 = all precise; 0.0 = no citations.\n\n"
            f"Critique report:\n{report_text}\n\n"
            "Return ONLY valid JSON, no explanation:\n"
            '{"fix_specificity": <0-1>, "severity_calibration": <0-1>, '
            '"insight_depth": <0-1>, "rule_grounding": <0-1>}'
        )

        response = await _client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        raw = (response.text or "").strip()
        if raw.startswith("```"):
            raw = raw[raw.find("{"):]
            if "```" in raw:
                raw = raw[: raw.rfind("```")]
        scores: dict = json.loads(raw.strip())

        # Clamp all values to [0.0, 1.0]
        for k in ("fix_specificity", "severity_calibration", "insight_depth", "rule_grounding"):
            scores[k] = max(0.0, min(1.0, float(scores.get(k, 0.5))))
        scores["overall"] = round(
            sum(scores[k] for k in ("fix_specificity", "severity_calibration",
                                     "insight_depth", "rule_grounding")) / 4,
            3,
        )

        from knowledge.ingest import get_db as _get_db
        _get_db().collection("critique_evals").add({
            "session_id": session_id,
            "user_id": user_id,
            "scores": scores,
            "timestamp": datetime.now(timezone.utc),
        })
        logger.info("Auto-eval complete for session %s: overall=%.2f", session_id, scores["overall"])

    except Exception:
        logger.debug("Auto-eval failed (non-critical)", exc_info=True)


# ── Endpoints ──────────────────────────────────────────────────────────────────


@app.get("/")
async def root():
    return {"service": "Design Ops Navigator", "docs": "/docs", "health": "/health"}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "adk_version": google.adk.__version__,
        "model": "gemini-2.5-flash",
        "knowledge_collection": settings.firestore_collection_knowledge,
    }


@app.get("/api/sessions")
async def list_sessions():
    """List all sessions with metadata (title, timestamps, message count)."""
    sessions = sorted(
        _session_meta.values(),
        key=lambda s: s["updated_at"],
        reverse=True,
    )
    return {"sessions": sessions}


@app.post("/api/chat")
@_limiter.limit("15/minute")
async def chat(request: Request, req: ChatRequest, uid: str = Depends(require_auth)):  # noqa: ARG001
    """
    Stream agent responses as AG-UI Server-Sent Events.

    Request body:
      {
        "message": "What's wrong with this button?",
        "session_id": "abc123",           // optional; creates new session if omitted
        "figma_url": "https://figma.com/design/...",  // optional
        "image_base64": "<base64 string>",            // optional screenshot
        "image_mime_type": "image/png"                // optional, defaults to image/png
      }

    Response: text/event-stream of AG-UI events.
    """
    session_id = req.session_id or str(uuid.uuid4())
    user_id = uid
    figma_token_override = request.headers.get("X-Figma-Token") or None

    return StreamingResponse(
        _run_agent_stream(
            session_id=session_id,
            user_id=user_id,
            message=req.message,
            figma_url=req.figma_url,
            image_base64=req.image_base64,
            image_mime_type=req.image_mime_type,
            figma_token=figma_token_override,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Session-Id": session_id,
        },
    )


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str, uid: str = Depends(require_auth)):
    """Retrieve session state and event history."""
    session = await _session_service.get_session(
        app_name=APP_NAME, user_id=uid, session_id=session_id
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "state_keys": list(session.state.keys()),
        "event_count": len(session.events) if hasattr(session, "events") else 0,
    }


# ── Knowledge management endpoints ─────────────────────────────────────────────

_ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
}


@app.post("/api/knowledge/upload")
@_limiter.limit("5/minute")
async def upload_knowledge(
    request: Request,  # noqa: ARG001
    file: UploadFile = File(...),
    source_name: str = "",
    category: str = "Team Docs",
    _uid: str = Depends(require_auth),
):
    """
    Upload a PDF or image to Tier 2 knowledge.

    The file is chunked, embedded with gemini-embedding-2-preview (multimodal),
    and written to the `user_knowledge` Firestore collection.

    The design team's uploaded docs are then searched alongside Tier 1
    universal UX rules during every critique.

    Form fields:
      file        — PDF or image file (required)
      source_name — Citation name shown in responses (optional; auto-derived from filename)
      category    — Knowledge category tag (default: "Team Docs")

    Returns:
      { status, chunks_written, source_name, filename }
    """
    from knowledge.user_docs import ingest_user_doc

    # Primary check: client-supplied Content-Type header
    content_type = file.content_type or ""
    if content_type not in _ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {content_type}. Allowed: PDF, PNG, JPEG, WEBP, GIF.",
        )

    file_bytes = await file.read()
    if len(file_bytes) > 20 * 1024 * 1024:  # 20 MB limit
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 20 MB.")

    # Secondary check: magic bytes (don't trust Content-Type header alone — HIGH-1)
    _MAGIC_SIGNATURES: dict[bytes, str] = {
        b"%PDF":        "application/pdf",
        b"\x89PNG\r\n": "image/png",
        b"\xff\xd8\xff": "image/jpeg",
        b"RIFF":        "image/webp",  # RIFF....WEBP
        b"GIF87a":      "image/gif",
        b"GIF89a":      "image/gif",
    }
    detected_mime: str | None = None
    for sig, mime in _MAGIC_SIGNATURES.items():
        if file_bytes[:len(sig)] == sig:
            detected_mime = mime
            break
    if detected_mime is None or detected_mime != content_type:
        logger.warning(
            "MIME mismatch on upload: declared=%s detected=%s filename=%s",
            content_type, detected_mime, file.filename,
        )
        raise HTTPException(
            status_code=415,
            detail="File content does not match declared type.",
        )

    result = ingest_user_doc(
        file_bytes=file_bytes,
        filename=file.filename or "upload",
        mime_type=content_type,
        source_name=source_name,
        category=category,
    )

    if result["status"] == "error":
        logger.error("File ingestion failed for %s: %s", file.filename, result.get("error"))
        raise HTTPException(status_code=500, detail="File processing failed. Please try again.")

    return result


@app.get("/api/knowledge/sources")
async def list_knowledge_sources():
    """
    List all knowledge sources (Tier 1 fixed + Tier 2 user-uploaded).

    Returns:
      {
        tier1: [ { source_name, category, chunk_count, description } ],
        tier2: [ { source_file, source_name, category, chunk_count, ingested_at } ]
      }
    """
    from knowledge.ingest import get_db
    from knowledge.user_docs import list_user_sources

    # Dynamically scan sources/*.md so the list stays in sync with what's on disk
    from pathlib import Path as _Path
    _sources_dir = _Path(__file__).parent / "knowledge" / "sources"
    tier1_sources = []
    for _p in sorted(_sources_dir.glob("*.md")):
        _content = _p.read_text(encoding="utf-8")
        _meta: dict[str, str] = {}
        if _content.startswith("---"):
            _end = _content.find("---", 3)
            if _end != -1:
                for _line in _content[3:_end].splitlines():
                    if ":" in _line:
                        _k, _, _v = _line.partition(":")
                        _meta[_k.strip()] = _v.strip()
        _body = _content[_content.find("---", 3) + 3:].strip() if _meta else _content
        _desc_lines = [ln.strip() for ln in _body.splitlines() if ln.strip() and not ln.startswith("#")]
        _description = _desc_lines[0][:140] if _desc_lines else ""
        tier1_sources.append({
            "source_name": _meta.get("source", _p.stem.replace("_", " ").title()),
            "category": _meta.get("category", "General"),
            "description": _description,
        })

    try:
        db = get_db()
        tier2_sources = list_user_sources(db)
    except Exception as exc:
        logger.warning("Failed to list Tier 2 sources: %s", exc)
        tier2_sources = []

    return {"tier1": tier1_sources, "tier2": tier2_sources}


_SAFE_SOURCE_FILE_RE = re.compile(r'^[\w\-. /%@?=&:+]+$')


@app.delete("/api/knowledge/sources/{source_file:path}")
async def delete_knowledge_source(source_file: str, _uid: str = Depends(require_auth)):
    """
    Delete a user-uploaded Tier 2 knowledge source by filename.

    All chunks associated with the file are removed from `user_knowledge`.
    Tier 1 sources cannot be deleted via this endpoint.
    """
    from knowledge.ingest import get_db
    from knowledge.user_docs import delete_user_source

    if ".." in source_file or not _SAFE_SOURCE_FILE_RE.match(source_file):
        raise HTTPException(status_code=422, detail="Invalid source identifier")

    db = get_db()
    deleted = delete_user_source(db, source_file)
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"status": "ok", "deleted_chunks": deleted}


class FetchUrlRequest(BaseModel):
    url: str
    source_name: str = ""
    category: str = "Web Resource"


@app.post("/api/knowledge/fetch-url")
@_limiter.limit("10/minute")
async def fetch_url_knowledge(request: Request, req: FetchUrlRequest, _uid: str = Depends(require_auth)):  # noqa: ARG001
    """
    Ingest a public URL into Tier 2 knowledge via Jina AI Reader.

    Fetches the page as clean markdown, chunks it by section, embeds with
    gemini-embedding-2-preview, and writes to `user_knowledge`.

    Body: { url, source_name?, category? }
    Returns: { status, chunks_written, source_name, url, content_length }
    """
    from knowledge.user_docs import ingest_url_content

    if not _validate_external_url(req.url, require_https=True):
        raise HTTPException(
            status_code=422,
            detail="URL must be a public HTTPS address. Private/internal addresses are not allowed.",
        )

    result = ingest_url_content(
        url=req.url,
        source_name=req.source_name,
        category=req.category,
        jina_api_key=settings.jina_api_key,
    )

    if result["status"] == "error":
        logger.error("URL ingestion failed for %s: %s", req.url, result.get("error"))
        raise HTTPException(status_code=500, detail="Failed to ingest URL. Please try again.")

    return result


class IssueFeedbackRequest(BaseModel):
    session_id: str = Field(max_length=128)
    issue_index: int = Field(ge=0)
    element: str = Field(default="", max_length=200)
    severity: str = Field(default="", max_length=20)
    rule_citation: str = Field(default="", max_length=300)
    status: str = Field(max_length=20)       # "fixed" | "in_progress" | "wont_fix" | "open"
    time_to_action_ms: int | None = Field(default=None, ge=0)
    workspace_id: str | None = Field(default=None, max_length=128)


class ExportFigmaRequest(BaseModel):
    figma_url: str
    critique_report: dict


@app.post("/api/feedback")
@_limiter.limit("30/minute")
async def record_issue_feedback(
    request: Request,  # noqa: ARG001
    req: IssueFeedbackRequest,
    uid: str = Depends(require_auth),
):
    """
    Record designer feedback on a single critique issue.

    Writes to Firestore `issue_feedback` collection for downstream
    preference learning and RAG personalization.

    Body: {
      session_id, issue_index, element, severity, rule_citation,
      status,           // "fixed" | "in_progress" | "wont_fix" | "open"
      time_to_action_ms?,
      workspace_id?
    }
    Returns: { status: "ok" }
    """
    valid_statuses = {"fixed", "in_progress", "wont_fix", "open"}
    if req.status not in valid_statuses:
        raise HTTPException(status_code=422, detail=f"status must be one of: {sorted(valid_statuses)}")

    try:
        from knowledge.ingest import get_db
        db = get_db()
        db.collection("issue_feedback").add({
            "session_id": req.session_id,
            "user_id": uid,
            "issue_index": req.issue_index,
            "element": req.element,
            "severity": req.severity,
            "rule_citation": req.rule_citation,
            "status": req.status,
            "time_to_action_ms": req.time_to_action_ms,
            "workspace_id": req.workspace_id,
            "recorded_at": _now_iso(),
        })
        logger.info(
            "Issue feedback: session=%s idx=%d status=%s",
            req.session_id, req.issue_index, req.status,
        )
    except Exception as exc:
        # Feedback is best-effort — never fail the user
        logger.warning("Failed to record issue feedback: %s", exc)

    return {"status": "ok"}


@app.get("/api/eval-scores")
async def get_eval_scores(uid: str = Depends(require_auth)):
    """
    Return auto-eval quality scores for the most recent critiques.

    Reads from Firestore `critique_evals` collection (written by the background
    auto-eval task that fires after every RUN_FINISHED).

    Returns:
      {
        sessions: [ { session_id, scores, timestamp } ],  // last 20
        averages: { fix_specificity, severity_calibration, insight_depth,
                    rule_grounding, overall }  // across all user's evals
      }
    """
    try:
        from knowledge.ingest import get_db
        db = get_db()
        docs = (
            db.collection("critique_evals")
            .where("user_id", "==", uid)
            .limit(20)
            .get()
        )
        sessions = []
        totals: dict[str, float] = {
            "fix_specificity": 0.0, "severity_calibration": 0.0,
            "insight_depth": 0.0, "rule_grounding": 0.0, "overall": 0.0,
        }
        count = 0
        for doc in docs:
            data = doc.to_dict()
            scores = data.get("scores", {})
            sessions.append({
                "session_id": data.get("session_id", ""),
                "scores": scores,
                "timestamp": data.get("timestamp", "").isoformat()
                if hasattr(data.get("timestamp"), "isoformat") else str(data.get("timestamp", "")),
            })
            for k in totals:
                totals[k] += float(scores.get(k, 0.0))
            count += 1

        averages = {k: round(v / count, 3) for k, v in totals.items()} if count > 0 else totals
        return {"sessions": sessions, "averages": averages, "count": count}
    except Exception as exc:
        logger.warning("Failed to fetch eval scores: %s", exc)
        return {"sessions": [], "averages": {}, "count": 0}


@app.post("/api/sessions/{session_id}/export-figma-comments")
async def export_figma_comments(session_id: str, req: ExportFigmaRequest, _uid: str = Depends(require_auth)):  # noqa: ARG001
    """
    Post critique issues as Figma comments on the design frame.

    Converts every issue, flow issue, and trust/safety item into a concise
    Figma comment pinned to the node from the figma_url.  A summary comment
    is posted first.

    Returns: { posted, failed, total, comments: [{message, status, error?}] }
    """
    token = settings.figma_access_token
    if not token:
        raise HTTPException(status_code=503, detail="FIGMA_ACCESS_TOKEN not configured")

    match = re.search(r"/(?:design|file)/([A-Za-z0-9]+)", req.figma_url)
    file_key = match.group(1) if match else None
    if not file_key:
        raise HTTPException(status_code=422, detail="Could not parse file_key from figma_url")

    node_match = re.search(r"node-id=([^&]+)", req.figma_url)
    node_id = node_match.group(1).replace("-", ":") if node_match else None

    headers = {"X-Figma-Token": token, "Content-Type": "application/json"}
    report = req.critique_report

    # Build list of comment messages from all critique sections
    comments: list[str] = []

    # Summary header — use director_summary bullets (actionable) with frame context
    director_bullets: list = report.get("director_summary", [])
    frame_desc: str = report.get("frame_description", "")
    total_issues = len(report.get("issues", []))

    header_lines = ["Vera — Design Critique"]
    if frame_desc:
        header_lines.append(frame_desc)
    if director_bullets:
        header_lines.append("")
        for b in director_bullets[:3]:
            header_lines.append(f"• {b}")
    else:
        assessment = report.get("overall_assessment", "")
        if assessment:
            header_lines.append(assessment)
    header_lines.append(f"\n{total_issues} issue(s) — see thread for details.")
    comments.append("\n".join(header_lines)[:4000])

    # Element-level issues
    for item in report.get("issues", []):
        sev = (item.get("severity") or "low").upper()
        parts = [
            f"[{sev}] {item.get('element', '')}",
            item.get("issue", ""),
            f"Fix: {item.get('fix', '')}",
            f"Rule: {item.get('rule_citation', '')}",
        ]
        if item.get("wcag_sc"):
            parts.append(f"WCAG SC {item['wcag_sc']}")
        comments.append("\n".join(p for p in parts if p)[:4000])

    # Flow issues
    for item in report.get("flow_issues", []):
        msg = f"[FLOW] {item.get('element', '')}\n{item.get('issue', '')}\nFix: {item.get('fix', '')}"
        comments.append(msg[:4000])

    # Trust & safety
    for item in report.get("trust_safety", []):
        cat = (item.get("category") or "other").replace("_", " ").upper()
        msg = f"[{cat}] {item.get('element', '')}\n{item.get('issue', '')}\nFix: {item.get('fix', '')}"
        comments.append(msg[:4000])

    # Build Figma client_meta (pins comment to the node if we have one)
    client_meta: dict = {}
    if node_id:
        client_meta = {"node_id": node_id, "node_offset": {"x": 0, "y": 0}}

    results: list[dict] = []
    posted = 0
    failed = 0

    async with httpx.AsyncClient(timeout=15) as client:
        for message in comments:
            body: dict = {"message": message}
            if client_meta:
                body["client_meta"] = client_meta
            try:
                resp = await client.post(
                    f"{_FIGMA_BASE}/files/{file_key}/comments",
                    json=body,
                    headers=headers,
                )
                resp.raise_for_status()
                results.append({"message": message[:80], "status": "ok"})
                posted += 1
            except httpx.HTTPStatusError as exc:
                results.append({
                    "message": message[:80],
                    "status": "error",
                    "error": f"Figma {exc.response.status_code}: {exc.response.text[:120]}",
                })
                failed += 1
            except Exception as exc:
                results.append({"message": message[:80], "status": "error", "error": str(exc)[:120]})
                failed += 1

            await asyncio.sleep(0.35)  # stay within ~3 req/s Figma rate limit

    return {"posted": posted, "failed": failed, "total": len(comments), "comments": results}


@app.get("/api/knowledge/stats")
async def knowledge_stats():
    """
    Return knowledge base statistics by tier and category.
    """
    from knowledge.ingest import get_db
    from config import settings as cfg

    db = get_db()
    stats: dict = {"tier1": {}, "tier2": {}, "total_chunks": 0}

    try:
        tier1_docs = db.collection(cfg.firestore_collection_knowledge).select(["category"]).stream()
        tier1_counts: dict[str, int] = {}
        for doc in tier1_docs:
            cat = doc.to_dict().get("category", "Unknown")
            tier1_counts[cat] = tier1_counts.get(cat, 0) + 1
        stats["tier1"] = tier1_counts
        stats["total_chunks"] += sum(tier1_counts.values())
    except Exception as exc:
        stats["tier1_error"] = str(exc)

    try:
        tier2_docs = db.collection("user_knowledge").select(["category"]).stream()
        tier2_counts: dict[str, int] = {}
        for doc in tier2_docs:
            cat = doc.to_dict().get("category", "Unknown")
            tier2_counts[cat] = tier2_counts.get(cat, 0) + 1
        stats["tier2"] = tier2_counts
        stats["total_chunks"] += sum(tier2_counts.values())
    except Exception:
        pass  # Tier 2 collection may not exist yet

    return stats
