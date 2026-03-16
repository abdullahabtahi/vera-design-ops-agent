"""
Critic tools — structured output schemas and the dev spec generator.

These are used by the Critic agent to produce grounded, actionable UX critique
and developer-ready specifications.

The CritiqueReport Pydantic schema is the single source of truth for all
structured critique output. Every field has a rule citation requirement.
"""

from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field


# ── Critique JSON Schema ───────────────────────────────────────────────────────


class CritiqueItem(BaseModel):
    """A single design issue, grounded in a specific UX rule."""

    severity: Literal["critical", "high", "medium", "low"] = Field(
        description=(
            "critical: breaks usability or accessibility (WCAG failure, unusable flow). "
            "high: violates team design system or major UX principle. "
            "medium: UX best practice gap (not blocking). "
            "low: polish / suggestion."
        )
    )
    rule_citation: str = Field(
        description=(
            "Exact rule name from the knowledge base. "
            "E.g. 'WCAG 2.2 SC 1.4.3 Contrast (Minimum) — AA', "
            "'Nielsen Heuristic 1: Visibility of System Status', "
            "'Fitts\\'s Law — Target Size'."
        )
    )
    element: str = Field(
        description="The specific UI element affected. E.g. 'Primary CTA button', 'Navigation sidebar'."
    )
    issue: str = Field(
        description="Clear, specific description of the problem."
    )
    fix: str = Field(
        description=(
            "Actionable, specific fix. Never vague. "
            "E.g. 'Change text color from #A0A0A0 to #767676 (achieves 4.52:1 on white, WCAG AA)' "
            "rather than 'improve contrast'."
        )
    )
    wcag_sc: str | None = Field(
        default=None,
        description="WCAG Success Criterion number if applicable. E.g. '1.4.3', '2.4.7'."
    )
    linked_goal: str | None = Field(
        default=None,
        description="The project goal this issue blocks. E.g. 'Submit report in under 60 seconds'."
    )
    linked_persona: str | None = Field(
        default=None,
        description="The persona most impacted. E.g. 'Stressed resident, low tech literacy'."
    )
    why_it_matters: str | None = Field(
        default=None,
        description=(
            "1-sentence explanation of real-world impact for this specific persona/context. "
            "E.g. 'Under stress, users have 40% reduced cognitive capacity — 8 options causes abandonment.'"
        )
    )


class FlowIssue(BaseModel):
    """A navigation, information architecture, or user-flow problem."""

    element: str = Field(description="The flow step or screen affected. E.g. 'Hazard reporting — Step 2 of 4'.")
    issue: str = Field(description="The specific flow problem.")
    fix: str = Field(description="Actionable fix.")
    linked_goal: str | None = Field(default=None, description="Goal this issue blocks.")
    linked_persona: str | None = Field(default=None, description="Persona most impacted.")


class TrustSafetyItem(BaseModel):
    """A trust, error-recovery, or safety-critical design concern."""

    category: Literal["error_state", "confirmation", "data_privacy", "emergency_affordance", "other"] = Field(
        description="Type of trust/safety concern."
    )
    element: str = Field(description="The UI element or screen affected.")
    issue: str = Field(description="The trust or safety problem.")
    fix: str = Field(description="Actionable fix.")


class LocalizationItem(BaseModel):
    """An inclusivity, localization, or accessibility-beyond-WCAG concern."""

    type: Literal["rtl", "text_expansion", "cultural_color", "age_accessibility", "language_clarity", "other"] = Field(
        description="Type of localization/inclusivity concern."
    )
    element: str = Field(description="The UI element affected.")
    issue: str = Field(description="The inclusivity problem.")
    fix: str = Field(description="Actionable fix.")


