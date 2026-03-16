export interface Playbook {
  id: string;
  title: string;
  description: string;
  badge: string;
  badgeColor: string;
  prompt: string;
}

export const PLAYBOOKS: Playbook[] = [
  {
    id: "accessibility-audit",
    title: "Accessibility Audit",
    description: "Full WCAG 2.2 AA compliance review — contrast ratios, focus management, ARIA roles, and keyboard navigation.",
    badge: "WCAG 2.2",
    badgeColor: "indigo",
    prompt:
      "Run a comprehensive WCAG 2.2 AA accessibility audit. Check: (1) color contrast ratios for all text and interactive elements — call out exact hex pairs and measured ratios, (2) focus indicators and keyboard navigation path, (3) ARIA roles and labels on interactive components, (4) touch target sizes (minimum 44×44px per Apple HIG / 48dp per Material 3), and (5) text alternatives for any non-text content. For each issue, cite the specific WCAG success criterion (e.g. SC 1.4.3) and give an exact, actionable fix with specific values.",
  },
  {
    id: "cognitive-load-check",
    title: "Cognitive Load Check",
    description: "Detect information overload, visual noise, and working-memory strain using Miller's Law, Hick's Law, and Fitts's Law.",
    badge: "Cognitive Laws",
    badgeColor: "violet",
    prompt:
      "Analyze this design for cognitive overload. Apply: Miller's Law (chunking — are groups limited to 5–9 items?), Hick's Law (choice paralysis — how many options are visible at once?), and Fitts's Law (target acquisition — are interactive elements sized and spaced appropriately?). Identify: (1) areas with too many simultaneous choices, (2) visual hierarchy breakdowns causing attention scatter, (3) flows requiring excessive working memory (e.g. multi-step forms with no progress indicator), (4) inconsistent patterns that break mental models. Suggest concrete simplifications for each issue with specific before/after values.",
  },
  {
    id: "first-time-user-flow",
    title: "First-Time User Flow",
    description: "Evaluate onboarding clarity, empty states, and progressive disclosure for brand-new users.",
    badge: "Nielsen #6",
    badgeColor: "emerald",
    prompt:
      "Review this design through the eyes of a first-time user who has never used this product. Identify: (1) missing onboarding cues or empty states that leave users without direction — what should a good empty state say here? (2) jargon or labels that aren't self-explanatory without prior product knowledge, (3) actions that lack undo support or confirmation (Nielsen Heuristic #5: Error Prevention), (4) progressive disclosure gaps — is the user overwhelmed immediately or guided step-by-step? (5) Apply Nielsen Heuristic #6 (Recognition vs. Recall) throughout — does the UI surface options or make users remember them?",
  },
  {
    id: "mobile-usability",
    title: "Mobile Usability",
    description: "Touch targets, thumb zone, content density, and gesture conflicts for smartphone screens.",
    badge: "Material 3",
    badgeColor: "amber",
    prompt:
      "Critique this design for mobile usability on a smartphone screen. Evaluate: (1) touch targets — are all interactive elements at least 44×44px (Apple HIG) or 48×48dp (Material 3)? Call out any that fall short. (2) Thumb zone — are primary CTAs reachable in the natural thumb zone (bottom 60% of screen)? (3) Content density — is information appropriately sized and spaced for a small screen without being sparse? (4) Gesture conflicts — any swipe-to-dismiss competing with scroll, or pinch conflicting with layout? (5) Typography — does all body text remain readable at 16px minimum? Prioritize issues by likely friction impact.",
  },
  {
    id: "conversion-friction",
    title: "Conversion Friction",
    description: "Identify drop-off risks, CTA clarity issues, and friction points that undermine conversion goals.",
    badge: "UX Patterns",
    badgeColor: "rose",
    prompt:
      "Review this design for conversion optimization and user drop-off risks. Analyze: (1) primary CTA — is it visible, clearly labelled, and above the fold? Is the label action-oriented (e.g. 'Start free trial' vs 'Submit')? (2) Form friction — are there unnecessary required fields? Is there a progress indicator for multi-step flows? Are error messages specific and recovery-oriented? (3) Trust signals — are security badges, privacy notices, or social proof present at the decision point where users need reassurance? (4) Competing CTAs — is there a clear primary vs. secondary action hierarchy, or are multiple CTAs fighting for attention? (5) Dead ends — can users recover from every error state or does any path lead to a stuck state?",
  },
];

export function getPlaybook(id: string): Playbook | undefined {
  return PLAYBOOKS.find(p => p.id === id);
}
