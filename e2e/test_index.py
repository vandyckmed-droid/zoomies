"""Browser smoke tests for index.html.

Everything else CI runs -- ruff, compileall, JSON parsing, node --check -- can
only prove the files are well formed. Both real bugs found in this repo so far
were behavioural: a dropped callback that left the correlation panel on
"loading..." forever, and a null lastClose that made a row do nothing when
tapped. Neither is reachable without running the page, so these tests do.

They live in e2e/ rather than tests/ on purpose. ci.yml's Python test step runs
`unittest discover -s tests`, which has no Playwright available; putting them
under tests/ would either turn that step red or -- worse -- leave it reporting
a green "OK" on zero collected tests.
"""

import datetime
import json
import os
import pathlib
import shutil
import tempfile
import unittest

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
SITE = "file://%s/index.html" % ROOT


def launch(pw):
    """Chromium, however this environment happens to provide it."""
    try:
        return pw.chromium.launch()
    except Exception:
        # A sandbox may ship a chromium whose revision predates the installed
        # playwright build. CI installs a matching one, so this is a local
        # convenience rather than something CI depends on.
        base = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        if not base:
            raise
        for pattern in ("chromium-*/chrome-linux/chrome",
                        "chromium_headless_shell-*/chrome-linux/headless_shell"):
            found = sorted(pathlib.Path(base).glob(pattern))
            if found:
                return pw.chromium.launch(executable_path=str(found[-1]))
        raise


def report():
    src = (ROOT / "scores.js").read_text()
    return json.loads(src[src.index("{"):src.rindex(";")])


class BrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = launch(cls.pw)
        cls.report = report()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def page(self, width=1280, height=900, url=SITE):
        """A fresh context, so localStorage never leaks between tests."""
        ctx = self.browser.new_context(viewport={"width": width, "height": height})
        self.addCleanup(ctx.close)
        page = ctx.new_page()
        page.errors = []
        page.on("pageerror", lambda e: page.errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector("#rows tr")
        return page

    def test_cold_load_renders_every_row_without_error(self):
        # Fresh load defaults MIN SCORE to 1, which filters out stocks with score < 1
        page = self.page()
        rows = page.eval_on_selector_all("#rows tr", "e => e.length")
        # Count expected rows: all stocks with score >= 1, plus stocks with null score that pass the filter
        # (unscored names have null score and are filtered out when minScore is not null)
        expected = sum(1 for s in self.report["universe"] if s["score"] is None or s["score"] >= 1)
        # But unscored names are actually excluded by the filter logic when minScore is set
        expected = sum(1 for s in self.report["universe"] if s["score"] is not None and s["score"] >= 1)
        self.assertEqual(rows, expected)
        self.assertEqual(page.errors, [])

    def test_restore_path_resolves_the_correlation_panel(self):
        """The dropped-callback race, which shipped once.

        renderPairs() (per-ticker shards) and openDetail() -> renderCorrelations()
        (bulk returns.js) both ask for their return data within a couple of
        frames of a reload -- two independent loaders now, not one, so this is
        also the regression test for the hybrid design not reintroducing the
        original bug in a new shape. If either caller's callback is dropped,
        its panel sits on "loading..." forever with no error shown.
        """
        page = self.page()
        # Use high-scoring stocks that are visible with default MIN SCORE = 1
        a, b = "AAPL", "GOOGL"
        page.click('.star[data-star="%s"]' % a)
        page.click('.star[data-star="%s"]' % b)
        page.click("#rows tr:first-child td.ticker")
        page.wait_for_selector("#overlay:not([hidden])")
        page.wait_for_timeout(200)

        page.reload()
        page.wait_for_selector("#rows tr")
        page.wait_for_selector("#overlay:not([hidden])", timeout=10000)
        page.wait_for_timeout(1000)          # returns.js is ~1.4 MB

        corr = page.inner_text("#ov-corr")
        self.assertNotIn("loading", corr.lower(), "correlation panel never resolved")
        note = page.inner_text("#pairs-note")
        self.assertNotIn("Loading", note, "pair matrix never resolved")
        self.assertGreater(page.eval_on_selector_all("#matrix td", "e => e.length"), 0)
        self.assertEqual(page.errors, [])

    def test_pair_matrix_fetches_only_starred_shards(self):
        """The whole point of sharding: starring 2 names should not download
        the other 998+ tracked series, only theirs. This is the regression
        guard for that specific claim -- catches a future change that
        accidentally widens the fetch back out (e.g. reverting to a bulk
        load, or fetching more than what is starred).
        """
        page = self.page()
        requests = []
        page.on("request", lambda req: requests.append(req.url)
                if "/data/returns/" in req.url or req.url.endswith("returns.js") else None)

        # Use high-scoring stocks that are visible with default MIN SCORE = 1
        a, b = "AAPL", "GOOGL"
        page.click('.star[data-star="%s"]' % a)
        page.click('.star[data-star="%s"]' % b)
        page.wait_for_function(
            "!document.getElementById('pairs-note').textContent.includes('Loading')",
            timeout=10000)

        self.assertEqual(len(requests), 2,
                          "starring 2 names should fetch exactly 2 shards, not %r" % requests)
        fetched = set(u.rsplit("/", 1)[-1] for u in requests)
        self.assertEqual(fetched, {a + ".js", b + ".js"})
        self.assertEqual(page.eval_on_selector_all("#matrix td", "e => e.length"), 4)
        self.assertEqual(page.errors, [])

    def test_bulk_load_warms_the_pair_matrix_for_free(self):
        """returns.js and the shards merge onto the same RETURNS object, so
        once a detail panel has bulk-loaded it, starring names afterward
        should need zero further requests -- the two loaders are meant to
        share data, not duplicate it.
        """
        page = self.page()
        page.click("#rows tr:first-child td.ticker")
        page.wait_for_selector("#overlay:not([hidden])")
        page.wait_for_function(
            "!document.getElementById('ov-corr').innerText.toLowerCase().includes('loading')",
            timeout=15000)
        page.click("#ov-close")

        requests = []
        page.on("request", lambda req: requests.append(req.url)
                if "/data/returns/" in req.url or req.url.endswith("returns.js") else None)
        # Use high-scoring stocks that are visible with default MIN SCORE = 1
        page.click('.star[data-star="AAPL"]')
        page.click('.star[data-star="GOOGL"]')
        page.wait_for_timeout(300)

        self.assertEqual(requests, [], "starring after a bulk load should fetch nothing new")
        self.assertEqual(page.eval_on_selector_all("#matrix td", "e => e.length"), 4)
        self.assertEqual(page.errors, [])

    def test_one_missing_shard_does_not_hide_the_other_pairs(self):
        """A 404 on one starred name's shard used to take out the whole
        matrix, not just that name -- withReturnsForAll's completion callback
        was gated on every symbol succeeding, so one failure meant the two
        names that DID load never got shown either. The single bulk file
        never had this failure mode: a name missing from RETURNS just got
        filtered out, and valid pairs still rendered. Force a 404 by deleting
        one starred name's shard, since every name in the committed data
        happens to have one.
        """
        work = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work, True)
        shutil.copy(ROOT / "index.html", work / "index.html")
        shutil.copy(ROOT / "scores.js", work / "scores.js")
        shutil.copytree(ROOT / "data" / "returns", work / "data" / "returns")

        # Use high-scoring stocks visible with default MIN SCORE = 1
        # MSFT has score -0.814 so use TSM (score 1.42) instead
        a, b, victim = "AAPL", "GOOGL", "TSM"
        (work / "data" / "returns" / (victim + ".js")).unlink()

        page = self.page(url="file://%s/index.html" % work)
        page.click('.star[data-star="%s"]' % a)
        page.click('.star[data-star="%s"]' % b)
        page.click('.star[data-star="%s"]' % victim)
        page.wait_for_function(
            "!document.getElementById('pairs-note').textContent.includes('Loading')",
            timeout=10000)

        note = page.inner_text("#pairs-note")
        self.assertNotIn("unavailable", note.lower(),
                          "two valid names should still show pair stats, not an error")
        cells = page.eval_on_selector_all("#matrix td", "e => e.length")
        self.assertEqual(cells, 4, "a and b should form a 2x2 matrix, excluding the victim")
        headers = page.eval_on_selector_all("#matrix th", "e => e.map(x => x.textContent)")
        self.assertNotIn(victim, headers[1:], "the missing-shard name should not appear as a column")
        self.assertEqual(page.errors, [])

    @staticmethod
    def _corr(xs, ys):
        """Pearson correlation, mirroring pairStats()'s formula exactly so
        the expected value here and the client-side one are computed the
        same way rather than one being asserted against a guess."""
        n = len(xs)
        mx = sum(xs) / n
        my = sum(ys) / n
        sxy = sxx = syy = 0.0
        for x, y in zip(xs, ys):
            dx, dy = x - mx, y - my
            sxy += dx * dy
            sxx += dx * dx
            syy += dy * dy
        return sxy / (sxx * syy) ** 0.5

    def _work_with_shards(self):
        work = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work, True)
        shutil.copy(ROOT / "index.html", work / "index.html")
        shutil.copy(ROOT / "scores.js", work / "scores.js")
        shutil.copytree(ROOT / "data" / "returns", work / "data" / "returns")
        return work

    def test_ranked_pairs_lists_unique_pairs_sorted_by_correlation(self):
        """The ranked list is the point of this feature: once a watchlist
        outgrows a handful of names, the NxN matrix stops being scannable,
        so a flat "highest correlation first" list should surface the most
        redundant pair without making the reader hunt across a grid.

        Uses synthetic per-symbol shards with known, non-degenerate
        correlations computed independently in Python (via _corr, the same
        formula pairStats() uses) rather than real market data, whose actual
        correlations are not an invariant of the system and would make this
        assertion drift on every rebuild.
        """
        work = self._work_with_shards()
        # Three real, score >= 1 names already in the committed universe, so
        # they render (and get star buttons) under the default MIN SCORE
        # filter with no other setup.
        a, b, c = "AAPL", "GOOGL", "TSM"
        n = 130  # REPORT.minOverlap is 120; comfortably above it
        series = {
            a: [i for i in range(n)],
            b: [i + (15 if i % 7 == 0 else 0) for i in range(n)],
            c: [(n - 1 - i) + (15 if i % 5 == 0 else 0) for i in range(n)],
        }
        for sym, vals in series.items():
            (work / "data" / "returns" / (sym + ".js")).write_text(
                "RETURNS[%s]=%s;\n" % (json.dumps(sym), json.dumps(vals)))

        expected = sorted(
            ((x, y, self._corr(series[x], series[y])) for x, y in ((a, b), (a, c), (b, c))),
            key=lambda t: t[2], reverse=True)

        page = self.page(url="file://%s/index.html" % work)
        page.click('.star[data-star="%s"]' % a)
        page.click('.star[data-star="%s"]' % b)
        page.click('.star[data-star="%s"]' % c)
        page.wait_for_selector("#ranked-pairs .crow")

        # h3 is styled text-transform: uppercase, so assert against textContent
        # (the DOM text) rather than inner_text (the rendered, transformed text).
        self.assertEqual(
            page.eval_on_selector("#ranked-pairs h3", "e => e.textContent"),
            "Most correlated pairs")
        rows = page.eval_on_selector_all(
            "#ranked-pairs .crow", "els => els.map(e => e.textContent.trim())")
        self.assertEqual(len(rows), 3, "three starred names should give exactly three unique pairs")
        for row, (x, y, corr) in zip(rows, expected):
            label = "%s ↔ %s" % (x, y)
            self.assertTrue(row.startswith(label),
                             "expected '%s' ordered by descending correlation, got %r" % (label, rows))
            self.assertAlmostEqual(float(row[len(label):]), corr, places=2)
        self.assertEqual(page.errors, [])

    def test_ranked_pairs_caps_at_five_when_more_are_available(self):
        """Acceptance criterion: show at least the top 5 pairs when
        available. Four starred names give six unique pairs -- more than
        fit in the cap -- so this proves the list truncates rather than
        dumping every pair once a watchlist gets large enough to actually
        need this feature.
        """
        work = self._work_with_shards()
        symbols = ["AAPL", "GOOGL", "TSM", "LLY"]
        n = 130
        for idx, sym in enumerate(symbols):
            vals = [(i * (idx + 1)) % 97 - 48 for i in range(n)]
            (work / "data" / "returns" / (sym + ".js")).write_text(
                "RETURNS[%s]=%s;\n" % (json.dumps(sym), json.dumps(vals)))

        page = self.page(url="file://%s/index.html" % work)
        for sym in symbols:
            page.click('.star[data-star="%s"]' % sym)
        page.wait_for_selector("#ranked-pairs .crow")

        rows = page.eval_on_selector_all("#ranked-pairs .crow", "els => els.length")
        self.assertEqual(rows, 5, "six unique pairs exist; the list should cap at the top 5")
        self.assertEqual(page.errors, [])

    def test_ranked_pairs_hidden_with_fewer_than_two_watchlist_names(self):
        page = self.page()
        self.assertTrue(page.is_hidden("#pairs"), "no watchlist should show neither list nor matrix")
        self.assertEqual(page.eval_on_selector("#ranked-pairs", "e => e.innerHTML"), "")

        page.click('.star[data-star="AAPL"]')
        page.wait_for_timeout(300)
        self.assertTrue(page.is_hidden("#pairs"),
                         "a single starred name has no pair to rank or show in the matrix")
        self.assertEqual(page.errors, [])

    def test_filters_round_trip_and_clear(self):
        page = self.page()
        total = page.eval_on_selector_all("#rows tr", "e => e.length")

        page.fill("#f-vol", "30")
        page.wait_for_timeout(200)
        filtered = page.eval_on_selector_all("#rows tr", "e => e.length")
        self.assertLess(filtered, total)

        # An unscored name has null metrics, and null compares as 0 in JS, so a
        # ceiling filter used to let all of them through.
        notes = page.eval_on_selector_all("#rows tr td.note", "e => e.length")
        self.assertEqual(notes, 0, "unscored names leaked through a ceiling filter")

        self.assertTrue(page.is_visible("#clear-filters"))
        page.click("#clear-filters")
        page.wait_for_timeout(200)
        self.assertEqual(page.eval_on_selector_all("#rows tr", "e => e.length"), total)
        self.assertEqual(page.input_value("#f-vol"), "")
        self.assertEqual(page.errors, [])

    def test_sector_filter_narrows_and_clears(self):
        """No committed scores.js has real sector data yet (it needs a
        --refresh-universe rebuild), so synthesize it here rather than wait
        for one.
        """
        work = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work, True)
        for name in ("index.html", "returns.js"):
            shutil.copy(ROOT / name, work / name)

        rep = report()
        sectors = ["Technology", "Healthcare"]
        for i, row in enumerate(rep["universe"]):
            row["sector"] = sectors[i % 2]
        (work / "scores.js").write_text(
            "// Generated by build.py -- do not edit.\nconst REPORT = %s;\n"
            % json.dumps(rep, indent=1))

        page = self.page(url="file://%s/index.html" % work)
        total = page.eval_on_selector_all("#rows tr", "e => e.length")

        options = page.eval_on_selector_all("#f-sector option", "e => e.map(x => x.value)")
        self.assertEqual(sorted(o for o in options if o), sorted(set(sectors)))

        page.select_option("#f-sector", "Technology")
        page.wait_for_timeout(200)
        filtered = page.eval_on_selector_all("#rows tr", "e => e.length")
        self.assertLess(filtered, total)
        self.assertGreater(filtered, 0)

        self.assertTrue(page.is_visible("#clear-filters"))
        page.click("#clear-filters")
        page.wait_for_timeout(200)
        self.assertEqual(page.eval_on_selector_all("#rows tr", "e => e.length"), total)
        self.assertEqual(page.input_value("#f-sector"), "")
        self.assertEqual(page.errors, [])

    def test_stale_saved_sector_falls_back_to_any(self):
        """A sector saved from a previous session can vanish on the next
        weekly universe refresh (a renamed or dropped sector). The <select>
        silently ignores a value with no matching <option> and shows "any" --
        view.sector must follow it back to '', or the display says "any"
        while every row is still being filtered against a sector nothing
        in the current universe has, hiding the whole table with no
        visible cause.
        """
        saved = json.dumps({
            "key": "rank", "sector": "Sector That No Longer Exists", "minScore": ""})
        ctx = self.browser.new_context(viewport={"width": 1280, "height": 900})
        self.addCleanup(ctx.close)
        ctx.add_init_script("localStorage.setItem('zoomies.view', %s)" % json.dumps(saved))
        page = ctx.new_page()
        page.errors = []
        page.on("pageerror", lambda e: page.errors.append(str(e)))
        page.goto(SITE)
        page.wait_for_selector("#rows tr")

        self.assertEqual(page.input_value("#f-sector"), "")
        # With minScore: '', no score filter is applied, so all 1000 stocks are shown
        self.assertEqual(page.eval_on_selector_all("#rows tr", "e => e.length"),
                          len(self.report["universe"]))
        self.assertEqual(page.errors, [])

    def test_saved_view_survives_an_obsolete_sort_key(self):
        """The exact regression this PR fixed: the restore logic used to be
        gated entirely on the saved sort key having a FIRST_DIR entry, so a
        saved key from a since-removed column (rankChange63d, retired by
        this PR) discarded not just the sort but theme, watchlist and
        filters too -- everything, on a single unrelated field going stale.
        Likely to recur whenever another sortable field is retired, so this
        seeds a realistic full saved state and checks each piece survives
        independently of the sort falling back.

        Seeded via context.add_init_script(), not page.evaluate() + reload():
        the latter sets localStorage on an *already-loaded* page, and reload()
        races that page's own pagehide/visibilitychange flush -- which fires
        during navigation and silently overwrites the seed with whatever
        (default) state was already in memory before it ever gets read back.
        add_init_script runs before the page's own scripts on every
        navigation, so there is nothing left to race.
        """
        symbol = self.report["universe"][0]["symbol"]
        saved = json.dumps({
            "key": "rankChange63d", "dir": -1, "theme": "dark",
            # A deliberately generous ceiling: this only needs to prove the
            # filter value itself survives, not stay realistic -- an actual
            # 30% cap could filter the watched symbol's row out of the table
            # entirely depending on its real volatility, hiding its star
            # button and breaking the watchlist assertion below for a
            # reason that has nothing to do with what this test checks.
            "watch": [symbol], "maxVol": "500", "minScore": "",
        })
        ctx = self.browser.new_context(viewport={"width": 1280, "height": 900})
        self.addCleanup(ctx.close)
        ctx.add_init_script("localStorage.setItem('zoomies.view', %s)" % json.dumps(saved))
        page = ctx.new_page()
        page.errors = []
        page.on("pageerror", lambda e: page.errors.append(str(e)))
        page.goto(SITE)
        page.wait_for_selector("#rows tr")

        self.assertEqual(page.get_attribute("#table", "data-sort"), "rank",
                          "an unrecognized saved sort key should fall back to rank")
        # #theme is text-transform: uppercase in CSS -- inner_text renders that.
        self.assertEqual(page.inner_text("#theme"), "DARK")
        self.assertEqual(page.input_value("#f-vol"), "500")
        self.assertEqual(
            page.get_attribute('.star[data-star="%s"]' % symbol, "aria-pressed"), "true",
            "the watchlist entry should survive an obsolete sort key too")
        self.assertEqual(page.errors, [])

    def _page_with_generated(self, generated):
        """A page whose REPORT.generated is a controlled date rather than
        whatever the committed scores.js happens to carry -- the staleness
        warning compares that date against the real wall clock, so a test
        that depends on the committed value drifts out from under itself
        and starts failing on an unrelated day, on an otherwise-correct
        branch, once the commit is old enough.
        """
        work = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work, True)
        for name in ("index.html", "returns.js"):
            shutil.copy(ROOT / name, work / name)

        rep = report()
        rep["generated"] = generated
        (work / "scores.js").write_text(
            "// Generated by build.py -- do not edit.\nconst REPORT = %s;\n"
            % json.dumps(rep, indent=1))
        return self.page(url="file://%s/index.html" % work)

    def test_fresh_data_shows_no_stale_warning(self):
        today = datetime.date.today().isoformat()
        page = self._page_with_generated(today)
        self.assertTrue(page.is_hidden("#stale"))
        self.assertEqual(page.errors, [])

    def test_old_data_shows_a_stale_warning(self):
        """REPORT.generated is stamped on every successful nightly rebuild,
        even one that finds no new prices -- so its age is a reliable signal
        that the automation stopped running, not just a timestamp nobody
        looks at. Spencer is weighting real positions off this page, so a
        silently stale ranking is worse than a loudly stale one.
        """
        old = (datetime.date.today() - datetime.timedelta(days=10)).isoformat()
        page = self._page_with_generated(old)
        self.assertFalse(page.is_hidden("#stale"))
        text = page.inner_text("#stale")
        self.assertIn("10 days old", text)
        self.assertIn(old, text)
        self.assertEqual(page.errors, [])

    def _page_with_rank_change_fixture(self):
        """A tiny, fully deterministic 6-name universe for the percentile and
        63D rank-change maths. Real committed data's actual rankings are not
        an invariant of the system -- they change on every rebuild -- so
        asserting exact values against it would tie test correctness to
        today's live data rather than the code, the same lesson the
        staleness tests hit earlier.

        Global current rank (by score, descending): Z=1 A=2 B=3 C=4 D=5 E=6.
        historicalRank63d: A=1 (unchanged) B=5 (was worse, improved: +3)
        C=3 (unchanged) D=2 (was better, declined: -2) Z=None, E=None (not
        enough history 63 sessions back for either).

        Z is deliberately the *highest*-scoring name and has no historical
        data, same as E at the bottom -- a name freshly qualified for a
        score has no history regardless of how well it currently scores.
        This is the regression case for a real bug: 63D rank change must be
        computed over the cohort that has a valid historicalRank63d, not
        every currently-scored name. Before that fix, Z's mere presence
        (occupying rank #1) silently shifted A/B/C/D's *apparent* rank
        change by one, purely because Z existed, not because any of their
        own momentum changed. If that regression ever comes back, A/B/C/D's
        expected values below (0, +3, 0, -2) will drift by exactly one.

        Score/return/vol/drawdown are evenly spaced across all six names so
        each metric's percentile ladder is exactly 0/20/40/60/80/100.
        """
        work = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work, True)
        for name in ("index.html", "returns.js"):
            shutil.copy(ROOT / name, work / name)

        rep = report()
        rep["rankChangeDaysBack"] = 63
        template = rep["universe"][0]
        # Shift all scores up by 4 so minimum is 1.0 (visible with default MIN SCORE = 1)
        fixture = [
            ("Z", 14.0, 0.70, 0.05, -0.02, None),
            ("A", 9.0, 0.50, 0.10, -0.05, 1),
            ("B", 7.0, 0.30, 0.20, -0.10, 5),
            ("C", 5.0, 0.10, 0.30, -0.15, 3),
            ("D", 3.0, -0.10, 0.40, -0.20, 2),
            ("E", 1.0, -0.30, 0.50, -0.25, None),
        ]
        rows = []
        for symbol, score, ann_return, ann_vol, max_dd, hist_rank in fixture:
            row = dict(template)
            row.update({
                "symbol": symbol, "name": symbol + " Corp",
                "score": score, "annReturn": ann_return, "annVol": ann_vol,
                "maxDrawdown": max_dd, "historicalRank63d": hist_rank,
                "lastClose": None, "lastDate": None,
            })
            rows.append(row)
        rep["universe"] = rows
        (work / "scores.js").write_text(
            "// Generated by build.py -- do not edit.\nconst REPORT = %s;\n"
            % json.dumps(rep, indent=1))
        return self.page(url="file://%s/index.html" % work)

    @staticmethod
    def _stats_map(page):
        """{dt label -> dd text} for the open detail panel, pairing each dt
        with the DOM element right after it rather than trusting .innerText's
        line-break guesses across the stats grid's two columns.
        """
        return page.eval_on_selector_all(
            "#ov-stats > *",
            "els => { var out = {}; "
            "for (var i = 0; i < els.length; i++) { "
            "  if (els[i].tagName === 'DT') out[els[i].textContent.trim()] = els[i+1].textContent.trim(); "
            "} return out; }")

    def _open_by_symbol(self, page, symbol):
        """Opens a fixture row by its exact data-symbol attribute, not the
        search box: every synthetic name in this fixture ends in "Corp",
        which contains the letter "c" -- searching "C" (row C's own ticker)
        matches every row's name too, silently opening whichever one sorts
        first instead of row C. data-symbol has no such collision.
        """
        page.click('tr[data-symbol="%s"] td.ticker' % symbol)
        page.wait_for_selector("#overlay:not([hidden])")
        return self._stats_map(page)

    def test_detail_panel_collapses_rank_and_63d_change_into_one_line(self):
        """Also the regression guard for the cohort bug (PR #16/#17's
        review): Z sits at rank #1 overall with no historical data, yet
        A/B/C/D's rank changes below (0, +3, 0, -2) are exactly what they'd
        be without Z in the universe at all -- if the cohort restriction
        ever regresses, Z's presence will shift every one of those by one.
        """
        page = self._page_with_rank_change_fixture()

        def rank_cell(symbol):
            page.click('tr[data-symbol="%s"] td.ticker' % symbol)
            page.wait_for_selector("#overlay:not([hidden])")
            cell = page.eval_on_selector_all(
                "#ov-stats > *",
                "els => { for (var i = 0; i < els.length; i++) { "
                "  if (els[i].tagName === 'DT' && els[i].textContent.trim() === 'Rank') { "
                "    var dd = els[i+1], span = dd.querySelector('span'); "
                "    return {text: dd.textContent.trim(), "
                "            cls: span ? span.className : null, "
                "            style: span ? span.getAttribute('style') : null}; "
                "  } } return null; }")
            page.click("#ov-close")
            return cell

        self.assertEqual(rank_cell("A"),
                          {"text": "#2 (0 in 3m)", "cls": "", "style": "color:var(--muted)"},
                          "zero movement should be muted, not colored")
        self.assertEqual(rank_cell("B"),
                          {"text": "#3 (+3 in 3m)", "cls": "pos", "style": None},
                          "positive movement should be green")
        self.assertEqual(rank_cell("C"), {"text": "#4 (0 in 3m)", "cls": "", "style": "color:var(--muted)"})
        self.assertEqual(rank_cell("D"),
                          {"text": "#5 (-2 in 3m)", "cls": "neg", "style": None},
                          "negative movement should be red")

        # Z and E both have no historicalRank63d (Z: high current rank but
        # no history; E: low rank, no history) -- the parenthetical must be
        # omitted entirely, not replaced with a placeholder message.
        self.assertEqual(rank_cell("Z"), {"text": "#1", "cls": None, "style": None})
        self.assertEqual(rank_cell("E"), {"text": "#6", "cls": None, "style": None})
        self.assertEqual(page.errors, [])

    def test_63d_column_and_sort_button_are_gone(self):
        """The main table and its always-visible sort control were removed
        in favor of the collapsed detail-panel line above -- regression
        guard against either coming back as UI chrome.
        """
        page = self.page()
        self.assertEqual(page.eval_on_selector_all('th[data-key="rankChange63d"]', "e => e.length"), 0)
        self.assertEqual(page.eval_on_selector_all("#sort-63d", "e => e.length"), 0)
        self.assertEqual(page.eval_on_selector_all("td.r63", "e => e.length"), 0)
        self.assertEqual(page.errors, [])

    def test_detail_panel_percentiles_unaffected_by_the_63d_simplification(self):
        page = self._page_with_rank_change_fixture()
        stats = self._open_by_symbol(page, "B")
        self.assertEqual(stats["Score percentile"], "60th (higher = stronger)")
        self.assertEqual(stats["Return percentile"], "60th (higher = stronger)")
        self.assertEqual(stats["Volatility percentile"], "40th (higher = more volatile)")
        self.assertEqual(stats["Drawdown percentile"], "60th (higher = shallower)")
        self.assertEqual(page.errors, [])

    def test_search_survives_a_reload(self):
        page = self.page()
        # Use AAPL, a high-scoring stock visible with default MIN SCORE = 1
        symbol = "AAPL"
        page.fill("#search", symbol)
        page.wait_for_timeout(200)
        page.reload()
        page.wait_for_selector("#rows tr")
        self.assertEqual(page.input_value("#search"), symbol)

    def test_row_with_no_cached_price_still_opens(self):
        """build.py leaves lastClose null when a name was never fetched.

        That is the documented quota-wall outcome, and reading .toFixed off it
        threw before the overlay was shown -- so the row silently did nothing
        when tapped. No committed scores.js contains that state, so synthesise it.
        """
        work = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work, True)
        for name in ("index.html", "returns.js"):
            shutil.copy(ROOT / name, work / name)

        rep = report()
        # Use AAPL, a high-scoring stock visible with default MIN SCORE = 1
        victim = "AAPL"
        for row in rep["universe"]:
            if row["symbol"] == victim:
                row["lastClose"] = None
                row["lastDate"] = None
        (work / "scores.js").write_text(
            "// Generated by build.py -- do not edit.\nconst REPORT = %s;\n"
            % json.dumps(rep, indent=1))

        page = self.page(url="file://%s/index.html" % work)
        page.fill("#search", victim)
        page.wait_for_timeout(200)
        page.click("#rows tr:first-child td.ticker")
        page.wait_for_selector("#overlay:not([hidden])", timeout=5000)

        stats = page.inner_text("#ov-stats")
        self.assertIn("Market cap", stats)
        self.assertNotIn("Last close", stats)
        self.assertNotIn("null", stats)
        self.assertEqual(page.errors, [])

    def test_phone_layout_does_not_overflow(self):
        page = self.page(width=375, height=780)
        visible_headers = page.eval_on_selector_all(
            "thead th",
            "e => e.filter(x => getComputedStyle(x).display !== 'none').length")
        visible_cells = page.eval_on_selector_all(
            "#rows tr:first-child td",
            "e => e.filter(x => getComputedStyle(x).display !== 'none')"
            "     .reduce((n, c) => n + (c.colSpan || 1), 0)")
        self.assertEqual(visible_headers, visible_cells,
                         "header and body rows disagree once a column is hidden")
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 375)
        self.assertEqual(page.errors, [])

    def test_row_tap_target_stays_accessible_at_phone_width(self):
        """Guards the density pass's own stated constraint: row padding was
        trimmed for scanability, but never below a ~44px tap target -- the
        row itself is what opens the detail panel, so this is the one
        measurement that actually matters for that tradeoff, not a hunch.
        """
        for width in (390, 375, 320):
            page = self.page(width=width, height=780)
            h = page.eval_on_selector("#rows tr:first-child", "e => e.getBoundingClientRect().height")
            self.assertGreaterEqual(h, 44, "row tap target dropped below 44px at %dpx wide" % width)
            self.assertEqual(page.errors, [])

    def test_fresh_visit_defaults_min_score_to_one(self):
        """A fresh visit without saved preferences should default the MIN SCORE
        filter to "1" to reduce the number of rows shown on first load.
        """
        page = self.page()
        self.assertEqual(page.input_value("#f-score"), "1")
        self.assertEqual(page.errors, [])

    def test_saved_min_score_preference_takes_precedence(self):
        """A saved MIN SCORE preference should override the default when
        the page reloads. Include other fields in saved state to mimic
        a realistic saved view object.
        """
        ctx = self.browser.new_context(viewport={"width": 1280, "height": 900})
        self.addCleanup(ctx.close)
        saved = json.dumps({
            "key": "rank", "dir": 1, "minScore": "2.5",
            "maxVol": "", "maxDD": "", "sector": ""
        })
        ctx.add_init_script("localStorage.setItem('zoomies.view', %s)" % json.dumps(saved))
        page = ctx.new_page()
        page.errors = []
        page.on("pageerror", lambda e: page.errors.append(str(e)))
        page.goto(SITE)
        page.wait_for_selector("#rows tr")

        # The saved preference should take precedence over the default
        self.assertEqual(page.input_value("#f-score"), "2.5")
        self.assertEqual(page.errors, [])

    def test_clear_filters_resets_min_score_to_one(self):
        """Clearing filters should reset MIN SCORE to the default of "1",
        not to empty.
        """
        page = self.page()
        # Set MIN SCORE to a different value
        page.fill("#f-score", "3")
        page.wait_for_timeout(200)
        self.assertEqual(page.input_value("#f-score"), "3")

        # Clear filters
        page.click("#clear-filters")
        page.wait_for_timeout(200)

        # MIN SCORE should be reset to "1", not empty
        self.assertEqual(page.input_value("#f-score"), "1")
        self.assertEqual(page.errors, [])


if __name__ == "__main__":
    unittest.main()
