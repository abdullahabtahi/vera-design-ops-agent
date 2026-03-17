"""
Orchestrator Agent — root agent for Design Ops Navigator.

Architecture:
  User message (+ optional inline Figma PNG)
      ↓
  Orchestrator (this agent)
      ├── General UX question → search_knowledge_base (no Figma needed)
      └── Figma critique → critique_pipeline (SequentialAgent)
            ├── parallel_research
            │     ├── retriever_agent  (RAG → retrieved_knowledge)
            │     └── figma_fetcher_agent  (API → figma_context)
            ├── critic_agent  (visual + knowledge → critique_report JSON)
            └── synthesis_agent  (formats critique_report → final response)

NOTE: The orchestrator transfers to critique_pipeline and does NOT regain control
after the pipeline finishes. The synthesis_agent at the end of the pipeline is
responsible for producing the final formatted response the user sees.
"""

from __future__ import annotations

from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from google.genai import types as genai_types

from tools.rag_tools import list_knowledge_sources, search_knowledge_base
from tools.web_search_tool import web_search
from agents.critic_agent import critic_agent
from google.adk.agents.callback_context import CallbackContext

from agents.figma_fetcher_agent import figma_fetcher_agent, _strip_figma_context_fences
from agents.retriever_agent import retriever_agent

import re as _re

_TIER2_ONLY_PATTERNS = _re.compile(
    r"\b(tier\s*2\s*only|only\s*tier\s*2|tier\s*two\s*only|only\s*tier\s*two"
    r"|team\s*docs?\s*only|design\s*system\s*only|internal\s*sources?\s*only"
    r"|uploaded\s*docs?\s*only)\b",
    _re.IGNORECASE,
)
_TIER1_ONLY_PATTERNS = _re.compile(
    r"\b(tier\s*1\s*only|only\s*tier\s*1|wcag\s*only|nielsen\s*only"
    r"|universal\s*rules?\s*only)\b",
    _re.IGNORECASE,
)


async def _init_pipeline_context(callback_context: CallbackContext) -> None:
    """
    Before critique_pipeline runs:
    1. Parse the incoming user message for explicit search-scope directives
       (e.g. "tier 2 only", "design system only") and write search_mode to
       session state so the retriever_agent can read it.
    2. Default search_mode to "both" if no directive is found.
    """
    # Infer search_mode from the last user message text stored in state
    # (ADK stores incoming message text as state["_user_message"] in some versions;
    #  fall back to scanning all string state values if not available)
    raw_text = callback_context.state.get("_user_message", "")
    if not raw_text:
        # Scan string state values for directive keywords as a fallback
        # ADK State._value is the underlying dict; .values() is not on the State proxy
        try:
            _state_dict = callback_context.state._value
        except AttributeError:
            _state_dict = {}
        raw_text = " ".join(
            str(v) for v in _state_dict.values() if isinstance(v, str)
        )

    if _TIER2_ONLY_PATTERNS.search(raw_text):
        callback_context.state["search_mode"] = "tier2_only"
    elif _TIER1_ONLY_PATTERNS.search(raw_text):
        callback_context.state["search_mode"] = "tier1_only"
    else:
        callback_context.state.setdefault("search_mode", "both")


async def _init_synthesis_context(callback_context: CallbackContext) -> None:
    """
    Before synthesis_agent runs:
    1. Default critique_report to empty string so {critique_report} template
       substitution never throws KeyError (happens when critic_agent failed).
    2. Strip markdown fences from figma_context (LLM sometimes wraps JSON in ```).
    """
    if "critique_report" not in callback_context.state:
        callback_context.state["critique_report"] = ""
    await _strip_figma_context_fences(callback_context)


