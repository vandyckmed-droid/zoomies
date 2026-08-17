# zoomies

A 12–1 momentum ranking of the largest US-traded common stocks.

This repo doubles as the cache: the downloaded price history lives in `data/`, so later sessions only fetch the trading days they are missing. A rerun that is already up to date makes no API calls at all and rewrites no files. Rebuilding all 1,000 names from scratch takes a few minutes; after that, a rerun that finds no new prices takes a little over a second.

## Run

```sh
API_KEY=<financialmodelingprep key> python3 build.py
```

Then open `index.html` in a browser. No server, no dependencies — `build.py` uses only the Python standard library.

Pass `--refresh-universe` to rebuild the stock list immediately; otherwise it is refreshed automatically once a week. `python3 build.py --offline` recomputes everything from the committed cache with no key and no requests — the right thing to run after changing the maths.

## Keeping data fresh

`.github/workflows/rebuild.yml` refreshes prices **automatically every night** at 06:00 UTC — well after US market close — so the ranking never goes stale. The nightly schedule refreshes prices only; the stock list itself changes on `build.py`'s own weekly staleness check, not every night, so the tracked names don't drift day to day without an actual rebalance.

The page checks the age of `scores.js`'s `generated` date on load and shows a visible warning once it is 2+ days old, since a healthy nightly build never gets older than about a day between a 06:00 UTC run and whenever the page is opened.

### Rebuilding from a phone, on demand

For anything the nightly schedule doesn't cover — a bigger universe, a different scoring window — **Actions > Rebuild data > Run workflow** does it instead: universe size, lookback and skip are inputs on the form, the key comes from the `API_KEY` repository secret, and the regenerated files are committed so Pages redeploys.

Filters that only threshold on data already in `scores.js` — score, return, volatility, drawdown, market cap, beta, alpha, R² — are instant and client-side; they need no rebuild at all.

## Files

| Path                | Purpose                                                     |
| ------------------- | ----------------------------------------------------------- |
| `build.py`          | Picks the universe, updates the cache, computes the scores. |
| `data/universe.json`| The tracked names, with market caps.                        |
| `data/prices/*.csv` | Cached daily adjusted closes, ~2 years per ticker.          |
| `data/prices/SPY.csv`| The benchmark series for beta, alpha and R².                |
| `scores.js`         | Generated table data, loaded by `index.html`.               |
| `data/returns/*.js` | One return series per ticker, fetched only for starred names — the ranked watchlist pairs list. |
| `returns.js`        | All return series in one file, for the correlation lists.   |
| `index.html`        | The ranking table.                                          |

## Universe

The 1,000 largest US-traded common stocks by market cap, from the FMP screener. ETFs, funds, preferreds, warrants, rights and units are excluded. Only NASDAQ / NYSE / AMEX lines are kept, so foreign cross-listings of the same company drop out. Duplicate share classes are collapsed to the most heavily traded line. US-listed ADRs are included.

`UNIVERSE_SIZE` in `build.py` controls how many are tracked and cached; it reads an environment variable of the same name first, which is how the rebuild workflow passes a size in.

Sorting or filtering re-renders the whole table, so its cost scales with the number of rows shown. Measured in headless Chromium at a 375px viewport under 4x CPU throttling, a sort takes about 380ms at 500 names and 880ms at 1,000.

Ticker symbols are bolder than the rest of the row (weight 700 vs. the row's default), and row padding runs about 9% tighter than it used to, both purely cosmetic — the eye anchors on the ticker when scanning a long list quickly. The padding reduction keeps row tap targets well above the 44px accessible minimum at every phone width.

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

Ranked highest score first. A stock listed too recently to fill the window (273 trading days) is shown without a score rather than ranked on partial data.

## Market statistics

Each stock is regressed on `SPY` over the same 12–1 window, giving beta, annualized alpha (no risk-free adjustment) and R². A name needs 120 overlapping days before a regression is reported. The detail panel also lists the five names a stock is most correlated with and the five it is least correlated with, ranked across every tracked name.

The detail panel also shows a 52-week range: the low and high adjusted close over the trailing 52 calendar weeks ending on the name's latest cached trading date, with the latest close marked between them. This is independent of the 12–1 score, so a name without enough history to be scored can still show one.

Starring names adds them to a watchlist, which drives a ranked "most correlated pairs" list below the table: every unique pair of starred names, highest correlation first, each with a one-tap action to drop the lower-ranked of the two.

## Percentiles and rank change

The detail panel shows each name's rank, how that rank has moved over the last 63 trading sessions, and where it sits percentile-wise against the rest of the universe on four metrics (score, annualized return, annualized volatility, max drawdown).

**Percentiles** are computed entirely client-side from fields already in `scores.js` — no extra build.py work or payload. Percentile is the tie-aware fraction of the current scored universe at or below a name's value on that metric (0–100).

**63-day rank change** uses data from 63 trading sessions ago: `build.py` reconstructs what every name's score *would have been* from the cached price series using the exact same `score()` maths as the live number. Ranking is against **today's tracked cohort** — every name in `REPORT.universe` — not whatever the universe looked like 63 sessions ago. The detail panel shows this as a compact line: `Rank #5 (+3 in 3m)`. Positive means the name's rank improved (a lower rank number) over the window; negative means it got worse.

Both percentiles and 63D rank change are **detail-panel-only** — neither has a main-table column.

## Filtering

Filters sit above the table: a minimum score, a maximum annualized volatility, a sector, and watchlist-only. Columns sort on rank, ticker, score, return, volatility and market cap.

Sector comes straight from the FMP screener response at no extra request cost, and is otherwise unused by the scoring math. The options list is whatever sectors are actually present in the current universe, so it changes as the tracked names change.

## State

The page remembers sort, search, scroll position, the open ticker, the theme, the watchlist and the filters in localStorage, so reopening it lands exactly where you left off. The theme button cycles auto (follow the device) → light → dark.

---

See [AGENTS.md](AGENTS.md) for the working agreement and collaboration workflow.

See [DESIGN.md](DESIGN.md) for durable design principles.