class CritiqueReport(BaseModel):
    """
    Full structured critique of a Figma frame.

    Produced by the Critic agent. All items must be grounded in knowledge base rules.
    """

    frame_description: str = Field(
        description="One-paragraph description of what the analyzed frame shows (layout, purpose, key UI elements)."
    )
    overall_assessment: str = Field(
        description="2–3 sentence overall quality assessment before listing specific issues."
    )
    issues: list[CritiqueItem] = Field(
        description="List of specific design issues, ordered by severity (critical first)."
    )
    design_system_notes: list[str] = Field(
        default_factory=list,
        description="Observations about design system consistency (component usage, token adherence)."
    )
    positive_observations: list[str] = Field(
        default_factory=list,
        description="Things the design does well — for balance and morale."
    )
    flow_issues: list[FlowIssue] = Field(
        default_factory=list,
        description="Navigation, IA, and user-flow problems not captured in per-element issues."
    )
    trust_safety: list[TrustSafetyItem] = Field(
        default_factory=list,
        description="Error states, confirmations, data privacy signals, and emergency affordances."
    )
    localization_inclusivity: list[LocalizationItem] = Field(
        default_factory=list,
        description="RTL, text expansion, cultural color meaning, age accessibility, language clarity."
    )
    context_alignment_score: Literal["strong", "partial", "misaligned"] | None = Field(
        default=None,
        description=(
            "How well the design serves the stated project goal and persona. "
            "strong: design directly enables the goal; partial: some gaps; misaligned: design works against goal."
        )
    )
    context_alignment_notes: str | None = Field(
        default=None,
        description="1-2 sentences explaining the alignment score. Omit if no project context was provided."
    )
    director_summary: list[str] = Field(
        default_factory=list,
        description=(
            "3 imperative bullets a design director would say in the first minute of review. "
            "Each bullet names one ship-blocking or structurally important finding. "
            "Written as direct commands: 'Fix the CTA contrast before this ships — it fails WCAG AA.' "
            "Never generic. Never praise-only. Max 3 items."
        )
    )
    recommended_experiments: list[str] = Field(
        default_factory=list,
        description=(
            "2-3 specific next actions a team should run: A/B tests, user research sessions, "
            "prototype validations, or data pulls that would resolve current design uncertainties. "
            "Each item names the hypothesis and the method: "
            "'Test two CTA label variants (\"Submit\" vs \"Send Report\") with 50 users — measure completion rate.' "
            "Omit if the design is straightforward with no open questions."
        )
    )

    class Config:
        json_schema_extra = {
            "example": {
                "frame_description": "Login screen with email/password fields and a primary CTA button.",
                "overall_assessment": "The layout follows a clear visual hierarchy. Two accessibility issues require attention before launch.",
                "issues": [
                    {
                        "severity": "critical",
                        "rule_citation": "WCAG 2.2 SC 1.4.3 Contrast (Minimum) — AA",
                        "element": "Placeholder text in email input",
                        "issue": "Placeholder text #A8A8A8 on white (#FFFFFF) achieves 2.32:1 — fails WCAG AA (4.5:1 minimum).",
                        "fix": "Change placeholder color to #767676 or darker (achieves 4.54:1 on white).",
                        "wcag_sc": "1.4.3"
                    }
                ],
                "design_system_notes": ["CTA button uses correct Primary/500 token."],
                "positive_observations": ["Clear single-column layout reduces cognitive load (Hick's Law)."]
            }
        }


# ── Dev Spec generator ─────────────────────────────────────────────────────────


class ComponentSpec(BaseModel):
    """Developer-ready spec for a single UI component."""
    component: str
    figma_node_id: str | None = None
    width: str | None = None
    height: str | None = None
    colors: dict[str, str] = Field(default_factory=dict)
    typography: dict[str, str] = Field(default_factory=dict)
    spacing: dict[str, str] = Field(default_factory=dict)
    accessibility_requirements: list[str] = Field(default_factory=list)
    notes: str = ""


class DevSpec(BaseModel):
    """Full developer handoff specification for a Figma frame."""
    frame_name: str
    figma_url: str
    components: list[ComponentSpec] = Field(default_factory=list)
    design_tokens_used: dict[str, str] = Field(default_factory=dict)
    interaction_notes: list[str] = Field(default_factory=list)
    accessibility_checklist: list[str] = Field(default_factory=list)


# ── Tool functions ─────────────────────────────────────────────────────────────