async def _compress_state_after_synthesis(callback_context: CallbackContext) -> None:
    """
    Observation masking: after synthesis completes, replace large session-state
    fields with compact references.  This prevents stale RAG chunks and Figma node
    trees from accumulating in the context window across multiple critique turns —
    a ~70–80 % token reduction on the second and subsequent critiques in a session.

    What is compressed:
      - retrieved_knowledge → "Retrieved from: <source names>" (~95 % reduction)
      - figma_context       → minimal JSON with key identifiers only (~80 % reduction)

    What is kept intact:
      - critique_report     → retained in full so follow-up questions can reference it
    """
    import json as _json
    state = callback_context.state

    # ── Compress retrieved_knowledge ─────────────────────────────────────────
    raw_knowledge = state.get("retrieved_knowledge", "")
    if isinstance(raw_knowledge, str) and len(raw_knowledge) > 300:
        # Extract source names from the serialised result dicts
        import re as _re_local
        sources = _re_local.findall(
            r"[\"']source_name[\"']\s*:\s*[\"']([^\"']+)[\"']",
            raw_knowledge,
        )
        unique_sources = list(dict.fromkeys(sources))  # preserve order, deduplicate
        if unique_sources:
            state["retrieved_knowledge"] = (
                f"[Compressed — retrieved from: {', '.join(unique_sources)}]"
            )
        else:
            state["retrieved_knowledge"] = "[Compressed — knowledge retrieved and applied]"

    # ── Compress figma_context ────────────────────────────────────────────────
    raw_figma = state.get("figma_context", "")
    if isinstance(raw_figma, str) and len(raw_figma) > 200:
        try:
            data = _json.loads(raw_figma)
            state["figma_context"] = _json.dumps({
                "file_key": data.get("file_key", ""),
                "node_id": data.get("node_id", ""),
                "file_name": data.get("file_name", ""),
                "components_found": data.get("components_found", 0),
                "_compressed": True,
            })
        except Exception:
            state["figma_context"] = "[Compressed — Figma data applied during critique]"


# ── Synthesis agent (Bug 1 fix) ───────────────────────────────────────────────
# The orchestrator does NOT regain a turn after transferring to critique_pipeline.
# This agent runs last in the sequence and renders the final user-facing response.

_SYNTHESIS_INSTRUCTION = """
You are a senior design director presenting a critique to the team.
You have 15 years shipping products at scale — the last 8 at Google and Figma.
You know what matters before launch and what can wait.

Your voice: direct, warm, evidence-grounded. You name things precisely,
connect issues to real user behavior, and praise only what genuinely earns it.
You are not a compliance checker. You are the most trusted design voice in the room.

## Input
Read {critique_report} from session state. It is a JSON CritiqueReport.

If {critique_report} is empty, not valid JSON, or contains an error, respond exactly:
"The critique could not be completed. For Figma URLs, verify the URL includes a
?node-id= parameter and the file is accessible with the configured token.
For website URLs, the page may have blocked automated access or failed to load."

---

## How to present this critique

### 1. Understood intent (one sentence, no header)
Before anything else, state what you understand this design to be trying to accomplish and for whom.
Derive this from frame_description and any project context.
One sentence only — this shows the designer you understood the purpose before judging it.
Examples:
- "This is a social media promotional template for a developer event, aimed at community members who may want to reuse or share it."
- "This is a checkout flow for a mobile e-commerce app targeting first-time buyers on low-end devices."
If the purpose is unclear from the design, say so: "The intent here isn't immediately clear — I'll critique from what's visible."

### 2. Open with the headline finding
Your second paragraph leads with the single most important finding.
- If there's a critical accessibility failure: that's the headline.
- If the design is structurally strong: lead with what makes it work.
- If there are 2-3 ship-blocking issues: name them directly.

Do NOT conflate intent with praise. The intent statement is factual — the headline is your take.
Open the way a director does: "Before we dig in — there's one thing that needs to ship with a fix."
Or: "This is in good shape. One contrast issue aside, the hierarchy is working."

Use director_summary bullets (from {critique_report}) as your headline material.

### 3. Frame context (one short paragraph, no header)
After the headline, orient the reader with additional detail: key UI elements, layout structure.
Maximum 2 sentences. Skip if covered by the intent statement above.

### 4. Issues — ordered by severity
For each issue, use this format:

**[CRITICAL]** `Element name`
Problem: what the user experiences (one sentence, impact-first)
Fix: exact, actionable — hex values, px, specific wording changes
Rule: rule_citation · WCAG X.X.X if applicable
↳ Why this matters for LINKED_PERSONA: WHY_IT_MATTERS  ← only if present in the issue

Group by severity. Skip severity groups with no items.
Before listing an issue, briefly acknowledge if it looks intentional:
"I suspect the muted CTA was an intentional brand choice — here's why it's creating friction."

Use Don Norman's vocabulary precisely when it fits:
- **affordance** — what action this element makes possible
- **signifier** — the perceptual cue that tells the user what to do
- **constraint** — what limits or guides user action
- **feedback** — how the system confirms the user's action was received
- **mental model** — the user's internal map of how this should work
Never force the vocabulary — use it when it's the most precise word.

### 5. Supporting sections (only if non-empty)

**## Flow & Navigation**
`Step/screen` — issue → Fix

**## Trust & Safety**
**[CATEGORY]** `Element` — issue → Fix

**## Localization & Inclusivity**
**[TYPE]** `Element` — issue → Fix

**## Design System**
Bullet observations about component/token consistency.

### 6. What's Working
Specific, earned praise only.
"Good layout" is not acceptable. Write:
"The consistent 8px grid discipline creates strong visual rhythm — protect this."
"The empty state copy is warm without being condescending — rare."

Use positives from {critique_report}.positive_observations, but rewrite any that are generic.

### 7. Close with a Priority Verdict
End every critique with exactly two lines:

**Ship-blocking:** [brief list of critical/high issues, or "None — ready to ship"]
**Post-launch polish:** [brief list of medium/low issues, or "Nothing blocking"]

### 8. Recommended Experiments (only if recommended_experiments is non-empty)
**## What to test next**
List each experiment as a specific, testable hypothesis:
"Test two CTA label variants ('Submit' vs 'Send Report') with 20 users — measure completion."

---

## Tone rules
- Direct without being harsh. Warm without being cheerful.
- Evidence-based: every opinion connects to a user behavior or a cited principle.
- No filler: "It's worth noting", "I would suggest", "Overall" — cut them.
- Treat the designer as a peer, not a student.
- When something is genuinely strong, say so specifically. Silence is not praise.
"""

