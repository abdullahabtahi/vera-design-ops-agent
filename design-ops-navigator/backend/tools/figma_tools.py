"""
Figma tools for the FigmaFetcher agent.

Two tools:
  - get_figma_node_tree: GET /v1/files/{file_key} → structured component/style info
  - get_figma_frame_image: GET /v1/images/{file_key}?ids={node_id} → PNG base64

Auth: Figma Personal Access Token (PAT) via settings.figma_access_token.
"""

from __future__ import annotations

import re

import httpx

from config import settings

_FIGMA_BASE = "https://api.figma.com/v1"
_TIMEOUT = 30  # seconds


def _headers() -> dict[str, str]:
    return {"X-Figma-Token": settings.figma_access_token}


def _parse_url(figma_url: str) -> tuple[str, str | None]:
    """
    Parse a Figma URL into (file_key, node_id | None).

    Supports formats:
      https://www.figma.com/design/{file_key}/...?node-id={node_id}
      https://www.figma.com/file/{file_key}/...?node-id={node_id}
    """
    match = re.search(r"/(?:design|file)/([A-Za-z0-9]+)", figma_url)
    file_key = match.group(1) if match else None

    node_match = re.search(r"node-id=([^&]+)", figma_url)
    node_id = node_match.group(1).replace("-", ":") if node_match else None

    return file_key, node_id


def _extract_fill_colors(node: dict, out: dict, depth: int = 0, max_depth: int = 4) -> None:
    """
    Recursively walk a Figma node tree and collect SOLID fill colors.

    Populates `out` as {element_name: "#RRGGBB"}.
    Capped to max_depth levels and 30 unique entries to keep payload small.
    """
    if depth > max_depth or len(out) >= 30:
        return
    name = node.get("name", "")
    fills = node.get("fills", [])
    for fill in fills:
        if fill.get("type") == "SOLID" and "color" in fill and name and name not in out:
            c = fill["color"]
            r = int(round(c.get("r", 0) * 255))
            g = int(round(c.get("g", 0) * 255))
            b = int(round(c.get("b", 0) * 255))
            out[name] = f"#{r:02X}{g:02X}{b:02X}"
    for child in node.get("children", []):
        _extract_fill_colors(child, out, depth + 1, max_depth)