def parse_critique_json(raw_json: str) -> dict:
    """
    Validate and parse a raw JSON string into a CritiqueReport.

    Use this after the Critic LLM produces JSON output to ensure schema compliance
    before returning to the user or Orchestrator.

    Args:
        raw_json: JSON string conforming to CritiqueReport schema.

    Returns:
        dict with keys:
          - status: "ok" or "error"
          - report: validated CritiqueReport as dict (if ok)
          - issue_count: total number of issues
          - critical_count: number of critical issues
          - error: validation error message (if error)
    """
    try:
        data = json.loads(raw_json)
        report = CritiqueReport(**data)
    except json.JSONDecodeError as exc:
        return {"status": "error", "error": f"Invalid JSON: {exc}"}
    except Exception as exc:
        return {"status": "error", "error": f"Schema validation failed: {exc}"}

    report_dict = report.model_dump()
    critical_count = sum(1 for i in report.issues if i.severity == "critical")

    # Non-blocking quality check — adds warnings but never suppresses the critique
    quality = check_critique_quality(report_dict)

    return {
        "status": "ok",
        "report": report_dict,
        "issue_count": len(report.issues),
        "critical_count": critical_count,
        "quality_warnings": quality["warnings"],
        "gaming_risk": quality["gaming_risk"],
        "vague_fix_indices": quality["vague_fix_indices"],
    }


def get_critique_schema() -> dict:
    """
    Return the CritiqueReport JSON schema for use in Gemini structured output prompts.

    The Critic agent calls this to get the exact schema to inject into its
    system prompt, ensuring Gemini outputs valid CritiqueReport JSON.

    Returns:
        dict with keys:
          - status: "ok"
          - schema: JSON schema dict for CritiqueReport
          - schema_json: JSON string of the schema (for direct prompt injection)
    """
    # Return only the JSON string — never the raw dict with $defs references.
    # Gemini treats function response dicts as potential schemas and chokes on $defs.
    schema = CritiqueReport.model_json_schema()
    return {
        "status": "ok",
        "schema_json": json.dumps(schema, indent=2),
    }


def compute_contrast_ratio(foreground_hex: str, background_hex: str) -> dict:
    """
    Compute the WCAG 2.2 contrast ratio between two hex colors.

    Uses the official WCAG relative luminance formula (IEC 61966-2-1).
    Call this whenever you have actual hex color values from the Figma node tree
    instead of visually estimating contrast — visual estimation is inaccurate.

    Args:
        foreground_hex: Foreground (text/element) color as hex, e.g. "#A8A8A8" or "A8A8A8".
        background_hex: Background color as hex, e.g. "#FFFFFF" or "FFFFFF".

    Returns:
        dict with keys:
          - status: "ok" or "error"
          - ratio: float contrast ratio (e.g. 4.54)
          - ratio_display: formatted string (e.g. "4.54:1")
          - passes_aa_normal: bool — ≥4.5:1 (WCAG AA normal text, SC 1.4.3)
          - passes_aa_large: bool — ≥3.0:1 (WCAG AA large text, SC 1.4.3)
          - passes_aaa_normal: bool — ≥7.0:1 (WCAG AAA normal text, SC 1.4.6)
          - passes_aaa_large: bool — ≥4.5:1 (WCAG AAA large text, SC 1.4.6)
          - foreground_hex: normalized input
          - background_hex: normalized input
    """
    def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
        h = hex_color.lstrip("#")
        if len(h) != 6:
            raise ValueError(f"Invalid hex color: {hex_color!r}")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def _relative_luminance(r: int, g: int, b: int) -> float:
        def _linearize(c: int) -> float:
            s = c / 255.0
            return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
        return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)

    try:
        fg_rgb = _hex_to_rgb(foreground_hex)
        bg_rgb = _hex_to_rgb(background_hex)
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}

    l1 = _relative_luminance(*fg_rgb)
    l2 = _relative_luminance(*bg_rgb)
    lighter, darker = max(l1, l2), min(l1, l2)
    ratio = round((lighter + 0.05) / (darker + 0.05), 2)

    return {
        "status": "ok",
        "ratio": ratio,
        "ratio_display": f"{ratio}:1",
        "passes_aa_normal": ratio >= 4.5,
        "passes_aa_large": ratio >= 3.0,
        "passes_aaa_normal": ratio >= 7.0,
        "passes_aaa_large": ratio >= 4.5,
        "foreground_hex": foreground_hex.upper().lstrip("#"),
        "background_hex": background_hex.upper().lstrip("#"),
    }