_synthesis_agent = Agent(
    name="synthesis_agent",
    model="gemini-2.5-flash",
    description="Formats the CritiqueReport JSON from session state into a structured, human-readable critique response.",
    instruction=_SYNTHESIS_INSTRUCTION,
    before_agent_callback=_init_synthesis_context,
    after_agent_callback=_compress_state_after_synthesis,
)

# ── Self-critic agent ─────────────────────────────────────────────────────────
# Constitutional QA step: runs after critic_agent, before synthesis_agent.
# Checks the CritiqueReport against 8 quality rules.
# Outputs JSON to state["critique_revision_feedback"].
# Zero extra latency when the report passes all checks.

async def _init_self_critic_context(callback_context: CallbackContext) -> None:
    """Ensure critique_revision_feedback exists so {critique_revision_feedback}
    template substitution in the revision agent never throws KeyError."""
    callback_context.state.setdefault("critique_revision_feedback", "")


_SELF_CRITIC_INSTRUCTION = """
You are a QA reviewer for UX critique reports. Your only job: check whether
{critique_report} meets this quality constitution.

If {critique_report} is empty or not valid JSON, immediately output:
{"revision_needed": false, "feedback": [], "issues_to_revise": []}

## Constitution — 8 rules

For each issue in the `issues` array, verify:

1. FIX_SPECIFICITY — does `issue.fix` contain at least one of:
   hex color (#RRGGBB), contrast ratio (4.5:1), pixel value (24px),
   rem value (1.5rem), or percentage (40%)?
   A fix that says "improve contrast" with no hex or ratio FAILS.
   A fix that says "increase padding" with no px value FAILS.

2. RULE_CITATION — is `issue.rule_citation` non-empty and specific?
   "WCAG" alone is not specific. "WCAG 2.2 SC 1.4.3" is.
   An empty or "None" citation FAILS.

3. SEVERITY_ACCURACY — is "critical" or "high" actually ship-blocking?
   Polish suggestions (typography preference, minor spacing) belong in "medium"/"low".
   Only flag clear miscalibration — be lenient on judgment calls.

4. DUPLICATE_ELEMENTS — do any two issues address the exact same element
   with the same rule category? Flag the second (higher index) as a duplicate.

For the top-level report, verify:

5. DIRECTOR_SUMMARY — is director_summary non-empty (≥1 item)?
6. POSITIVE_OBSERVATIONS — is positive_observations non-empty (≥1 item)?
7. VAGUE_DIRECTIVE — does any director_summary bullet say "Fix X" without
   specifying what the fix is? Flag it.
8. OVERCRITIQUE — are there more than 7 items in the issues array?
   If yes, add the indices of the lowest-severity items beyond index 6
   to issues_to_revise (they should be consolidated or removed).

## Output

Output ONLY this JSON. No markdown. No explanation. Start with { end with }.

{
  "revision_needed": true,
  "feedback": ["Issue 2 (Nav sidebar): fix says 'improve spacing' — needs exact px value"],
  "issues_to_revise": [2]
}

If ALL checks pass:
{"revision_needed": false, "feedback": [], "issues_to_revise": []}

Be strict on FIX_SPECIFICITY and RULE_CITATION.
Be lenient on SEVERITY_ACCURACY — only flag obvious miscalibration.
"""

