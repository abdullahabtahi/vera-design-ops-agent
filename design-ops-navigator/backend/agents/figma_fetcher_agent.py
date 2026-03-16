"""
FigmaFetcher Agent — fetches design data from Figma REST API.

Responsibilities:
- Reads the Figma URL from session state ({figma_url})
- Fetches node tree (components, styles, design tokens)
- Stores only the image URL (not base64) to avoid flooding session state

Output key: "figma_context" — JSON summary of design structure (no base64)
"""

import re

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext

from tools.figma_tools import get_figma_frame_image, get_figma_node_tree


async def _init_figma_url(callback_context: CallbackContext) -> None:
    """Ensure figma_url exists in session state to prevent template KeyError."""
    if "figma_url" not in callback_context.state:
        callback_context.state["figma_url"] = ""


async def _strip_figma_context_fences(callback_context: CallbackContext) -> None:
    """
    Strip markdown code fences from figma_context in session state.

    The LLM sometimes wraps its JSON output in ```json ... ``` despite instructions.
    This callback sanitizes figma_context before the critic agent interpolates it
    into its {figma_context} template — preventing corrupt prompt injection.
    """
    raw = callback_context.state.get("figma_context", "")
    if isinstance(raw, str) and raw.strip().startswith("```"):
        # Remove opening fence (```json or ```) and closing fence (```)
        cleaned = re.sub(r"^```[a-z]*\n?", "", raw.strip())
        cleaned = re.sub(r"\n?```$", "", cleaned.strip())
        callback_context.state["figma_context"] = cleaned.strip()

INSTRUCTION = """
You are the Figma Data Fetcher. Retrieve design data from the Figma URL provided.

## Figma URL
The URL to use is: {figma_url}

If {figma_url} is empty or not set, return {"error": "No Figma URL provided", "status": "error"}.

## Process
1. Call get_figma_node_tree with the figma_url above.
2. Call get_figma_frame_image with the figma_url above.
3. Return a compact JSON summary.

## IMPORTANT: Output format
Return ONLY this JSON (do NOT include image_base64 — the image is already in the conversation):
{{
  "file_key": "...",
  "node_id": "...",
  "file_name": "...",
  "components_found": 12,
  "styles_found": 8,
  "image_url": "...",
  "image_available": true,
  "node_tree_summary": {{
    "components": [{{"name": "Button/Primary", "key": "abc123"}}],
    "styles": {{"Primary/Blue": "FILL", "Body/Regular": "TEXT"}}
  }},
  "error": null
}}

If a call fails, set image_available: false and describe the error.
Return ONLY the JSON object — no surrounding text or markdown.
"""

figma_fetcher_agent = Agent(
    name="figma_fetcher_agent",
    model="gemini-2.5-flash",
    description=(
        "Fetches Figma design data: node tree (component names, styles, tokens) "
        "and frame image URL. The PNG is passed as inline multimodal input separately."
    ),
    instruction=INSTRUCTION,
    tools=[get_figma_node_tree, get_figma_frame_image],
    output_key="figma_context",
    before_agent_callback=_init_figma_url,
)