# ── Anti-gaming quality checks ─────────────────────────────────────────────────

# A "measurement token" makes a fix actionable — hex color, contrast ratio,
# pixel/rem/percent/dp value.  A fix string lacking any such token is vague.
_MEASUREMENT_RE = re.compile(
    r"(#[0-9a-fA-F]{3,6}"         # hex color: #A0A0A0
    r"|\d+(?:\.\d+)?:\d+(?:\.\d+)?"  # contrast ratio: 4.5:1
    r"|\d+\s*px"                   # pixel value: 24px
    r"|\d+\s*rem"                  # rem value: 1.5rem
    r"|\d+\s*%"                    # percentage: 40%
    r"|\d+\s*pt"                   # point value: 12pt
    r"|\d+\s*dp)",                  # density-independent pixels: 48dp
    re.IGNORECASE,
)


def _has_measurement_token(text: str) -> bool:
    """Return True if `text` contains at least one specific measurement value."""
    return bool(_MEASUREMENT_RE.search(text))


def check_critique_quality(report: dict) -> dict:
    """
    Run anti-gaming quality checks on a parsed CritiqueReport dict.

    Non-blocking — callers should log warnings but NEVER suppress the critique.
    Used by parse_critique_json() to annotate outputs for downstream learning.

    Checks:
      1. Fix specificity: every issue.fix should contain a measurement token.
      2. Issue inflation: >7 issues may indicate list-padding.
      3. Monotone citation: >70% of issues sharing one rule prefix is suspicious.

    Returns:
      dict with keys:
        - warnings: list[str]          — human-readable warning messages
        - gaming_risk: "low"|"medium"|"high"
        - vague_fix_indices: list[int] — 0-based indices of issues with vague fixes
    """
    warnings: list[str] = []
    vague_fix_indices: list[int] = []
    issues: list[dict] = report.get("issues", [])

    # Check 1 — Fix specificity
    for idx, issue in enumerate(issues):
        fix_text = issue.get("fix", "")
        if fix_text and not _has_measurement_token(fix_text):
            vague_fix_indices.append(idx)

    if vague_fix_indices:
        warnings.append(
            f"Vague fix text (no measurement token) at issue indices: {vague_fix_indices}. "
            "Each fix should include specific values (hex color, px, %, ratio, rem)."
        )

    # Check 2 — Issue inflation
    if len(issues) > 7:
        warnings.append(
            f"Issue inflation risk: {len(issues)} issues listed. "
            "Consider consolidating minor items to keep the critique actionable."
        )

    # Check 3 — Monotone citation pattern (requires ≥4 issues to be meaningful)
    if len(issues) >= 4:
        citation_prefixes: dict[str, int] = {}
        for issue in issues:
            citation = issue.get("rule_citation", "")
            prefix = citation.split()[0] if citation else "Unknown"
            citation_prefixes[prefix] = citation_prefixes.get(prefix, 0) + 1

        top_prefix, top_count = max(citation_prefixes.items(), key=lambda x: x[1])
        if top_count / len(issues) > 0.7:
            warnings.append(
                f"Monotone citation pattern: {top_count}/{len(issues)} issues cite "
                f"'{top_prefix}'. Consider diversifying rule citations."
            )

    gaming_risk: str
    if len(warnings) >= 2:
        gaming_risk = "high"
    elif len(warnings) == 1:
        gaming_risk = "medium"
    else:
        gaming_risk = "low"

    return {
        "warnings": warnings,
        "gaming_risk": gaming_risk,
        "vague_fix_indices": vague_fix_indices,
    }
