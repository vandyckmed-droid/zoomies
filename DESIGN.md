# Design Principles

## Durable intent

These principles guide decisions without prescribing the current UI. Tables, cards, or other presentations may coexist or evolve. Data and ranking logic should stay independent from presentation; different views consume shared state rather than duplicate product logic.

## Core principles

- **Be ambitious in the interface, conservative in the machinery.** The product experience — what a screen looks like, how an interaction feels, what a view surfaces — should be free to be bold. The machinery underneath it — ranking, scoring, correlation, persistence, and the data a build produces — should change only when a real product requirement demands it, not as a side effect of chasing a new look.
- **Phone-first.** The default experience is optimized for mobile devices. Desktop is an enhancement.
- **Minimal, dense, sharp, calm, legible.** Every element serves a purpose. UI chrome is subordinate to information. The interface is precise and assertive without being aggressive.
- **Ranking is the primary product.** Tables, cards, and other views are presentation mechanisms that serve the ranking and may coexist or evolve.
- **Ticker is identity.** The ticker symbol is the primary identifier and visual anchor.
- **Core hierarchy: Return + volatility → score → rank.** This is the product's mathematical heart.
- **Primary information dominates; chrome stays subordinate.** Navigation and decoration are minimized.
- **Secondary information uses progressive disclosure.** Detail panels, separate sections, or deep dives reveal secondary content.
- **Favor useful information density over decoration.** Whitespace, animations, and visual ornament exist only when they serve clarity.
- **Prefer small, reversible design changes.** Incremental tweaks over large redesigns; easy rollback over structural risk.
- **Lightweight and loosely coupled.** Simple, straightforward HTML/CSS/JS so the interface can be substantially changed without destabilizing ranking or other functionality. Stay plain HTML/CSS/JS — no framework, build step, or dependency — until a concrete product requirement can't reasonably be met without one.
- **Presentation is malleable; product logic is not.** Data and state remain separate from presentation. A major theme or layout change should replace markup, CSS, and rendering — never the ranking, persistence, correlation, or other data logic underneath it. Reuse existing UI primitives and CSS/theme tokens where they fit, rather than inventing parallel ones.
- **Visual assumptions stay out of product state.** What a view happens to render should never leak into what the app persists or computes — saved state and data structures describe the product, not one particular presentation of it.
- **Refactor opportunistically, not speculatively.** Clean up code you're already touching for a real reason; don't restructure working code on the chance it might someday be useful.

## Evaluating a new idea

Bold interaction and product ideas are welcome — that ambition belongs in the interface, per the first principle above. Before committing to one, place it honestly:

- **Possible in the current architecture** — plain HTML/CSS/JS, existing data, no new moving parts.
- **Possible with a small, well-scoped extension** — a modest build.py addition, a new field, a contained new client-side mechanism.
- **Requires a materially different platform** — a real backend, a native app, persistent server state, or similar. Say so plainly rather than reaching for a brittle web hack to imitate a capability the current platform doesn't actually have.

Whatever tier an idea lands in, the existing product must keep working. Polish and experimentation should never unnecessarily destabilize the ranking, persistence, or other functionality already in daily use — a design that ships broken is not more ambitious than one that ships working.

When in doubt, defer to clarity and utility over aesthetic preference.
