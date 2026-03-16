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
