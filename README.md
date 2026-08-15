# zoomies

A 12–1 momentum ranking of the largest US-traded common stocks.

This repo doubles as the cache: the downloaded price history lives in `data/`,
so later sessions only fetch the trading days they are missing. A rerun that is
already up to date makes no API calls at all and rewrites no files.

Rebuilding all 500 names from scratch takes a few minutes; after that a rerun
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

## Files

| Path                | Purpose                                                     |
| ------------------- | ----------------------------------------------------------- |
| `build.py`          | Picks the universe, updates the cache, computes the scores. |
| `data/universe.json`| The 500 tracked names, with market caps.                    |
| `data/prices/*.csv` | Cached daily adjusted closes, ~2 years per ticker.          |
| `scores.js`         | Generated table data, loaded by `index.html`.               |
| `index.html`        | The ranking table.                                          |

## Universe

The 500 largest US-traded common stocks by market cap, from the FMP screener:

- ETFs, funds, preferreds, warrants, rights and units are excluded.
- Only NASDAQ / NYSE / AMEX lines are kept, so foreign cross-listings of the same
  company (e.g. `MU.TO`) drop out.
- Duplicate share classes are collapsed to the most heavily traded line, so
  `GOOGL` is kept over `GOOG` and `BRK-B` over `BRK-A`.

US-listed ADRs (`TSM`, `ASML`, `ARM`, …) are included — they are US-traded common
equity.

`index.html` shows the 50 largest of those names; `DISPLAY_COUNT` in `build.py`
controls how many, and `UNIVERSE_SIZE` how many are tracked and cached.
The table sorts, searches and re-renders in under 15ms even at 500 rows.

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
(273 trading days) is shown without a score rather than ranked on partial data;
8 of the current 500 fall in that bucket.

The page follows the system light/dark setting.
