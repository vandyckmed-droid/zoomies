# zoomies

A 12–1 momentum ranking of the largest US-traded common stocks.

This repo doubles as the cache: the downloaded price history lives in `data/`,
so later sessions only fetch the trading days they are missing. A rerun that is
already up to date makes no API calls at all and rewrites no files.

Rebuilding all 1,000 names from scratch takes a few minutes; after that, a
rerun that finds no new prices takes a little over a second — one extra
historical score snapshot per name (see "Percentiles and rank change" below)
adds roughly 30% versus computing only the live score, measured at 1.44s
before that feature existed and 1.87s after, both `--offline` on 1,000
names. If the API plan's quota runs out mid-build, the run keeps going from
cache and says how many names are still missing — rerun later and it picks
up where it stopped.

## Run

```sh
API_KEY=<financialmodelingprep key> python3 build.py
```

Then open `index.html` in a browser. No server, no dependencies — `build.py` uses
only the Python standard library.

Pass `--refresh-universe` to rebuild the stock list immediately; otherwise it is
refreshed automatically once a week.

`python3 build.py --offline` recomputes everything from the committed cache with
no key and no requests — the right thing to run after changing the maths, since
it makes the result reproducible by anyone without an API key.

## Keeping data fresh

`.github/workflows/rebuild.yml` refreshes prices **automatically every night**
at 06:00 UTC — well after US market close and end-of-day settlement — so the
ranking never goes stale from nobody remembering to update it. A run that
finds nothing new (a weekend, a holiday) is a harmless no-op. The nightly
schedule refreshes prices only; the stock list itself changes on `build.py`'s
own weekly staleness check, not every night, so the tracked names don't drift
day to day without an actual rebalance behind it.

If the automation itself stops running — a failing cron, a lapsed API key —
nothing else would tell you short of noticing the numbers look wrong. The
page checks the age of `scores.js`'s `generated` date on load and shows a
visible warning once it is 2+ days old, since a healthy nightly build never
gets older than about a day between a 06:00 UTC run and whenever the page is
opened.

### Rebuilding from a phone, on demand

For anything the nightly schedule doesn't cover — a bigger universe, a
different scoring window, a new factor — **Actions > Rebuild data > Run
workflow** does it instead: universe size, lookback and skip are inputs on
the form, the key comes from the `API_KEY` repository secret, and the
regenerated files are committed so Pages redeploys. No laptop, and the key
never reaches the client.

Filters that only threshold on data already in `scores.js` — score, return,
volatility, drawdown, market cap, beta, alpha, R² — need no rebuild at all;
they are instant and client-side.

## Files

| Path                | Purpose                                                     |
| ------------------- | ----------------------------------------------------------- |
| `build.py`          | Picks the universe, updates the cache, computes the scores. |
| `data/universe.json`| The tracked names, with market caps.                        |
| `data/prices/*.csv` | Cached daily adjusted closes, ~2 years per ticker.          |
| `data/prices/SPY.csv`| The benchmark series for beta, alpha and R².                |
| `scores.js`         | Generated table data, loaded by `index.html`.               |
| `data/returns/*.js` | One return series per ticker, fetched only for starred names — the pair matrix. |
| `returns.js`        | All return series in one file, loaded once for the correlation lists. |
| `index.html`        | The ranking table.                                          |

## Universe

The 1,000 largest US-traded common stocks by market cap, from the FMP screener:

- ETFs, funds, preferreds, warrants, rights and units are excluded.
- Only NASDAQ / NYSE / AMEX lines are kept, so foreign cross-listings of the same
  company (e.g. `MU.TO`) drop out.
- Duplicate share classes are collapsed to the most heavily traded line, so
  `GOOGL` is kept over `GOOG` and `BRK-B` over `BRK-A`.

US-listed ADRs (`TSM`, `ASML`, `ARM`, …) are included — they are US-traded common
equity.

`index.html` shows every tracked name; `DISPLAY_COUNT` in `build.py` controls
how many, and `UNIVERSE_SIZE` how many are tracked and cached. Both read an
environment variable of the same name first, which is how the rebuild workflow
passes a size in without editing the file.

