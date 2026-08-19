# TODO

This is the active backlog and work ledger, not a history log. It answers:
what is happening now, what comes next, what is being researched, what
remains on the roadmap, what has been deferred or rejected. The Chief of
Staff maintains it. It is not a changelog — completed work leaves this file.
Nothing in this file authorizes a build. Items reach production only as an
explicit APPROVED TO BUILD task.

## Inbox

Raw captures from the Product Owner, unsorted and untriaged. The Chief of Staff
moves items from here into the sections below. Nothing in this section is
approved, scheduled, or lane-assigned.

- 52-week range presentation. The Product Owner liked an external layout: a
  horizontal track with the high label above and right-aligned, the low label
  below and left-aligned, and a hollow circular marker sitting on the line at
  the current close. Zoomies already renders low52w / high52w / lastClose as a
  track-and-marker in the detail panel (rangeBarHtml, index.html), so this is
  presentation only — no new data, payload, or build work. Two separable
  pieces: (a) restyle the existing detail-panel range, cosmetic, folds into the
  Detail panel polish item under Next; (b) promote the range to a per-row
  column in the ranking table, which is not cosmetic — it competes with the
  primary ticker/rank/score/return/volatility hierarchy and with progressive
  disclosure, and needs a product decision before it is scheduled.

## In Progress

- Universe contamination detection (Agent 3, Research Lane, issue in flight).
  At least 22 exchange-traded debt and preferred instruments pass
  is_common_stock(). Both detection methods tried so far are name-based
  heuristics and both were provably incomplete. The real question is whether
  the data provider exposes an authoritative security-type field. Currently
  ranks 380-850, nothing user-visible affected. Low priority.
- Candidate -> Watchlist correlation (issue #38). While scanning rankings, see
  whether a candidate is already highly correlated with watchlist names.
  Possible later extensions: redundancy warning on add, diversification
  summary, candidate comparison, correlation-aware selection. Awaiting a
  Product Owner decision.

## Next

- Correct README.md line 44. It currently claims ETFs, funds, preferreds,
  warrants, rights and units are excluded from the universe; preferreds and
  exchange-traded debt are demonstrably present. The corrected wording depends
  on the universe-contamination research now in flight, so this is recorded
  rather than scheduled.
- Cosmetic bundle (Fast Lane). Two adjacent surfaces, one PR.
  (a) Watchlist pair rows: move the correlation value inward, use a compact
      minus control at far right, drop the repeated ticker from the remove
      button. Target shape: "BTSG <-> ASX   0.31                 -"
  (b) Detail panel polish: long-value/date alignment, typography, light-mode
      muted-text contrast, better-integrated close control.

## Research Queue

- Universe tab scoping. What population-level views actually change a decision.
  Must precede any design work, to avoid building a generic dashboard.
- Risk/return map. Natural Universe candidate; research and design first.
- Per-ticker price graph — payload and data design. A real price-vs-time chart,
  not a rank sparkline. Likely per-symbol price shards mirroring the return
  shards. Architecture decision must precede UI work.

## Fast Lane Candidates

Small, well-understood items not yet scheduled. Everything currently identified
as Fast Lane is already in Next.

## Product Roadmap

- Universe — planned third destination.
- Cards + table coexistence. The current table is not permanent by definition.
  Primary hierarchy stays ticker, rank, score, return, volatility. No decorative
  card clutter.
- 63-day rank movement population view: biggest climbers and fallers. Detail
  already shows 63D rank change. Does not justify resurrecting the sparkline.
- Logos in detail and cards. Needs sourcing, licensing, caching, fallback. Do
  not hotlink.
- Fourth destination: intentionally undefined.

## Deferred / Later

- Correlation-aware sizing. Explicitly not V1. Only worth adding if decision
  quality improves enough to justify the complexity.
- Price-graph range selectors.
- Expanding the GitHub-as-shared-office workflow (PR threads for Agent 1 <->
  Agent 2, Issues for Agent 3 -> Agent 2). Trialled on PR #34, qualified
  result. Agent 2 posting its verdict as a GitHub review worked and removed one
  relay. Two limits surfaced: Agent 1 and Agent 2 share a GitHub identity, so
  native review states are unavailable; and webhook delivery is best-effort, so
  the approval and merge events never arrived. Keep the PR-review convention.
  Do not build on branch protection or on event delivery. Not formalized
  further until a second real trial.

## Rejected / Do Not Resurrect Without New Reason

Revisit only with genuinely new reasoning or evidence.

- Volatility floor in the score. Researched in issue #36, reviewed and ACCEPTED
  by Agent 2. Decision: KEEP CURRENT SCORE. The premise fails on current data —
  Spearman(annVol, score) = -0.099, and top-25 median volatility (0.3252) sits
  above the universe median (0.3217). No floor candidate separated from
  baseline on forward returns; the best result deflates to t < 0.9 once window
  overlap is honoured, and is less extreme than noise across a 30-cell sweep
  would typically produce. A 22% floor would reprice roughly 113 legitimate
  low-volatility equities and act as an undeclared sector bet against
  utilities, REITs and pipelines. Adaptive floors additionally make a name's
  rank depend on other names' volatility, which contradicts DESIGN.md. Do not
  reopen without materially more price history or a different market regime.
- Rank/score sparkline (PR #15, closed)
- Universe-wide watchlist correlation matrix
- Covariance toggle
- MAX DD filter
- Market-cap column in the main ranking table
- Correlation adjustment inside risk-equivalent sizing V1
- Speculative framework migration
- TypeScript or bundler adoption
- Simulated iPhone haptics
- Near-term universe-wide correlation deduplication