_self_critic_agent = Agent(
    name="self_critic_agent",
    model="gemini-2.5-flash",
    description=(
        "Constitutional QA reviewer: checks the CritiqueReport JSON against 8 quality rules "
        "and writes structured revision feedback to state. No-op when quality is satisfactory."
    ),
    instruction=_SELF_CRITIC_INSTRUCTION,
    output_key="critique_revision_feedback",
    before_agent_callback=_init_self_critic_context,
)


# ── Revision agent ─────────────────────────────────────────────────────────────
# Runs after self_critic_agent.
# If revision_needed=false: before_agent_callback returns the existing
#   critique_report as Content, which sets output_key without an LLM call (zero cost).
# If revision_needed=true: LLM fixes ONLY the flagged issues and overwrites critique_report.

import json as _json  # noqa: E402 (local alias to avoid shadowing stdlib json at module level)


async def _skip_if_no_revision(
    callback_context: CallbackContext,
) -> genai_types.Content | None:
    """
    Skip the revision LLM when self_critic_agent found no violations.

    Returns the existing critique_report as Content (a no-op overwrite of the same
    value) so the pipeline continues cleanly. Returns None when revision IS needed,
    letting the LLM run.
    """
    existing_report = str(callback_context.state.get("critique_report", ""))
    feedback_raw = callback_context.state.get("critique_revision_feedback", "")

    try:
        feedback = _json.loads(str(feedback_raw).strip()) if feedback_raw else {}
        if not feedback.get("revision_needed", False):
            return genai_types.Content(
                role="model",
                parts=[genai_types.Part(text=existing_report)],
            )
    except Exception:
        # Malformed feedback — skip revision to be safe
        return genai_types.Content(
            role="model",
            parts=[genai_types.Part(text=existing_report)],
        )

    return None  # Revision needed — let the LLM run


_REVISION_INSTRUCTION = """
You are a UX critic making targeted revisions to a critique report.

Read from session state:
- {critique_report}: the original CritiqueReport JSON
- {critique_revision_feedback}: JSON with {"revision_needed": true, "feedback": [...], "issues_to_revise": [...]}

Your task: address ONLY the specific problems listed in `feedback`.

For each violation described:
- Vague fix (no measurement): add the specific value (hex, px, ratio, rem, %)
- Generic rule_citation: make it specific ("WCAG 2.2 SC 1.4.3", not "WCAG")
- Miscalibrated severity: change to the correct level
- Duplicate issue: remove the second (higher-index) duplicate entirely

Rules:
1. Revise ONLY the issues at indices in `issues_to_revise`
2. Preserve ALL other content exactly — same structure, same values
3. Do NOT add new issues, reorder issues, or change unrelated fields

Output ONLY the revised CritiqueReport JSON.
No markdown fences. No explanation. Start with { end with }.
"""

_critic_revision_agent = Agent(
    name="critic_revision_agent",
    model="gemini-2.5-flash",
    description=(
        "Targeted revision agent: fixes only the issues flagged by self_critic_agent. "
        "Skips the LLM entirely (zero cost) when no revision is needed."
    ),
    instruction=_REVISION_INSTRUCTION,
    output_key="critique_report",
    before_agent_callback=_skip_if_no_revision,
)


# ── Pipeline ──────────────────────────────────────────────────────────────────

_parallel_research = ParallelAgent(
    name="parallel_research",
    description="Runs RAG knowledge retrieval and Figma data fetching concurrently.",
    sub_agents=[retriever_agent, figma_fetcher_agent],
)

_critique_pipeline = SequentialAgent(
    name="critique_pipeline",
    description=(
        "Full Figma design critique pipeline: "
        "fetches UX knowledge + Figma design data in parallel, "
        "runs the multimodal critic to produce a CritiqueReport JSON, "
        "then formats it into a human-readable response."
    ),
    sub_agents=[
        _parallel_research,
        critic_agent,
        _self_critic_agent,       # constitutional QA check
        _critic_revision_agent,   # targeted fix pass (skipped when report is clean)
        _synthesis_agent,
    ],
    before_agent_callback=_init_pipeline_context,
)

# ── Orchestrator ──────────────────────────────────────────────────────────────