Sorting or filtering re-renders the whole table, so its cost scales with the
number of rows shown. Measured in headless Chromium at a 375px viewport under
4x CPU throttling — a rough stand-in for a mid-range phone — a sort takes about
380ms at 500 names and 880ms at 1,000. Past roughly 1,500 it becomes the
limiting factor, ahead of download size.

## Score

For each stock, from adjusted closes:

1. Daily natural-log returns.
2. A 252-trading-day window that ends 21 trading days ago (the 12–1 window).
3. `mean` and `stdev` of the daily log returns over that window.

```
Score                  = mean / stdev × √252
Annualized return      = mean × 252
Annualized volatility  = stdev × √252
```

Ranked highest score first. A stock listed too recently to fill the window
(273 trading days) is shown without a score rather than ranked on partial data
— 8 names in the last build.

## Market statistics

Each stock is regressed on `SPY` over the same 12–1 window, on the benchmark's
trading calendar, giving beta, annualized alpha (no risk-free adjustment) and R².
A name needs 120 overlapping days before a regression is reported.

The detail panel also lists the five names a stock is most correlated with and
the five it is least correlated with, ranked across every tracked name.

Starring names adds them to a watchlist, which drives a pair matrix below the
table showing correlation or annualized covariance of daily log returns.

Return series load two different ways, because the two features that need
them have opposite shapes of need. The pair matrix only ever needs the
starred names — typically under ten — so `index.html` fetches one small file
per ticker from `data/returns/<symbol>.js` on demand, and starring two names
downloads only those two files. The correlation lists compare one stock
against every other displayed name, so there is no small subset to fetch
instead; they load the single combined `returns.js` once, the first time any
detail panel opens. That was tried the sharded way too — fetching ~1,000
individual files for this measured about 20x slower than one combined file,
even with zero real network latency, so it stayed bulk-loaded deliberately,
not by oversight. Both loaders write onto the same in-memory table, so the
benefit runs one direction: once `returns.js` has loaded — opening any detail
panel — every ticker's series is already present, and the pair matrix needs
no further fetches for the rest of the session. It does not run the other
way — starring names first loads only those tickers' shards, which is not
enough for the correlation lists, so opening a detail panel afterward still
triggers the bulk load.

Series are stored as integers scaled by 1e6 to keep both formats small;
correlation is unaffected by the scaling and covariance divides it back out.

## Percentiles and rank change

The detail panel shows each name's rank, how that rank has moved over the
last 63 trading sessions, and where it sits percentile-wise against the
rest of the universe on four metrics.

**Percentiles** (score, annualized return, annualized volatility, max
drawdown) are computed entirely client-side from fields already in
`scores.js` — no extra build.py work or payload for this half of the
feature. Percentile is the tie-aware fraction of the current scored
universe at or below a name's value on that metric (0–100; ties share the
average rank). Direction is **not** normalized to mean "higher is always
better" — it follows each metric's own stored value, and every label says
so explicitly rather than relying on a remembered convention:

- Score / return: higher percentile = **stronger**.
- Volatility: higher percentile = **more volatile** (not "stronger" — a
  high number here is the riskier end, on purpose).
- Max drawdown: higher percentile = **shallower** (drawdown is stored
  negative, so a value close to zero — the least damage — sits at the top
  of the percentile range).

**63-day rank change** needs data percentiles don't: what every name's
score *would have been* 63 trading sessions ago. `build.py` reconstructs
that from the already-cached price series — no extra API calls — using the
exact same `score()` maths as the live number, just on a copy of each
name's prices trimmed to that one earlier date (`score_asof`). That date
itself is the benchmark's own calendar, 63 sessions back from its most
recent bar (`historical_endpoint`), so every name is compared at the same
market-date endpoint rather than each one's own last-traded day — that is
what keeps the comparison fair when a stock's data has a gap.

