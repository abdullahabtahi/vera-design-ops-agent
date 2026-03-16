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
