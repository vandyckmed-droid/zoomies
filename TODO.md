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

- Volatility-floor scoring (Agent 3, Research Lane). Question: does unusually
  low realized volatility give too much ranking advantage? Candidates: baseline
  no floor; naive 20/22/25%; one-sided 20/22/25%; adaptive one-sided 20th and
  25th percentile. One-sided = positive-return names use max(realized vol,
  floor); zero/negative-return names keep the existing score. Known pathology:
  a naive floor improves negative scores by making them less negative — Agent 3
  is quantifying this. Permitted conclusions: KEEP CURRENT SCORE; fixed
  one-sided 20/22/25%; adaptive 20th; adaptive 25th; INCONCLUSIVE — GATHER MORE
  HISTORY. No production change approved. Return path: Agent 3 → Chief of Staff
  → Agent 2 independent review → Product Owner decision → only then Agent 1.

## Next

- Risk-equivalent dollar size, V1 (Fast Lane, high priority). Display a rounded
  dollar amount representing approximately equal standalone daily volatility
  risk across stocks. Target one-standard-deviation daily move of about ±$10.
  Size = 10 x sqrt(252) / annualized volatility, rounded to nearest $100.
  Standalone volatility only; no correlation adjustment in V1. No holdings data,
  no personalized position management. Not presented as a literal "Buy $X"
  recommendation. Candidate labels: SIZE or RISK $.
- Cosmetic bundle (Fast Lane). Two adjacent surfaces, one PR.
  (a) Watchlist pair rows: move the correlation value inward, use a compact
      minus control at far right, drop the repeated ticker from the remove
      button. Target shape: "BTSG <-> ASX   0.31                 -"
  (b) Detail panel polish: long-value/date alignment, typography, light-mode
      muted-text contrast, better-integrated close control.

## Research Queue

- Candidate -> Watchlist correlation. While scanning rankings, see whether a
  candidate is already highly correlated with watchlist names. Possible later
  extensions: redundancy warning on add, diversification summary, candidate
  comparison, correlation-aware selection.
- Universe tab scope. Goal is understanding the population, not a generic
  dashboard. Must go through Agent 3 before any build.
- Risk/return map. Natural Universe candidate; research and design first.
- Proper per-ticker price graph. Real price-vs-time, not a rank sparkline.
  Needs deliberate payload/data/UI design; possible per-symbol price-history
  shards mirroring the return shards.

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
