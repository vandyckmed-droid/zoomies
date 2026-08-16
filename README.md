# zoomies

A 12–1 momentum ranking of the largest US-traded common stocks.

This repo doubles as the cache: the downloaded price history lives in `data/`,
so later sessions only fetch the trading days they are missing. A rerun that is
already up to date makes no API calls at all and rewrites no files.

Rebuilding all 1,000 names from scratch takes a few minutes; after that a rerun
takes about a second. If the API plan's quota runs out mid-build, the run keeps
going from cache and says how many names are still missing — rerun later and it
picks up where it stopped.

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
not by oversight. Both loaders write onto the same in-memory table, so
whichever runs first, the other needs no further fetches — opening a detail
panel once effectively pre-loads the pair matrix for the rest of the session.

Series are stored as integers scaled by 1e6 to keep both formats small;
correlation is unaffected by the scaling and covariance divides it back out.

## Filtering

Three filters sit above the table: a minimum score, a maximum annualized
volatility, and watchlist-only. They combine with the search box, and a clear
link appears whenever any of them is active. Columns sort on rank, ticker,
score, return, volatility and market cap.

## State

The page remembers sort, search, scroll position, the open ticker, the theme,
the watchlist, the filters and the pair mode in localStorage, so reopening it lands exactly
where you left off. The theme button cycles auto (follow the device) →
light → dark.