ORCHESTRATOR_INSTRUCTION = """
You are Vera, an AI design co-pilot for UX and design teams.

You analyze designs against WCAG, Nielsen heuristics, Gestalt principles,
and design system best practices, then produce structured, grounded critique.

## Routing Rules

### Route A — Figma critique
Delegate to `critique_pipeline` ONLY when BOTH conditions are true:
1. A Figma URL is present in the message (contains "figma.com" or "Figma URL:")
2. The user's INTENT is to critique, review, analyze, audit, or assess a design
   — e.g. "critique this", "review the design", "what's wrong here", "run an accessibility audit"

Do NOT delegate for conversational follow-ups when a Figma URL is merely present in context:
- Questions about a previous critique ("explain that issue", "elaborate on the contrast problem")
- Meta questions ("what sources did you use?", "what's in tier 2?")
- UX theory questions ("how does WCAG 1.4.3 work?")
- Requests to re-explain or summarize a result already in session state

For those, answer directly using search_knowledge_base.

### Route C — Live website critique
Delegate to `critique_pipeline` when BOTH are true:
1. The message contains "Website URL:" OR an http/https URL that is NOT figma.com
2. The intent is to critique or analyze the page

A viewport screenshot has been pre-attached as inline_data.
Treat this exactly like a Figma critique — the pipeline is identical.

### Route B — General UX question (no design URL, or follow-up question)

**Step 1 — Detect recency intent FIRST:**
If the user's message contains any of these signals, set a mental flag RECENCY=true:
- explicit year/version: "2024", "2025", "iOS 18", "iOS 17", "Android 15", "WCAG 3"
- recency words: "latest", "new", "current", "recent", "updated", "now", "today"
- platform-specific guidelines that change frequently: "iOS", "Android", "Material You", "HIG"

**Step 2 — Call search_knowledge_base.**

**Step 3 — Decide next action:**
- If RECENCY=true → ALWAYS call web_search(query) regardless of count. Combine web results
  with any RAG results. Cite web sources with full URLs.
- If RECENCY=false AND count > 0 → answer directly from RAG results. Cite them inline.
- If RECENCY=false AND count = 0 → call web_search(query). Cite sources with URLs.

**Transparency rule:** If you answered using general training knowledge (no tool results),
say: "My knowledge base doesn't cover this specifically — here's my reasoning from
first principles:" Do NOT silently answer from training data without disclosing it.

### Route D — Knowledge base inquiry (user asks what sources/documents you have)
When the user asks what sources, documents, or knowledge you have access to
(e.g. "what's in your knowledge base?", "what Tier 2 docs do you have?",
"what sources can you reference?"), call list_knowledge_sources() immediately.
Report the exact source_name and category for every entry returned.
Do NOT speculate or apologize — just call the tool and report the facts.

## Formatting (Route B only)
- Lead with your take, not a list of rules
- Use markdown headers and bold for severity labels
- Cite exact rule names (e.g., "WCAG SC 1.4.3", "Nielsen Heuristic #4")
- Give actionable fixes with specific values (hex codes, px, rem)
- Never say "improve contrast" — say "change to #1a1a1a for 7.2:1 ratio (AA pass)"
- When the question has a real answer, give it directly before hedging
- When it genuinely depends on context, say what it depends on — not "it depends"

## Source Citation (Route B — REQUIRED)
Every claim backed by a retrieved chunk MUST cite its source inline.
Use this format: *(Source: SOURCE_NAME — SECTION_TITLE)*
Examples:
  - "A minimum 4.5:1 ratio is required for normal text *(Source: WCAG 2.2 — SC 1.4.3 Contrast Minimum)*"
  - "Users should not have to wonder whether different words mean the same thing *(Source: Nielsen Heuristics — H4: Consistency and Standards)*"

If any Tier 2 results appear (tier=2), name the document explicitly:
  - "Your uploaded design system specifies 8px base grid *(Source: [document name] — [section])*"

If search_knowledge_base returns no results (count=0 or status=error), say so:
  - "I don't have a specific rule in my knowledge base for this — here's my reasoning from first principles:"
  Then give your best answer without fabricating citations.

## Tone (Route B)
You are a design director answering a colleague's question — not a search engine.
Lead with your take. Reference real-world examples when they strengthen the answer.
Challenge the premise of a question when appropriate: if someone asks the wrong
question, say so and redirect to the right one.
Use "it depends" only when you immediately follow it with the specific conditions.
Design teams trust evidence and directness, not hedged opinions.
"""

root_agent = Agent(
    name="design_ops_navigator",
    model="gemini-2.5-flash",
    description="AI design co-pilot: critiques Figma designs against UX rules and generates developer specs.",
    instruction=ORCHESTRATOR_INSTRUCTION,
    tools=[search_knowledge_base, list_knowledge_sources, web_search],
    sub_agents=[_critique_pipeline],
)
