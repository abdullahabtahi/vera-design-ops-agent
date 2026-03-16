"""
Fetch and parse authoritative UX knowledge sources into clean markdown files.

Run once to populate knowledge/sources/:
    uv run python -m knowledge.fetch_sources

Sources fetched:
  - WCAG 2.2 success criteria (W3C)
  - Nielsen's 10 Usability Heuristics (NNg)
  - Material Design 3 key principles (Google)

Sources written locally (no fetch needed):
  - Gestalt principles
  - Cognitive laws (Fitts', Hick's, Miller's)
"""

import re
import textwrap
import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

SOURCES_DIR = Path(__file__).parent / "sources"
SOURCES_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "DesignOpsNavigator/1.0 (research; contact@designopsnavigator.com)"
}


# ── Helpers ───────────────────────────────────────────────────────────────────


def fetch_html(url: str) -> BeautifulSoup:
    resp = httpx.get(url, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def write_source(filename: str, content: str) -> None:
    path = SOURCES_DIR / filename
    path.write_text(content.strip() + "\n", encoding="utf-8")
    size_kb = len(content.encode()) / 1024
    print(f"  ✓  {filename}  ({size_kb:.1f} KB)")


# ── WCAG 2.2 ─────────────────────────────────────────────────────────────────


def fetch_wcag() -> None:
    """
    Write curated WCAG 2.2 success criteria.
    W3C HTML structure is complex and changes frequently — curated version is
    more reliable and accurate for RAG purposes than fragile HTML parsing.
    """
    print("Writing WCAG 2.2 (curated authoritative version)...")
    _write_wcag_curated()


def _write_wcag_curated() -> None:
    """Curated WCAG 2.2 AA success criteria — used as fallback if scrape fails."""
    content = textwrap.dedent("""
    ---
    source: WCAG 2.2
    url: https://www.w3.org/TR/WCAG22/
    category: Accessibility
    ---

    # WCAG 2.2 Success Criteria (Curated)

    W3C Web Content Accessibility Guidelines 2.2. Meet AA minimum for all digital products.

    ## SC 1.1.1 — Non-text Content (Level A)
    All non-text content (images, icons, charts) has a text alternative that serves the same purpose.
    Decorative images use empty alt="". Icons used as buttons must have accessible names.

    ## SC 1.3.1 — Info and Relationships (Level A)
    Information, structure, and relationships conveyed through presentation are also available in text.
    Use semantic HTML: headings, lists, tables with headers. Don't rely on color or position alone.

    ## SC 1.3.3 — Sensory Characteristics (Level A)
    Instructions don't rely solely on shape, color, size, or location ("click the red button").

    ## SC 1.3.4 — Orientation (Level AA)
    Content doesn't restrict its view to a single display orientation (portrait or landscape).

    ## SC 1.3.5 — Identify Input Purpose (Level AA)
    Input fields for personal data identify their purpose via autocomplete attributes.

    ## SC 1.4.1 — Use of Color (Level A)
    Color is not the only visual means of conveying information or indicating an action.
    Always pair color with text, pattern, or icon.

    ## SC 1.4.3 — Contrast (Minimum) (Level AA)
    Normal text: minimum 4.5:1 contrast ratio against background.
    Large text (18pt / 14pt bold): minimum 3:1 contrast ratio.
    UI components and graphical objects: minimum 3:1 against adjacent colors.
    Tool: check with WebAIM Contrast Checker.

    ## SC 1.4.4 — Resize Text (Level AA)
    Text can be resized up to 200% without loss of content or functionality.

    ## SC 1.4.5 — Images of Text (Level AA)
    Use actual text rather than images of text, except for logos.

    ## SC 1.4.10 — Reflow (Level AA)
    Content reflows in a single column at 320px width without horizontal scrolling.
    No loss of content or functionality.

    ## SC 1.4.11 — Non-text Contrast (Level AA)
    UI components (buttons, inputs, checkboxes) and graphical objects: 3:1 contrast ratio against surroundings.
    A disabled button that intentionally has low contrast is exempt.

    ## SC 1.4.12 — Text Spacing (Level AA)
    No loss of content when: line-height ≥ 1.5× font size, letter-spacing ≥ 0.12× font size,
    word-spacing ≥ 0.16× font size, paragraph spacing ≥ 2× font size.

    ## SC 1.4.13 — Content on Hover or Focus (Level AA)
    Additional content that appears on hover/focus must be: dismissible (Esc), hoverable (pointer can move to it), persistent (doesn't disappear on its own).

    ## SC 2.1.1 — Keyboard (Level A)
    All functionality is available via keyboard. No keyboard traps.

    ## SC 2.4.3 — Focus Order (Level A)
    Focus order preserves meaning and operability.

    ## SC 2.4.4 — Link Purpose (Level A)
    Link purpose is determinable from the link text alone or with context.
    Avoid "click here", "read more" without context.

    ## SC 2.4.6 — Headings and Labels (Level AA)
    Headings and labels describe topic or purpose.

    ## SC 2.4.7 — Focus Visible (Level AA)
    Any keyboard operable UI has a visible focus indicator.

    ## SC 2.4.11 — Focus Not Obscured (Minimum) (Level AA) — NEW in WCAG 2.2
    When a component receives focus, it is not entirely hidden by author-created content (e.g., sticky headers).

    ## SC 2.5.3 — Label in Name (Level A)
    For UI components with visible text labels, the accessible name contains the visible text.

    ## SC 2.5.8 — Target Size (Minimum) (Level AA) — NEW in WCAG 2.2
    Pointer input targets are at least 24×24 CSS pixels, or have sufficient spacing.
    Recommended: 44×44px touch targets (Apple HIG / Material Design).

    ## SC 3.1.1 — Language of Page (Level A)
    Default human language of the page is programmatically determinable (lang attribute).

    ## SC 3.2.1 — On Focus (Level A)
    Receiving focus doesn't trigger context changes.

    ## SC 3.2.2 — On Input (Level A)
    Changing a UI component's value doesn't automatically trigger a context change unless user is advised beforehand.

    ## SC 3.3.1 — Error Identification (Level A)
    Input errors are identified and described in text.

    ## SC 3.3.2 — Labels or Instructions (Level A)
    Labels or instructions are provided when content requires user input.

    ## SC 3.3.7 — Redundant Entry (Level A) — NEW in WCAG 2.2
    Information already entered by the user is auto-populated or available for selection in the same process.

    ## SC 4.1.1 — Parsing (Level A)
    HTML is well-formed. No duplicate IDs. Proper nesting.

    ## SC 4.1.2 — Name, Role, Value (Level A)
    All UI components have accessible name, role, and state programmatically determinable.
    Use ARIA where native HTML semantics are insufficient.

    ## SC 4.1.3 — Status Messages (Level AA)
    Status messages (success, error, progress) are programmatically determinable without focus.
    Use role="status", role="alert", or aria-live regions.
    """)
    write_source("wcag_2_2.md", content)


# ── Nielsen's 10 Heuristics ───────────────────────────────────────────────────


def fetch_nielsen() -> None:
    """Fetch Nielsen's 10 Usability Heuristics from NNg."""
    print("Fetching Nielsen's 10 Heuristics...")
    # NNg article is publicly accessible
    url = "https://www.nngroup.com/articles/ten-usability-heuristics/"
    try:
        soup = fetch_html(url)
        # Extract article content
        article = soup.find("article") or soup.find("main") or soup.body
        if article:
            # Find heuristic sections — they're typically h2/h3 + paragraphs
            lines = [
                "---",
                "source: Nielsen Norman Group",
                "url: https://www.nngroup.com/articles/ten-usability-heuristics/",
                "category: Usability",
                "---",
                "",
                "# Nielsen's 10 Usability Heuristics",
                "",
                "Jakob Nielsen's 10 general principles for interaction design. "
                "Use these as heuristics for evaluation, not strict guidelines.",
                "",
            ]
            headings = article.find_all(["h2", "h3"])
            # Find heuristic headings (they usually contain numbers 1-10)
            heuristic_headings = [
                h for h in headings
                if any(f"{i}." in h.get_text() or f"#{i}" in h.get_text()
                       for i in range(1, 11))
                or re.search(r'\b[1-9]0?\b', h.get_text())
            ]
            if len(heuristic_headings) >= 8:
                for h in heuristic_headings[:10]:
                    lines.append(f"## {h.get_text(strip=True)}")
                    lines.append("")
                    # Grab next 2 paragraphs
                    for sib in h.find_next_siblings():
                        if sib.name in ("h2", "h3"):
                            break
                        if sib.name == "p":
                            t = sib.get_text(" ", strip=True)
                            if t:
                                lines.append(t)
                        if len(lines) > 10 and lines[-1]:
                            break
                    lines.append("")
                write_source("nielsen_heuristics.md", "\n".join(lines))
                return
    except Exception as e:
        print(f"  ⚠  NNg fetch failed ({e}), using curated version")

    _write_nielsen_curated()


def _write_nielsen_curated() -> None:
    content = textwrap.dedent("""
    ---
    source: Nielsen Norman Group
    url: https://www.nngroup.com/articles/ten-usability-heuristics/
    category: Usability
    ---

    # Nielsen's 10 Usability Heuristics

    Jakob Nielsen's 10 general principles for interaction design. These are heuristics, not strict rules.

    ## Heuristic 1 — Visibility of System Status
    Always keep users informed about what is going on through appropriate feedback within reasonable time.
    Examples: progress bars, loading indicators, active state on navigation, "Saved" confirmation.
    Violation: Silent background operations with no user feedback.

    ## Heuristic 2 — Match Between System and the Real World
    The system uses words, phrases, and concepts familiar to the user, not internal jargon.
    Information appears in a natural and logical order.
    Examples: Trash/Recycle Bin metaphor, "Add to Cart" not "Add to Basket Object."
    Violation: Technical error codes, database IDs shown to users.

    ## Heuristic 3 — User Control and Freedom
    Users often choose system functions by mistake and need a clearly marked "emergency exit."
    Support undo, redo, and easy navigation back.
    Examples: Undo/Redo, Cancel button, Back navigation, Soft delete with restore.
    Violation: Irreversible actions without confirmation, no way to go back.

    ## Heuristic 4 — Consistency and Standards
    Users should not have to wonder whether different words, situations, or actions mean the same thing.
    Follow platform conventions (iOS, Material, Web).
    Examples: Same icon always means the same thing, consistent button placement.
    Violation: "Submit" on one form, "Send" on another for the same action type.

    ## Heuristic 5 — Error Prevention
    Prevent problems from occurring in the first place. Better than good error messages.
    Examples: Confirmation dialogs for destructive actions, input constraints (date picker vs free text),
    inline validation before submission.
    Violation: Allowing invalid date formats to be entered with no warning until submit.

    ## Heuristic 6 — Recognition Rather Than Recall
    Minimize user memory load. Make objects, actions, and options visible.
    Users shouldn't have to remember information from one part of the dialogue to another.
    Examples: Breadcrumbs, recently viewed, autocomplete, visible options (not hidden in menus).
    Violation: Requiring users to remember codes or IDs from previous steps.

    ## Heuristic 7 — Flexibility and Efficiency of Use
    Accelerators — unseen by novice users — speed up interaction for experts.
    Allow users to tailor frequent actions.
    Examples: Keyboard shortcuts, bulk actions, saved searches, command palette.
    Violation: No shortcuts for power users, every action requires navigating full UI.

    ## Heuristic 8 — Aesthetic and Minimalist Design
    Dialogues should not contain irrelevant or rarely needed information.
    Every extra unit of information competes with the relevant information and diminishes its relative visibility.
    Examples: Progressive disclosure, focused empty states, clean forms.
    Violation: Showing 20 fields when 5 are required, cluttered dashboards, decorative elements that obscure content.

    ## Heuristic 9 — Help Users Recognize, Diagnose, and Recover from Errors
    Error messages: plain language (no codes), precisely indicate the problem, constructively suggest a solution.
    Examples: "Password must be at least 8 characters" not "Invalid input."
    Violation: "Error 403", "Something went wrong", red highlight with no explanation.

    ## Heuristic 10 — Help and Documentation
    Even though it is better if the system can be used without documentation, it may be necessary to provide help.
    Help is: easy to search, focused on the user's task, lists concrete steps, not too large.
    Examples: Contextual tooltips, inline help text, searchable FAQ.
    Violation: Requiring a 50-page manual to perform basic tasks.
    """)
    write_source("nielsen_heuristics.md", content)


# ── Material Design 3 ─────────────────────────────────────────────────────────


def fetch_material3() -> None:
    """Fetch key Material Design 3 principles."""
    print("Fetching Material Design 3 principles...")
    # Write curated version — M3 site is JS-rendered, hard to scrape reliably
    _write_material3_curated()


def _write_material3_curated() -> None:
    content = textwrap.dedent("""
    ---
    source: Material Design 3
    url: https://m3.material.io/
    category: Design System
    ---

    # Material Design 3 (M3) Guidelines

    Google's open-source design system. M3 introduces dynamic color, updated components, and accessibility improvements.

    ## Color System
    M3 uses a tonal palette derived from a seed color via HCT (Hue, Chroma, Tone) color space.
    Key roles: Primary, Secondary, Tertiary, Error, each with Container and On-Container variants.
    Minimum contrast: All text must meet WCAG AA (4.5:1 normal, 3:1 large).
    Dynamic Color: System derives palette from user's wallpaper (Android 12+). Design for this adaptability.

    ## Typography Scale
    M3 type scale: Display (Large/Medium/Small), Headline, Title, Label, Body — each Large/Medium/Small.
    Display Large: 57sp. Headline Large: 32sp. Body Large: 16sp. Label Small: 11sp.
    Font: Roboto (default). Line height and letter spacing defined per scale level.
    Use type roles semantically: Headline for page titles, Label for UI components, Body for content.

    ## Layout and Grid
    M3 uses an 4dp grid. Margins: 16dp mobile, 24dp tablet.
    Breakpoints: Compact (<600dp), Medium (600–839dp), Expanded (≥840dp).
    Minimum touch target: 48×48dp (recommended), minimum 24×24dp (WCAG 2.5.8).

    ## Elevation and Surface
    Elevation uses surface tint (primary color overlaid at opacity) not shadows alone.
    Levels: 0–5. Level 1 = 5% tint, Level 5 = 12% tint. Shadows supplement tint.
    Cards: Level 1. Bottom sheets: Level 1. Navigation drawer: Level 0 with scrim.

    ## Component Specifications

    ### Buttons
    Filled button: High emphasis, primary action. Corner radius: 20dp (fully rounded).
    Outlined button: Medium emphasis, secondary action.
    Text button: Low emphasis, least important action.
    Minimum width: 48dp. Height: 40dp. Padding: 24dp horizontal.

    ### Text Fields
    Filled and Outlined variants. Height: 56dp. Corner radius (outlined): 4dp.
    Label animates from placeholder to floating label on focus.
    Supporting text: below field, 16dp left padding.
    Error state: red (#B3261E in baseline) indicator + error message.

    ### Navigation
    Navigation bar (bottom): 3–5 destinations. Icon + optional label. Active indicator pill.
    Navigation drawer: 5+ destinations, persistent on expanded layout.
    Tab bar: Horizontal, primary and secondary variants.

    ### Dialogs
    Full-screen dialogs for complex tasks. Standard dialogs: max 560dp wide, centered.
    Avoid more than 2 actions. Destructive action is text-only (no filled button in dialog).

    ### Chips
    Assist, Filter, Input, Suggestion chips. Height: 32dp. Corner radius: 8dp.

    ## States
    M3 defines 5 interaction states: Enabled, Hovered (+8% overlay), Focused (+12% overlay),
    Pressed (+12% overlay), Dragged (+16% overlay), Disabled (38% opacity).
    State layer uses on-surface color at defined opacities.

    ## Accessibility
    All interactive components have minimum 48×48dp touch targets.
    Focus indicators visible. Color not used as sole differentiator.
    Icon buttons always have content descriptions.
    """)
    write_source("material_design_3.md", content)


# ── Gestalt Principles ────────────────────────────────────────────────────────


def write_gestalt() -> None:
    print("Writing Gestalt principles...")
    content = textwrap.dedent("""
    ---
    source: Gestalt Psychology
    category: Visual Design
    ---

    # Gestalt Principles in UI Design

    Gestalt principles describe how humans perceive visual elements as unified wholes.
    Apply these to create clear visual hierarchy and intuitive layouts.

    ## Principle: Proximity
    Elements close together are perceived as related. Elements far apart are perceived as separate.
    UI application: Group related form fields together. Add space between unrelated sections.
    Button groups: place primary and secondary actions close; place destructive action far away.
    Violation: Random spacing that doesn't reflect logical groupings.

    ## Principle: Similarity
    Elements that look similar (color, shape, size, texture) are perceived as related.
    UI application: Same button style for same type of action. Color-coded categories.
    Consistent icon style within an interface (all filled, or all outlined — not mixed).
    Violation: Using the same color for both interactive links and static text.

    ## Principle: Continuity
    The eye follows smooth paths and continuous lines rather than abrupt changes.
    UI application: Align elements on a grid. Use consistent left-edge alignment in lists.
    Progress indicators and steppers imply continuation.
    Violation: Jagged, misaligned layouts that break the visual flow.

    ## Principle: Closure
    The mind completes incomplete shapes. Partial forms are perceived as complete wholes.
    UI application: Hamburger menu icon, loading skeletons, partially visible cards hint at more content.
    Use implied boundaries (whitespace) instead of explicit borders to define regions.

    ## Principle: Figure-Ground
    The eye differentiates an object (figure) from its background (ground).
    UI application: Modals with darkened backdrop. Tooltip on hover over background.
    High contrast between interactive elements and background ensures figure-ground separation.
    Violation: Low contrast buttons that blend into the page background.

    ## Principle: Common Fate
    Elements moving in the same direction are perceived as a group.
    UI application: Accordion panels that expand/collapse together. Drag-and-drop groups.
    Animations that move related elements in unison reinforce grouping.

    ## Principle: Prägnanz (Good Form / Simplicity)
    The mind organizes visual input into the simplest, most stable form.
    UI application: Use simple shapes, clear hierarchy, minimal visual noise.
    Prefer simple iconography. Remove decorative elements that don't add meaning.
    Violation: Overly complex icons, cluttered layouts with competing focal points.

    ## Principle: Symmetry and Order
    Symmetrical elements are perceived as stable, balanced, and related.
    UI application: Center-aligned modals and dialogs. Balanced card grids.
    Asymmetry can be used intentionally to create emphasis (e.g., large hero text on left).

    ## Principle: Focal Point
    An element that stands out from its surroundings becomes the focal point.
    UI application: Primary CTA button in a contrasting color. Hero image. Large headings.
    One strong focal point per screen section. Multiple competing focal points = visual chaos.
    """)
    write_source("gestalt_principles.md", content)


# ── Cognitive Laws ────────────────────────────────────────────────────────────


def write_cognitive_laws() -> None:
    print("Writing cognitive laws...")
    content = textwrap.dedent("""
    ---
    source: HCI Research / UX Laws
    url: https://lawsofux.com/
    category: Cognitive Psychology
    ---

    # Cognitive Laws in UX Design

    Evidence-based principles from cognitive psychology applied to user interface design.

    ## Fitts' Law
    The time to acquire a target is a function of distance to the target and target size.
    Formula: T = a + b × log₂(2D/W) where D = distance, W = target width.
    UX implications:
    - Make buttons and click targets large (minimum 44×44px for touch, WCAG recommends 24×24px CSS).
    - Place frequently used actions close to where users are (context menus, floating action buttons).
    - Edge and corner of screen are effectively infinite in size (Fitts' law for pointing devices).
    - Primary CTAs should be the largest interactive element on the screen.
    - Don't make users travel far to reach related actions.
    Violation: Small 16px buttons, action buttons placed far from the content they act on.

    ## Hick's Law
    The time to make a decision increases with the number and complexity of choices.
    Formula: T = b × log₂(n + 1) where n = number of stimuli.
    UX implications:
    - Limit navigation items to 5–7 options (Miller's Law synergy).
    - Use progressive disclosure: hide advanced options behind "More" or secondary navigation.
    - Reduce cognitive load at decision points: one primary CTA per screen.
    - Chunk long forms into steps (wizard pattern).
    - Recommendation engines reduce decision paralysis by narrowing choices.
    Violation: 20-item navigation menus, forms with 30 fields on one page, no default selections.

    ## Miller's Law
    The average person can hold 7 ± 2 items in working memory at once.
    UX implications:
    - Navigation: max 7 items in top-level nav (5 is safer for mobile).
    - Phone numbers formatted as chunks: (555) 867-5309 not 5558675309.
    - Onboarding steps: max 5–7 before users lose track.
    - Data tables: highlight key columns; don't show 20 columns by default.
    - Chunk lists with visual separators every 5–7 items.
    Violation: 15-step onboarding, 12-tab navigation, unbounded lists with no pagination.

    ## Jakob's Law
    Users spend most of their time on other sites. They expect your site to work the same way.
    UX implications:
    - Follow platform conventions (iOS back-swipe, browser back button, form submit on Enter).
    - Use familiar patterns: hamburger menu, search icon (magnifying glass), cart icon.
    - Don't innovate on navigation patterns without strong user research justification.
    Violation: Custom navigation patterns that deviate from platform conventions without benefit.

    ## Law of Common Region
    Elements within the same bounded area are perceived as a group.
    UX implications:
    - Use cards, panels, and containers to group related content.
    - Form sections with visible boundaries reduce cognitive load.
    - Avoid overusing borders — whitespace can imply common region without visual weight.

    ## Peak-End Rule
    People judge an experience by its peak (most intense moment) and its end, not the average.
    UX implications:
    - Make success states (confirmation, completion) delightful and clear.
    - End onboarding on a high note (show value, not more setup).
    - Error states are peaks — design them carefully to reduce frustration.
    - Loading states at the end of a long process should feel rewarding.
    Violation: Ending a checkout with a bland confirmation page after a complex purchase.

    ## Aesthetic-Usability Effect
    Users perceive aesthetically pleasing design as more usable.
    UX implications:
    - Beautiful interfaces get more forgiveness for usability issues (but don't rely on this).
    - Visual polish increases perceived trustworthiness.
    - Invest in spacing, typography, and color consistency — it's not just decoration.
    """)
    write_source("cognitive_laws.md", content)


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    print(f"\nFetching knowledge sources → {SOURCES_DIR}\n")

    # Write curated + fetch from web
    fetch_wcag()

    fetch_nielsen()
    time.sleep(1)  # polite delay after network fetch

    fetch_material3()

    # Write locally (no fetch needed)
    write_gestalt()
    write_cognitive_laws()

    print(f"\nDone. Files in {SOURCES_DIR}:")
    for f in sorted(SOURCES_DIR.glob("*.md")):
        size_kb = f.stat().st_size / 1024
        print(f"  {f.name:40s} {size_kb:6.1f} KB")


if __name__ == "__main__":
    main()
