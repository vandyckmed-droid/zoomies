#!/usr/bin/env python3
"""Rank large-cap US stocks by their 12-1 momentum score.

Usage:
    API_KEY=<fmp key> python3 build.py [--refresh-universe]
    python3 build.py --offline          # recompute from cache, no key needed

Writes:
    data/universe.json   the tracked universe (cached, refreshed weekly)
    data/prices/*.csv    daily adjusted closes (cached, updated incrementally)
    scores.js            the table that index.html renders
    returns.js           return series, loaded only for watchlist comparisons
"""

import csv
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

API = "https://financialmodelingprep.com/stable"
API_KEY = os.environ.get("API_KEY", "")

# Overridable from the environment so the rebuild workflow can pass a size in
# without editing the file -- see .github/workflows/rebuild.yml.
UNIVERSE_SIZE = int(os.environ.get("UNIVERSE_SIZE") or 1000)   # names to track
DISPLAY_COUNT = int(os.environ.get("DISPLAY_COUNT") or UNIVERSE_SIZE)  # names shown
BENCHMARK = "SPY"       # market proxy for beta, alpha and R squared
RETURN_SCALE = 1000000  # return series are stored as scaled integers
MIN_OVERLAP = 120       # aligned days needed before a regression is meaningful
LOOKBACK = int(os.environ.get("LOOKBACK") or 252)   # trading days in the window
SKIP = int(os.environ.get("SKIP") or 21)            # most recent days excluded
HISTORY_DAYS = 730      # calendar days of prices to keep (~2 years)
UNIVERSE_MAX_AGE = 7    # days before the universe is rebuilt

ROOT = os.path.dirname(os.path.abspath(__file__))
PRICE_DIR = os.path.join(ROOT, "data", "prices")
UNIVERSE_FILE = os.path.join(ROOT, "data", "universe.json")
OUTPUT_FILE = os.path.join(ROOT, "scores.js")
RETURNS_FILE = os.path.join(ROOT, "returns.js")

US_EXCHANGES = {"NASDAQ", "NYSE", "AMEX"}

# FMP suffixes for instruments that are not common equity.
NON_COMMON_SUFFIX = re.compile(r"^(P[A-Z]?|W[TS]?|U[N]?|R[T]?|CL|CV)$")

# Noise to strip before comparing company names for duplicate share classes.
NAME_NOISE = re.compile(
    r"\b(class\s+[a-z]|american\s+depositary\s+(shares?|receipts?)|adr|"
    r"ordinary\s+shares?|common\s+stock|inc|incorporated|corp|corporation|"
    r"company|co|plc|ltd|limited|holdings?|group|the|s\.?a|n\.?v|a\.?g|se|ab|a/s)\b"
)


class RateLimited(Exception):
    """The API plan's request quota is spent."""


def api_get(path, **params):
    """GET an FMP endpoint, retrying on transient failures."""
    params["apikey"] = API_KEY
    url = "%s/%s?%s" % (API, path, urllib.parse.urlencode(params))
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                payload = json.loads(resp.read().decode())
            if isinstance(payload, dict) and "Error Message" in payload:
                raise RateLimited(payload["Error Message"][:120])
            return payload
        except urllib.error.HTTPError as exc:
            # Quota and plan errors will not clear by trying again.
            if exc.code in (402, 403, 429):
                raise RateLimited("HTTP %d on %s" % (exc.code, path))
            if attempt == 3:
                raise
            print("  retrying (%s)" % exc)
            time.sleep(2 ** attempt)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt == 3:
                raise
            print("  retrying (%s)" % exc)
            time.sleep(2 ** attempt)


def normalized_name(name):
    """Collapse a company name so duplicate share classes compare equal."""
    name = re.sub(r"[^a-z0-9\s]", " ", name.lower())
    name = NAME_NOISE.sub(" ", name)
    return " ".join(name.split())


def is_common_stock(row):
    symbol = row["symbol"]
    if row.get("isEtf") or row.get("isFund") or not row.get("isActivelyTrading"):
        return False
    if row.get("exchangeShortName") not in US_EXCHANGES:
        return False
    if "." in symbol:                       # foreign line, e.g. MU.TO
        return False
    if "-" in symbol:                       # BRK-B is fine, MER-PK is not
        return not NON_COMMON_SUFFIX.match(symbol.split("-", 1)[1])
    return True