def get_figma_node_tree(figma_url: str) -> dict:
    """
    Fetch the Figma file node tree to extract component names, styles, and design tokens.

    Makes two Figma API calls:
      1. GET /v1/files/{file_key}?depth=2 — file-level component/style metadata
      2. GET /v1/files/{file_key}/nodes?ids={node_id}&depth=4 — frame-level color fills
         (only when a node_id is present in the URL)

    Use this to understand the design system structure before visual critique.

    Args:
        figma_url: Full Figma file URL, e.g.
                   "https://www.figma.com/design/AbC123/My-Design?node-id=1-2"
                   The file_key is extracted automatically.

    Returns:
        dict with keys:
          - status: "ok" or "error"
          - file_name: Figma file name
          - last_modified: ISO timestamp
          - components: list of top-level component names
          - styles: dict of style names → type (FILL, TEXT, EFFECT, GRID)
          - colors: dict of element names → hex color (e.g. {"Primary button": "#3B5BDB"})
          - node_id: parsed node_id from URL (if present)
          - file_key: parsed file key
    """
    if not settings.figma_access_token:
        return {"status": "error", "error": "FIGMA_ACCESS_TOKEN not configured in .env"}

    file_key, node_id = _parse_url(figma_url)
    if not file_key:
        return {"status": "error", "error": f"Could not parse file_key from URL: {figma_url}"}

    try:
        resp = httpx.get(
            f"{_FIGMA_BASE}/files/{file_key}",
            params={"depth": 2},
            headers=_headers(),
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as exc:
        return {"status": "error", "error": f"Figma API {exc.response.status_code}: {exc.response.text[:200]}"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}

    # Extract lightweight summary
    components = [
        {"name": v.get("name", ""), "key": k}
        for k, v in data.get("components", {}).items()
    ][:50]  # cap at 50

    styles = {
        v.get("name", k): v.get("styleType", "UNKNOWN")
        for k, v in data.get("styles", {}).items()
    }

    result: dict = {
        "status": "ok",
        "file_key": file_key,
        "node_id": node_id,
        "file_name": data.get("name", ""),
        "last_modified": data.get("lastModified", ""),
        "components": components,
        "styles": styles,
        "colors": {},
    }

    # Second call: fetch the specific frame's node tree to extract actual fill colors.
    # These hex values allow the critic agent to compute accurate WCAG contrast ratios.
    if node_id:
        try:
            node_resp = httpx.get(
                f"{_FIGMA_BASE}/files/{file_key}/nodes",
                params={"ids": node_id, "depth": 4},
                headers=_headers(),
                timeout=_TIMEOUT,
            )
            node_resp.raise_for_status()
            nodes_data = node_resp.json()
            colors: dict[str, str] = {}
            for node_data in nodes_data.get("nodes", {}).values():
                if node_data and "document" in node_data:
                    _extract_fill_colors(node_data["document"], colors)
            result["colors"] = colors
        except Exception:
            pass  # Non-fatal — critique continues without hex colors

    return result


def get_figma_frame_image(figma_url: str, scale: float = 2.0) -> dict:
    """
    Render a specific Figma frame as a PNG image (base64-encoded).

    Calls GET /v1/images/{file_key}?ids={node_id}&format=png&scale={scale}.
    The resulting base64 PNG is passed to Gemini multimodal for visual analysis.

    Args:
        figma_url: Figma URL with a node-id query parameter, e.g.
                   "https://www.figma.com/design/AbC123/My-Design?node-id=1-2"
                   The frame to render is identified by node-id.
        scale:     Export scale factor (1.0–4.0). Default 2.0 (2× for sharpness).

    Returns:
        dict with keys:
          - status: "ok" or "error"
          - file_key: str
          - node_id: str
          - image_base64: PNG data as base64 string (use with Gemini inline_data)
          - mime_type: "image/png"
          - image_url: direct S3 URL returned by Figma (available for ~1 hour)
    """
    if not settings.figma_access_token:
        return {"status": "error", "error": "FIGMA_ACCESS_TOKEN not configured in .env"}

    file_key, node_id = _parse_url(figma_url)
    if not file_key:
        return {"status": "error", "error": f"Could not parse file_key from URL: {figma_url}"}
    if not node_id:
        return {"status": "error", "error": "URL must include ?node-id=... to identify a specific frame"}

    scale = max(1.0, min(scale, 4.0))

    # Step 1: Get the image S3 URL from Figma
    try:
        resp = httpx.get(
            f"{_FIGMA_BASE}/images/{file_key}",
            params={"ids": node_id, "format": "png", "scale": scale},
            headers=_headers(),
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as exc:
        return {"status": "error", "error": f"Figma API {exc.response.status_code}: {exc.response.text[:200]}"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}

    images = data.get("images", {})
    # Figma returns node IDs with ":" replaced by "-" in some versions
    image_url = images.get(node_id) or images.get(node_id.replace(":", "-"))

    if not image_url:
        return {
            "status": "error",
            "error": f"No image returned for node_id={node_id}. Check node-id exists in file.",
            "available_ids": list(images.keys())[:5],
        }

    # Step 2: Download the PNG
    try:
        img_resp = httpx.get(image_url, timeout=30)
        img_resp.raise_for_status()
    except Exception as exc:
        return {"status": "error", "error": f"Failed to download PNG: {exc}"}

    return {
        "status": "ok",
        "file_key": file_key,
        "node_id": node_id,
        "image_url": image_url,
        "mime_type": "image/png",
        "size_bytes": len(img_resp.content),
        # image_base64 intentionally omitted — the PNG is already passed as inline_data
        # by the server pre-fetch. Including it here doubles the image in the session
        # history and causes the critic_agent context to overflow.
    }
