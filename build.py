#!/usr/bin/env python3
"""Rank large-cap US stocks by their 12-1 momentum score.

Usage:
    API_KEY=<fmp key> python3 build.py [--refresh-universe]

Writes:
    data/universe.json   the 50-name universe (cached, refreshed weekly)
    data/prices/*.csv    daily adjusted closes (cached, updated incrementally)
    scores.js            the table that index.html renders
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

UNIVERSE_SIZE = 50      # names to track
DISPLAY_COUNT = 10      # names shown in index.html (proof of concept)
LOOKBACK = 252          # trading days in the scoring window
SKIP = 21               # most recent trading days excluded
HISTORY_DAYS = 730      # calendar days of prices to keep (~2 years)
UNIVERSE_MAX_AGE = 7    # days before the universe is rebuilt

ROOT = os.path.dirname(os.path.abspath(__file__))
PRICE_DIR = os.path.join(ROOT, "data", "prices")
UNIVERSE_FILE = os.path.join(ROOT, "data", "universe.json")
OUTPUT_FILE = os.path.join(ROOT, "scores.js")

US_EXCHANGES = {"NASDAQ", "NYSE", "AMEX"}

# FMP suffixes for instruments that are not common equity.
NON_COMMON_SUFFIX = re.compile(r"^(P[A-Z]?|W[TS]?|U[N]?|R[T]?|CL|CV)$")

# Noise to strip before comparing company names for duplicate share classes.
NAME_NOISE = re.compile(
    r"\b(class\s+[a-z]|american\s+depositary\s+(shares?|receipts?)|adr|"
    r"ordinary\s+shares?|common\s+stock|inc|incorporated|corp|corporation|"
    r"company|co|plc|ltd|limited|holdings?|group|the|s\.?a|n\.?v|a\.?g|se|ab|a/s)\b"
)


def api_get(path, **params):
    """GET an FMP endpoint, retrying on transient failures."""
    params["apikey"] = API_KEY
    url = "%s/%s?%s" % (API, path, urllib.parse.urlencode(params))
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                return json.loads(resp.read().decode())
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
        marketCapMoreThan=50_000_000_000,
        isEtf="false",
        isFund="false",
        isActivelyTrading="true",
        limit=500,
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


def load_universe(refresh):
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


def update_prices(symbol):
    """Return the full history, downloading only the days we are missing."""
    prices = read_prices(symbol)
    today = date.today()
    start = today - timedelta(days=HISTORY_DAYS)
    if prices:
        # Refetch the last cached day too, so splits/dividends restate cleanly.
        start = max(start, date.fromisoformat(max(prices)))
    if prices and start >= today:
        print("  %-6s cached (%d days)" % (symbol, len(prices)))
        return prices

    bars = api_get(
        "historical-price-eod/dividend-adjusted",
        symbol=symbol,
        **{"from": start.isoformat(), "to": today.isoformat()}
    )
    fetched = {b["date"]: float(b["adjClose"]) for b in bars if b.get("adjClose")}
    if not fetched and not prices:
        print("  %-6s no data" % symbol)
        return {}

    prices.update(fetched)
    cutoff = (today - timedelta(days=HISTORY_DAYS)).isoformat()
    prices = {d: p for d, p in prices.items() if d >= cutoff}
    write_prices(symbol, prices)
    print("  %-6s +%d new (%d days)" % (symbol, len(fetched), len(prices)))
    return prices


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
    return {
        "score": mean / vol * math.sqrt(252),
        "annReturn": mean * 252,
        "annVol": vol * math.sqrt(252),
        "windowStart": dates[0],
        "windowEnd": dates[-1],
        "days": len(window),
    }


def main():
    if not API_KEY:
        sys.exit("API_KEY is not set")

    universe = load_universe("--refresh-universe" in sys.argv)

    print("Updating prices...")
    rows, window = [], None
    for stock in universe:
        prices = update_prices(stock["symbol"])
        result = score(prices) if prices else None
        rows.append({
            "symbol": stock["symbol"],
            "name": stock["name"],
            "marketCap": stock["marketCap"],
            "score": result["score"] if result else None,
            "annReturn": result["annReturn"] if result else None,
            "annVol": result["annVol"] if result else None,
        })
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
        "universe": rows,
    }
    with open(OUTPUT_FILE, "w") as fh:
        fh.write("// Generated by build.py -- do not edit.\n")
        fh.write("const REPORT = %s;\n" % json.dumps(report, indent=1))

    print("Wrote scores.js: %d of %d names scored, window %s to %s"
          % (scored, len(rows), report["windowStart"], report["windowEnd"]))


if __name__ == "__main__":
    main()