def build_universe():
    """The largest US-traded common stocks, one line per company."""
    print("Building universe...")
    rows = api_get(
        "company-screener",
        marketCapMoreThan=3_000_000_000,
        isEtf="false",
        isFund="false",
        isActivelyTrading="true",
        limit=3000,
    )
    rows = [r for r in rows if r.get("marketCap") and is_common_stock(r)]
    rows.sort(key=lambda r: -r["marketCap"])

    # One company, one ticker: keep the most heavily traded share class.
    best = {}
    for row in rows:
        key = normalized_name(row["companyName"])
        liquidity = (row.get("price") or 0) * (row.get("volume") or 0)
        if key not in best or liquidity > best[key][0]:
            best[key] = (liquidity, row)

    kept = sorted((r for _, r in best.values()), key=lambda r: -r["marketCap"])
    universe = [
        {
            "symbol": r["symbol"],
            "name": r["companyName"],
            "marketCap": r["marketCap"],
            "exchange": r["exchangeShortName"],
        }
        for r in kept[:UNIVERSE_SIZE]
    ]
    os.makedirs(os.path.dirname(UNIVERSE_FILE), exist_ok=True)
    with open(UNIVERSE_FILE, "w") as fh:
        json.dump({"asOf": date.today().isoformat(), "stocks": universe}, fh, indent=1)
    print("  %d names, %s ... %s" % (len(universe), universe[0]["symbol"], universe[-1]["symbol"]))
    return universe


def load_universe(refresh, offline=False):
    if offline:
        if not os.path.exists(UNIVERSE_FILE):
            sys.exit("--offline needs a cached %s" % os.path.basename(UNIVERSE_FILE))
        with open(UNIVERSE_FILE) as fh:
            cached = json.load(fh)
        print("Universe: %d names from cache (offline)" % len(cached["stocks"]))
        return cached["stocks"]
    if not refresh and os.path.exists(UNIVERSE_FILE):
        with open(UNIVERSE_FILE) as fh:
            cached = json.load(fh)
        age = (date.today() - date.fromisoformat(cached["asOf"])).days
        if age <= UNIVERSE_MAX_AGE and len(cached["stocks"]) == UNIVERSE_SIZE:
            print("Universe: %d names cached %d day(s) ago" % (len(cached["stocks"]), age))
            return cached["stocks"]
    return build_universe()


def price_path(symbol):
    return os.path.join(PRICE_DIR, "%s.csv" % symbol.replace("/", "_"))


def read_prices(symbol):
    """Cached history as an ordered {date: adjusted close} mapping."""
    path = price_path(symbol)
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        return {row["date"]: float(row["adj_close"]) for row in csv.DictReader(fh)}


