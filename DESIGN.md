# Design Principles

## Core Philosophy

Zoomies is built on the principle that ranking is the product. The interface, information architecture, and interactions all exist to serve the ranking system's clarity and utility.

## Design Principles

### 1. Phone-First

The default experience is optimized for mobile devices. Desktop is an enhancement, not the primary target. This drives:

- Touch-friendly interaction targets
- Portrait-first layout
- Data density appropriate for small screens
- Fast-loading, minimal asset payloads

### 2. Minimal and Dense

Every element serves a purpose. UI chrome is subordinate to information.

- Avoid decoration and visual noise
- Information density is valued over whitespace
- Prioritize data presentation over affordances
- Small, functional components over large, prominent ones

### 3. Sharp and Calm

The interface is precise and assertive without being aggressive.

- Clarity in typography and layout
- Confident use of color and contrast
- Restrained motion and interaction feedback
- Legible metrics and numbers at all sizes

### 4. Legible

All content must be readable and meaningful.

- Sufficient contrast for all viewing conditions
- Typography that works at small sizes
- Numbers formatted for quick scanning
- Abbreviations and symbols consistent and clear

### 5. Ranking is Primary

The ranking table/list is the core product. All other presentations (cards, detailed views, analytics) are secondary.

- Ranking display is the first and most prominent element
- Navigation and chrome are minimized
- Alternative views are accessed through progressive disclosure
- Information architecture prioritizes the rank list

### 6. Ticker is Identity

The asset ticker symbol is the primary identifier and visual anchor for each item.

- Tickers are prominent and consistent
- They're the first element users scan
- Color, size, and position emphasize ticker identity
- Related information (name, metrics) is secondary

## Information Hierarchy

### Primary Information

Always visible in the default view:

- Asset ticker
- Current score
- Rank position
- Return value
- Volatility value

### Secondary Information

Revealed through progressive disclosure (expandable details, separate sections):

- Historical score movement
- Additional metrics
- Asset category or sector
- More detailed volatility breakdown
- Performance comparison

## Design Practices

### Progressive Disclosure

Information is shown in layers:

1. **At a glance**: Ticker, score, rank, return, volatility
2. **On interaction**: Detailed metrics, history, related assets
3. **On navigation**: Deep analysis, configuration, historical data

### Useful Density Over Decoration

- Use whitespace functionally, not for breathing room
- Compact layouts on small screens
- Multi-column presentations where appropriate
- Data visualization favors clarity over aesthetics

### Small, Reversible Design Changes

- Prefer incremental tweaks to large redesigns
- Test changes on actual devices
- Easy rollback of UI changes
- Avoid structural changes without strong justification

### Color and Contrast

- Use color semantically (gains/losses, volatility ranges)
- Sufficient contrast for accessibility (WCAG AA minimum)
- Consistent meaning across the interface (green/red patterns apply everywhere)
- Support both light and dark modes

## Implementation Notes

When making design decisions, consult this document in order:

1. Is this change aligned with phone-first principles?
2. Does this add essential information or interaction?
3. Is the information hierarchy clear?
4. Can secondary information be progressively disclosed?
5. Can this change be made smaller and more reversible?

All design changes should preserve or improve ranking prominence and clarity.