Ranking is against **today's displayed cohort** — `REPORT.universe.slice(0,
displayCount)`, the same slice `index.html` already treats as "the tracked
names" everywhere else — not whatever the universe looked like 63 sessions
ago: a name that has since fallen out of the universe contributes nothing
to the historical ranking, and a newly tracked name is ranked on its own
historical score alongside everyone currently tracked. `build.py` restricts
`historicalRank63d` to that same slice explicitly, rather than the full
tracked universe, so the two ends of the comparison are never on different
population sizes even if `DISPLAY_COUNT` is ever configured smaller than
`UNIVERSE_SIZE`.

```
63D rank change = historical rank − current rank
```

Both ranks here are **restricted to names that have a valid historical
score** — not `historical rank − s.rank` (the name's ordinary, unrestricted
current rank). A recently-listed name with no 63-session-old score still
has *today's* score, so it would otherwise occupy a rank slot in the
"current" side of the comparison while being entirely absent from the
"historical" side — shifting every other name's apparent current rank by
one purely because that new name exists, not because anything about their
own momentum changed. `index.html` computes a second, cohort-restricted
current rank (`currentRankFor63d`) over exactly the same set of names that
have a `historicalRank63d`, and only that rank feeds the subtraction above.
The ordinary `Rank` shown elsewhere in the detail panel is unaffected —
this restriction exists only for the 63D comparison's own fairness, not for
how rank is displayed generally.

The detail panel shows both cohort ranks the change is actually computed
from — `63D rank: #5 → #2` — rather than just the historical end next to a
number that would not match if recomputed against the ordinary `Rank`
shown above it. Displaying `#5` alone next to a `+3` that a reader would
naturally (and wrongly) recompute against a `Rank` from a different
population made a correct number look wrong.

Positive means the name's rank improved (a lower rank number) over the
window; negative means it got worse. `#412 → #73` is `+339`; `#18 → #190`
is `−172`. A name too newly qualified to have had a valid score 63 sessions
back — or, in principle, one where the price cache itself does not yet
reach back that far — gets no historical rank and no rank change, *for
either side of the comparison*: it is excluded from the cohort entirely,
not just left with a null `historicalRank63d`. The detail panel says so
plainly ("not enough history 63 sessions ago") rather than showing a blank
or a misleading zero, regardless of how highly that name currently ranks
overall. `build.py` checks at startup whether `HISTORY_DAYS` can even reach
`LOOKBACK + SKIP + 63` days back and refuses to run rather than silently
shipping a rank change nobody should trust if not — at the shipped
defaults (252 + 21 + 63 = 336 against ~521 reachable trading days) this has
a wide margin and should not come up in practice.

This one extra historical snapshot per name — not a repeated
recomputation across many dates — is what keeps the cost small: about
+30% on an otherwise-instant `--offline` rerun (1.44s → 1.87s measured on
1,000 names) and about 29 KB added to `scores.js` (728 KB → 757 KB, one
nullable integer per row). Percentiles cost nothing extra either way, since
they are derived client-side from data already shipped.

63D rank change is also a sortable column in the main table, surfacing the
biggest 63-day climbers or decliners across the whole universe. The column
itself hides at phone width, same as max drawdown, but sorting by it is the
main point of the feature (not just a detail worth losing on the primary
device) — a compact **63D** button next to the row count stays reachable
at every width and triggers the identical sort the hidden header would.
Percentiles are detail-panel-only: four more numeric columns would not
stay clean at phone width, so they were left out of the table rather than
forced in.

## Filtering

Filters sit above the table: a minimum score, a maximum annualized
volatility, a maximum drawdown, a sector, and watchlist-only. They combine
with the search box, and a clear link appears whenever any of them is
active. Columns sort on rank, ticker, score, return, volatility and market
cap.

Sector comes straight from the FMP screener response used to build the
universe, at no extra request cost, and is otherwise unused by the scoring
math — it only drives this filter and a line in the detail panel. The
options list is whatever sectors are actually present in the current
universe, so it changes as the tracked names change. A name FMP does not
tag with a sector has none to filter by and is simply excluded from every
sector option, the same way an unscored name is excluded from the score and
volatility filters.

## State

The page remembers sort, search, scroll position, the open ticker, the theme,
the watchlist, the filters and the pair mode in localStorage, so reopening it lands exactly
where you left off. The theme button cycles auto (follow the device) →
light → dark.