def write_prices(symbol, prices):
    os.makedirs(PRICE_DIR, exist_ok=True)
    with open(price_path(symbol), "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["date", "adj_close"])
        for day in sorted(prices):
            writer.writerow([day, "%.6f" % prices[day]])


def latest_session(today):
    """The most recent weekday, i.e. the newest bar that could exist yet."""
    while today.weekday() > 4:
        today -= timedelta(days=1)
    return today


def update_prices(symbol, verbose=True):
    """Return the full history, downloading only the days we are missing."""
    prices = read_prices(symbol)
    today = date.today()

    # Already holding the newest bar that can exist: no request at all.
    if prices and max(prices) >= latest_session(today).isoformat():
        if verbose:
            print("  %-6s current (%d days)" % (symbol, len(prices)))
        return prices

    start = today - timedelta(days=HISTORY_DAYS)
    if prices:
        # Refetch the last cached day too, so splits/dividends restate cleanly.
        start = max(start, date.fromisoformat(max(prices)))

    bars = api_get(
        "historical-price-eod/dividend-adjusted",
        symbol=symbol,
        **{"from": start.isoformat(), "to": today.isoformat()}
    )
    fetched = {b["date"]: float(b["adjClose"]) for b in bars if b.get("adjClose")}
    if not fetched and not prices:
        print("  %-6s no data" % symbol)
        return {}

    before = dict(prices)
    prices.update(fetched)
    cutoff = (today - timedelta(days=HISTORY_DAYS)).isoformat()
    prices = {d: p for d, p in prices.items() if d >= cutoff}
    if prices != before:                      # only touch the file on a change
        write_prices(symbol, prices)
    added = len(set(prices) - set(before))
    if verbose:
        print("  %-6s +%d new (%d days)" % (symbol, added, len(prices)))
    return prices


def log_returns(prices):
    """Daily log returns keyed by date."""
    days = sorted(prices)
    out = {}
    for a, b in zip(days, days[1:]):
        if prices[a] > 0 and prices[b] > 0:
            out[b] = math.log(prices[b] / prices[a])
    return out


def market_window(prices):
    """The benchmark's 12-1 window, used as the common date axis."""
    days = sorted(log_returns(prices))
    if len(days) < LOOKBACK + SKIP:
        sys.exit("benchmark %s has too little history" % BENCHMARK)
    return days[-(LOOKBACK + SKIP):-SKIP]


def align(returns, dates):
    """A stock's returns on the benchmark's date axis, None where it did not trade."""
    return [returns.get(d) for d in dates]


def regress(stock, market):
    """Beta, annualized alpha and R squared against the benchmark."""
    pairs = [(s, m) for s, m in zip(stock, market) if s is not None and m is not None]
    if len(pairs) < MIN_OVERLAP:
        return None

    xs = [m for _, m in pairs]
    ys = [s for s, _ in pairs]
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None

    beta = sxy / sxx
    return {
        "beta": beta,
        "alpha": (my - beta * mx) * 252,   # annualized, no risk-free adjustment
        "r2": (sxy * sxy) / (sxx * syy),
    }


def drawdown(prices, dates):
    """Deepest peak-to-trough fall in adjusted close across the given days.

    Depth is negative (or zero when the series only ever rose), and the peak it
    is measured from is the running high, so the trough always follows it.
    """
    peak = peak_day = None
    worst = {"maxDrawdown": 0.0, "ddPeak": None, "ddTrough": None}
    for day in dates:
        price = prices[day]
        if peak is None or price > peak:
            peak, peak_day = price, day
        elif peak > 0 and price / peak - 1.0 < worst["maxDrawdown"]:
            worst = {
                "maxDrawdown": price / peak - 1.0,
                "ddPeak": peak_day,
                "ddTrough": day,
            }
    return worst


def score(prices):
    """12-1 momentum: risk-adjusted drift over 252 days, skipping the last 21."""
    series = [prices[d] for d in sorted(prices)]
    returns = [math.log(b / a) for a, b in zip(series, series[1:]) if a > 0 and b > 0]
    if len(returns) < LOOKBACK + SKIP:
        return None

    window = returns[-(LOOKBACK + SKIP):-SKIP]
    mean = statistics.fmean(window)
    vol = statistics.stdev(window)
    if vol == 0:
        return None

    dates = sorted(prices)[-(LOOKBACK + SKIP + 1):-SKIP]
    return dict(drawdown(prices, dates), **{
        "score": mean / vol * math.sqrt(252),
        "annReturn": mean * 252,
        "annVol": vol * math.sqrt(252),
        "meanDaily": mean,
        "dailyVol": vol,
        "windowReturn": math.expm1(sum(window)),
        "skipReturn": math.expm1(sum(returns[-SKIP:])),
        "windowStart": dates[0],
        "windowEnd": dates[-1],
        "days": len(window),
    })


def write_returns(series):
    """The return series, one ticker per line so diffs stay readable.

    Kept out of scores.js because the page only needs them when comparing
    watchlist names, and they are five times the size of everything else.
    """
    lines = ['"%s":%s' % (sym, json.dumps(vals, separators=(",", ":")))
             for sym, vals in sorted(series.items())]
    with open(RETURNS_FILE, "w") as fh:
        fh.write("// Generated by build.py -- do not edit.\n")
        fh.write("const RETURNS = {\n%s\n};\n" % ",\n".join(lines))
    print("Wrote returns.js: %d series, %.0f KB"
          % (len(series), os.path.getsize(RETURNS_FILE) / 1024))


def main():
    # Offline recomputes scores from the committed cache. It is what to use
    # after changing the maths: no key, no requests, same numbers every run.
    offline = "--offline" in sys.argv
    if not API_KEY and not offline:
        sys.exit("API_KEY is not set (or pass --offline to rebuild from cache)")

    # A window longer than the cache can reach scores nothing, which looks like
    # a data fault rather than the config error it is. ~5 trading days a week.
    reachable = HISTORY_DAYS * 5 // 7
    if LOOKBACK + SKIP > reachable - 20:
        sys.exit("LOOKBACK+SKIP is %d days, but HISTORY_DAYS=%d only reaches ~%d"
                 % (LOOKBACK + SKIP, HISTORY_DAYS, reachable))
    print("Window: %d-day lookback, %d skipped, %d names"
          % (LOOKBACK, SKIP, UNIVERSE_SIZE))

    universe = load_universe("--refresh-universe" in sys.argv, offline)

    print("Updating benchmark %s..." % BENCHMARK)
    market_prices = read_prices(BENCHMARK) if offline else update_prices(BENCHMARK)
    if not market_prices:
        sys.exit("no cached prices for benchmark %s" % BENCHMARK)
    axis = market_window(market_prices)                  # shared date axis
    market = align(log_returns(market_prices), axis)
    print("  axis: %d days, %s to %s" % (len(axis), axis[0], axis[-1]))

    print("Updating prices for %d names..." % len(universe))
    rows, window, limited, series = [], None, None, {}
    for i, stock in enumerate(universe, 1):
        if offline or limited:
            prices = read_prices(stock["symbol"])       # cache only
        else:
            try:
                prices = update_prices(stock["symbol"], verbose=len(universe) <= 60)
            except RateLimited as exc:
                limited = exc
                print("  quota reached at %s (%s)" % (stock["symbol"], exc))
                print("  continuing from cache; rerun later to fill the rest")
                prices = read_prices(stock["symbol"])
        if len(universe) > 60 and (i % 50 == 0 or i == len(universe)):
            print("  %d/%d" % (i, len(universe)))
        result = score(prices) if prices else None
        row = {
            "symbol": stock["symbol"],
            "name": stock["name"],
            "exchange": stock["exchange"],
            "marketCap": stock["marketCap"],
            "lastClose": prices[max(prices)] if prices else None,
            "lastDate": max(prices) if prices else None,
            "historyDays": len(prices),
            "score": None,
            "annReturn": None,
            "annVol": None,
            "maxDrawdown": None,
        }
        # Extra detail for the per-stock panel in index.html.
        for field in ("score", "annReturn", "annVol", "maxDrawdown",
                      "ddPeak", "ddTrough", "meanDaily", "dailyVol",
                      "windowReturn", "skipReturn", "windowStart", "windowEnd"):
            row[field] = result[field] if result else None

        # Market stats, plus the aligned return series the browser needs for
        # pair statistics. Those ship separately — see write_returns.
        aligned = align(log_returns(prices), axis) if prices else None
        fit = regress(aligned, market) if aligned else None
        for field in ("beta", "alpha", "r2"):
            row[field] = fit[field] if fit else None
        if aligned:
            series[stock["symbol"]] = [
                None if r is None else int(round(r * RETURN_SCALE)) for r in aligned
            ]
        rows.append(row)
        if result and not window:
            window = (result["windowStart"], result["windowEnd"])

    scored = sum(1 for r in rows if r["score"] is not None)
    report = {
        "generated": date.today().isoformat(),
        "windowStart": window[0] if window else None,
        "windowEnd": window[1] if window else None,
        "lookback": LOOKBACK,
        "skip": SKIP,
        "displayCount": DISPLAY_COUNT,
        "benchmark": BENCHMARK,
        "minOverlap": MIN_OVERLAP,
        "returnScale": RETURN_SCALE,
        "universe": rows,
    }
    with open(OUTPUT_FILE, "w") as fh:
        fh.write("// Generated by build.py -- do not edit.\n")
        fh.write("const REPORT = %s;\n" % json.dumps(report, indent=1))

    write_returns(series)
    print("Wrote scores.js: %d of %d names scored, window %s to %s"
          % (scored, len(rows), report["windowStart"], report["windowEnd"]))
    if limited:
        missing = sum(1 for r in rows if not r["historyDays"])
        print("Incomplete: %d name(s) have no cached prices yet." % missing)


if __name__ == "__main__":
    main()
