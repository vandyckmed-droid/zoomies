# Design Principles

## Durable intent

These principles guide decisions without prescribing the current UI. Tables, cards, or other presentations may coexist or evolve. Data and ranking logic should stay independent from presentation; different views consume shared state rather than duplicate product logic.

## Core principles

- **Phone-first.** The default experience is optimized for mobile devices. Desktop is an enhancement.
- **Minimal, dense, sharp, calm, legible.** Every element serves a purpose. UI chrome is subordinate to information. The interface is precise and assertive without being aggressive.
- **Ranking is the primary product.** All other presentations are secondary.
- **Ticker is identity.** The ticker symbol is the primary identifier and visual anchor.
- **Core hierarchy: Return + volatility → score → rank.** This is the product's mathematical heart.
- **Primary information dominates; chrome stays subordinate.** Navigation and decoration are minimized.
- **Secondary information uses progressive disclosure.** Detail panels, separate sections, or deep dives reveal secondary content.
- **Favor useful information density over decoration.** Whitespace, animations, and visual ornament exist only when they serve clarity.
- **Prefer small, reversible design changes.** Incremental tweaks over large redesigns; easy rollback over structural risk.
- **Lightweight and loosely coupled.** Simple, straightforward HTML/CSS/JS so the interface can be substantially changed without destabilizing ranking or other functionality.

When in doubt, defer to clarity and utility over aesthetic preference.
