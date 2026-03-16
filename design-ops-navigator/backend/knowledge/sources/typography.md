---
source: Typography Best Practices for UI
url: https://www.nngroup.com/articles/typography-for-ui/
category: Visual Design
---

# Typography Best Practices for UI

Evidence-based guidelines for readable, accessible, and hierarchically clear typography in digital interfaces.

## Font Size Minimums

Body text must be a minimum of 16px (1rem) on desktop; mobile body text should not go below 16px either — smaller text forces users to zoom, which breaks layout.
Supporting text (captions, helper text, metadata) minimum 12px (0.75rem) — never smaller for any content users need to read.
WCAG SC 1.4.4: Text must resize up to 200% without loss of content or functionality.

## Line Height (Leading)

Body text line height: 1.4–1.6× font size (e.g., 24–26px for 16px text).
Too tight (< 1.2×): lines run together, severely impairs dyslexic users.
Too loose (> 2×): paragraph cohesion breaks — lines feel disconnected.
Headings may use tighter line height (1.1–1.3×) because they are short strings.

## Line Length (Measure)

Optimal measure: 60–80 characters per line (including spaces) for body text.
Too short (< 45 chars): excessive eye movement, reading rhythm broken.
Too long (> 100 chars): users lose their place when returning to the next line.
On mobile: 35–50 characters per line is acceptable due to screen width constraints.
Use `max-width: 65ch` or `max-width: 680px` to enforce measure in CSS.

## Type Scale and Hierarchy

Use a modular scale (e.g., 1.25× or 1.333× ratio) for consistent heading sizes.
Maintain at least 4px size difference between adjacent hierarchy levels — 16px body and 18px subheading is not a meaningful distinction.
Never rely on size alone to convey hierarchy — also vary weight, color, or spacing.
Limit to 3–4 distinct typographic roles per screen (display, heading, body, caption) to avoid visual noise.

## Font Weight Usage

Use weight variation purposefully: body 400 (Regular), emphasis 500 or 600 (Medium/Semibold), display 700+ (Bold).
Avoid faux bold (browser-synthesized) on custom web fonts — it produces uneven strokes and degrades legibility.
Light weights (100–300) are decorative only — never use for body text, especially on low-contrast displays.
Weight contrast between heading and body: minimum 100–200 weight units for visual separation (e.g., heading 700 vs body 400).

## Contrast Ratio Requirements (WCAG SC 1.4.3 + 1.4.6)

Normal text (< 18pt regular / < 14pt bold): minimum 4.5:1 against background (AA).
Large text (≥ 18pt regular / ≥ 14pt bold): minimum 3:1 (AA).
Enhanced: 7:1 for normal, 4.5:1 for large text (AAA).
Placeholder text: commonly fails — minimum 4.5:1 even for placeholder.
Disabled text: exempt from contrast requirements, but should still be visually distinguishable.

## Letter Spacing and Tracking

Default letter spacing: 0 for body text — do not override unless the typeface requires it.
Uppercase labels/headings: add +0.05–0.1em tracking for legibility (ALL CAPS reduces letter recognition).
Tight tracking on body text (negative letter-spacing) severely impairs dyslexic readers.
WCAG SC 1.4.12: Users must be able to set letter-spacing to 0.12× font size without loss of content.

## Alignment

Left-aligned text (LTR languages): default for body, always use for paragraphs.
Centered text: acceptable for headings, short labels, empty states — never for multi-line body text.
Justified text: avoid in UI — creates uneven word spacing (rivers of whitespace) harmful to dyslexic users.
Right-aligned: for RTL languages and right-anchored numerical data in tables.

## Font Families — Web Font Best Practices

System font stacks (San Francisco, Segoe UI, Roboto) offer best performance and OS-native rendering — use as fallback always.
Load no more than 2 custom typefaces per project — each additional font family adds ~100–300KB.
Use `font-display: swap` to prevent invisible text while web fonts load.
Avoid typefaces with ambiguous characters (lowercase l, uppercase I, numeral 1) for UI labels — choose fonts with clear glyph distinction.

## Responsive Typography

Use `clamp()` for fluid type: `font-size: clamp(1rem, 2.5vw, 1.5rem)` — avoids abrupt breakpoint jumps.
Do not use viewport units (vw) alone — text becomes uncontrollably small on narrow screens.
Test typography at 320px viewport width (WCAG minimum supported width) and at 1440px.

## Number Typography (Tabular Figures)

Use tabular (monospaced) figures for numerical data in tables and dashboards — ensures columns align.
CSS: `font-variant-numeric: tabular-nums`.
Default proportional figures are acceptable for running text but break alignment in data tables.

## Readability for Dyslexia and Low Vision

Avoid italic for long passages — italic increases reading time for dyslexic users.
Avoid ALL CAPS for paragraphs — reduces reading speed by 13–20%.
Do not use text overlaid directly on busy images without a scrim or semi-transparent overlay.
Dyslexia-friendly: adequate spacing, clear letterforms, generous line height. Dedicated "dyslexia fonts" (OpenDyslexic) are not universally preferred — prioritize NN/g tested best practices instead.

## Text Overflow and Truncation

Use ellipsis (`text-overflow: ellipsis`) only for secondary, non-critical text — users must be able to access full content (tooltip, expand, or separate view).
Never truncate headings or primary labels — resize or reflow instead.
Multi-line truncation (`-webkit-line-clamp`) is acceptable for card descriptions when full text is accessible elsewhere.

## Spacing Between Text Blocks

Paragraph spacing: 0.75–1× line height (e.g., 18–24px after a 24px line-height paragraph).
WCAG SC 1.4.12: Paragraph spacing must accommodate 2× font-size without loss of content.
Heading-to-content gap: slightly less than space above the heading — proximity signals the heading belongs to the content below it (Gestalt Law of Proximity).
