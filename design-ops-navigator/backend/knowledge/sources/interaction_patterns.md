---
source: UI Interaction Patterns
url: https://www.w3.org/WAI/ARIA/apg/patterns/
category: Interaction Design
---

# UI Interaction Patterns

Evidence-based interaction patterns for common UI components. Based on ARIA Authoring Practices Guide (APG), WCAG 2.2, and NN/g research.

## Modal Dialog Pattern
Modals must trap keyboard focus inside the dialog while open — Tab and Shift+Tab cycle through interactive elements within the modal only.
Opening a modal moves focus to the first focusable element or the dialog title.
Closing the modal (via close button, Esc key, or backdrop click) returns focus to the trigger element that opened it.
Modal must have role="dialog" with aria-modal="true" and aria-labelledby pointing to the dialog title.
Scroll behind an open modal must be blocked. Don't use modals for complex flows that need navigation — use a drawer or new page instead.

## Dropdown / Select Menu Pattern
Custom dropdowns must support: Arrow keys to navigate options, Enter/Space to select, Esc to close, Home/End to jump to first/last option.
The trigger button must show the current selection and indicate it opens a listbox (aria-haspopup="listbox").
Dropdown lists should not exceed viewport height — implement internal scrolling with a fixed max-height.
Never use hover alone to reveal dropdown menus — they must also be accessible by keyboard focus.

## Tab Panel Pattern
Tab panels use role="tablist", role="tab", and role="tabpanel". Active tab has aria-selected="true".
Arrow keys (← →) navigate between tabs; Tab moves focus into the active panel.
Tab content should not change URL — if the content warrants deep-linking, use pages instead.
Avoid more than 7 tabs — beyond that, consider a sidebar nav or dropdown selector.

## Accordion Pattern
Accordions use role="region" with aria-labelledby pointing to the trigger. Trigger buttons use aria-expanded="true/false".
Enter or Space activates the trigger. Arrow keys optionally navigate between accordion headers.
Use accordions for progressive disclosure — don't hide content users will almost certainly need.
Avoid nesting accordions inside accordions (cognitive overload, violation of Nielsen Heuristic #8).

## Navigation Menu — Mega Menu and Flyout
Mega menus that open on hover must also open on keyboard focus.
Esc closes the current menu and returns focus to the trigger.
Don't auto-close menus when the pointer leaves — add a short delay (300–500ms) to prevent accidental dismissal.
Current page/section in navigation must be marked with aria-current="page".

## Toast / Snackbar Notifications
Toasts should use role="status" (polite) for informational messages and role="alert" (assertive) for errors.
Auto-dismissing toasts must remain visible for at least 5 seconds — users may be slow readers.
Provide a manual dismiss option for any toast that auto-dismisses. Never auto-dismiss error messages.
Don't stack more than 3 simultaneous toasts — it's cognitive overload. Queue them instead.
Don't use toasts for information users need to act on — use a modal or inline message instead.

## Tooltip Pattern
Tooltips appear on hover AND on keyboard focus — never hover-only.
Tooltip text is supplementary — don't put critical information only in tooltips.
Use aria-describedby (for supplementary info) or aria-label (for icon buttons with no visible text).
Don't put interactive content (links, buttons) inside tooltips. For that, use a popover/disclosure.
Tooltips should appear within 300–500ms of hover/focus, not instantly (prevents accidental display).

## Loading States and Async Actions
Buttons that trigger async actions must show a loading state (spinner + text like "Saving…") to prevent double-clicks.
Disable interactive elements only during active loading — not before submission starts.
Use aria-busy="true" on the loading region, aria-live="polite" for completion announcements.
Show progress for operations over 1 second. Show a skeleton screen for operations over 3 seconds.

## Infinite Scroll vs Pagination
Infinite scroll requires keyboard access to reach footer content — implement a "Load more" button fallback.
Infinite scroll loses the user's position on page refresh — preserve scroll position in URL or session.
Pagination is preferred for task-completion contexts (search results, tables) — users can navigate to specific pages.
Use virtual scrolling (render only visible items) for lists over 100 items to maintain performance.

## Drag and Drop
Drag-and-drop must have an alternative keyboard interaction (e.g., cut/paste, arrow keys + modifier, or explicit move controls).
Provide visual feedback during drag: highlight valid drop targets, show drag ghost, indicate invalid drop zones.
Announce drag-and-drop results to screen readers using aria-live regions.

## Destructive Action Confirmation
Destructive actions (delete, discard, overwrite) must always require a confirmation step.
Use a modal dialog, not a tooltip or inline toggle — the modal creates a clear pause and reduces accidental deletion.
Confirmation dialog must clearly state the consequence: "Delete 'Project Alpha'? This cannot be undone."
Don't use red buttons for every delete — reserve high-severity color for truly destructive, irreversible actions.

## Breadcrumb Navigation
Breadcrumbs use nav aria-label="Breadcrumb" with an ordered list (ol). Current page uses aria-current="page".
Show breadcrumbs when users are 3 or more levels deep in a hierarchy.
Don't include the current page as a link in breadcrumbs — it should be plain text.

## Empty States
Empty states (no data, first use, search with no results) must provide context and a clear next action.
Bad: "No results." Good: "No projects yet. Create your first project to get started." with a CTA button.
Distinguish between "no data exists" (onboarding), "search returned nothing" (adjust query), and "error" states — each needs different messaging.

## Contextual Menus and Action Menus
Right-click context menus must have an equivalent keyboard method (e.g., action button, overflow "..." menu).
Action menus (kebab/overflow menus) should group and order items by frequency of use, with separators for destructive actions.
Don't put more than 10 items in a flat context menu — group with submenus or separate out the primary actions.
