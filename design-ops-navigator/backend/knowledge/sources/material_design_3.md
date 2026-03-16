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
