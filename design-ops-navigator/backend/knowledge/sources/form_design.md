---
source: Form Design Best Practices
url: https://www.nngroup.com/articles/form-design/
category: Interaction Design
---

# Form Design Best Practices

Evidence-based guidelines for designing accessible, usable forms. Forms are the highest-friction element in most UIs — poor form design directly causes abandonment.

## Label Placement — Top-Aligned Preferred
Top-aligned labels (label above input) have the fastest completion rates and best scanability.
Left-aligned inline labels require two eye fixations (label + field) and break on mobile.
Placeholder-only labels (no persistent label) fail when users are filling in the form — the label disappears and users forget the expected input. Never use placeholder as the only label.

## Required vs Optional Fields
Mark optional fields, not required ones — most fields in a well-designed form should be required.
Use "(optional)" text, not asterisks alone. If using asterisks, place a legend ("* Required") at the top.
Avoid requiring fields that aren't genuinely necessary — every extra field increases abandonment by ~4%.

## Input Width Signals Expected Length
Match input field width to expected input length: short fields for ZIP codes, phone numbers; full-width for free text.
Fixed-width fields that are too short signal the wrong input type and frustrate users.

## Placeholder Text Anti-Patterns
Placeholder text disappears when users start typing — never use it for instructions or examples that users need while filling in the field.
Use placeholder only for format hints that users can infer again (e.g., "MM/DD/YYYY"). Critical instructions belong in helper text below the field.
Placeholder text contrast often fails WCAG SC 1.4.3 — minimum 4.5:1 against background required.

## Inline Validation Timing
Validate on blur (when field loses focus), not on keypress — keystroke-by-keystroke errors frustrate users before they finish typing.
Exception: password strength indicators may update in real-time as a positive affordance.
Show success indicators (green checkmark) for fields that pass validation — reduces anxiety.

## Error Message Placement and Tone
Place error messages directly below the field that caused the error, not in a summary at the top only.
Error messages must: (1) identify which field is wrong, (2) explain what's wrong, (3) tell users how to fix it.
Bad: "Invalid input." Good: "Phone number must be 10 digits (e.g., 555-867-5309)."
Use red for errors but also add an icon — never rely on color alone (WCAG SC 1.4.1).

## Submit Button State and Placement
Submit button should be left-aligned (aligned to input fields), not centered — users scan the left edge.
Disable submit only after submission starts to prevent double-submit. Don't disable before — it hides why the form can't submit.
Show loading state on submit button during async operations (spinner + "Saving…"). Prevents duplicate submissions.

## Grouped Fields and Visual Proximity
Use visual grouping (whitespace, borders, or light background) for related fields (e.g., billing address block).
Gestalt Law of Proximity: fields close together are perceived as related. Use consistent spacing to signal groupings.

## Password Field Design
Always provide a show/hide password toggle (eye icon) — reduces input errors and improves conversion.
Password fields with no show toggle fail mobile users who can't easily see what they're typing.
Password strength indicators should specify requirements, not just show a colored bar (strong/medium/weak labels alone are not actionable).

## Multi-Step Forms and Progress Indication
For long forms, break into steps with a visible progress indicator (step X of Y, or labeled steps).
Show users what step they're on and how many remain — reduces anxiety and abandonment.
Save progress between steps — don't lose data if users navigate back or refresh (WCAG SC 3.3.7).
Each step should have a clear, descriptive heading.

## Select vs Radio vs Checkbox
Use radio buttons when there are 2–7 mutually exclusive options (faster to scan than a dropdown).
Use a dropdown/select when there are 8+ options or screen space is constrained.
Use checkboxes for multi-select. Never use a dropdown for multi-select on mobile — checkboxes are more touch-friendly.
Avoid dependent dropdowns (choosing one changes another) without clear feedback to the user.

## Field Instructions and Helper Text
Persistent helper text below a field is preferable to tooltip-only instructions.
Helper text should describe format, constraints, or why the information is needed — not restate the label.
Example: Label "Date of birth" + helper text "We use this to verify your age (DD/MM/YYYY)."

## Input Mode and Keyboard Type
Set appropriate input modes: inputmode="numeric" for numeric-only fields, inputmode="email" for email, inputmode="tel" for phone.
This triggers the correct mobile keyboard (numeric, email, phone) — reduces error rate and friction on mobile.

## Autofill and Autocomplete
Enable browser autocomplete: use autocomplete attributes (name, email, tel, cc-number, etc.) per WCAG SC 1.3.5.
Don't disable autocomplete with autocomplete="off" on login forms — this worsens UX for returning users and reduces password manager compatibility.
