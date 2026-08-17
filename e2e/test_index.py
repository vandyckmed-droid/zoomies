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
        # Ranked pairs live on the Watchlist destination now; switch there so
        # the active tab (persisted, like theme) survives the reload below.
        page.click("#nav-watchlist")
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
        self.assertNotIn("Loading", note, "ranked pairs list never resolved")
        self.assertGreater(page.eval_on_selector_all("#ranked-pairs .crow", "e => e.length"), 0)
        self.assertEqual(page.errors, [])

    def test_ranked_pairs_fetches_only_starred_shards(self):
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
        self.assertEqual(page.eval_on_selector_all("#ranked-pairs .crow", "e => e.length"), 1)
        self.assertEqual(page.errors, [])

    def test_bulk_load_warms_the_ranked_pairs_for_free(self):
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
        self.assertEqual(page.eval_on_selector_all("#ranked-pairs .crow", "e => e.length"), 1)
        self.assertEqual(page.errors, [])

    def test_one_missing_shard_does_not_hide_the_other_pairs(self):
        """A 404 on one starred name's shard used to take out the whole
        ranked pairs list, not just that name -- withReturnsForAll's
        completion callback was gated on every symbol succeeding, so one
        failure meant the two names that DID load never got shown either.
        The single bulk file never had this failure mode: a name missing
        from RETURNS just got filtered out, and valid pairs still rendered.
        Force a 404 by deleting one starred name's shard, since every name
        in the committed data happens to have one.
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

        page.click("#nav-watchlist")
        note = page.inner_text("#pairs-note")
        self.assertNotIn("unavailable", note.lower(),
                          "two valid names should still show pair stats, not an error")
        labels = page.eval_on_selector_all(
            "#ranked-pairs .crow > span:first-child", "els => els.map(e => e.textContent)")
        self.assertEqual(len(labels), 1, "a and b should form exactly one pair, excluding the victim")
        self.assertNotIn(victim, labels[0], "the missing-shard name should not appear in the ranked list")
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
        """The ranked list is the whole watchlist correlation experience:
        once a watchlist outgrows a handful of names, an NxN grid stops
        being scannable, so a flat "highest correlation first" list should
        surface the most redundant pair without making the reader hunt
        across a grid.

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
        page.click("#nav-watchlist")
        page.wait_for_selector("#ranked-pairs .crow")

        # h3 is styled text-transform: uppercase, so assert against textContent
        # (the DOM text) rather than inner_text (the rendered, transformed text).
        self.assertEqual(
            page.eval_on_selector("#ranked-pairs h3", "e => e.textContent"),
            "Most correlated pairs")
        labels = page.eval_on_selector_all(
            "#ranked-pairs .crow > span:first-child", "els => els.map(e => e.textContent.trim())")
        values = page.eval_on_selector_all(
            "#ranked-pairs .cval", "els => els.map(e => e.textContent.trim())")
        self.assertEqual(len(labels), 3, "three starred names should give exactly three unique pairs")
        for label, value, (x, y, corr) in zip(labels, values, expected):
            self.assertEqual(label, "%s ↔ %s" % (x, y),
                              "expected pairs ordered by descending correlation, got %r" % labels)
            self.assertAlmostEqual(float(value), corr, places=2)
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
        page.click("#nav-watchlist")
        page.wait_for_selector("#ranked-pairs .crow")

        rows = page.eval_on_selector_all("#ranked-pairs .crow", "els => els.length")
        self.assertEqual(rows, 5, "six unique pairs exist; the list should cap at the top 5")
        self.assertEqual(page.errors, [])

    def test_ranked_pairs_hidden_with_fewer_than_two_watchlist_names(self):
        page = self.page()
        page.click("#nav-watchlist")
        self.assertTrue(page.is_hidden("#pairs"), "no watchlist should show the ranked pairs section")
        self.assertEqual(page.eval_on_selector("#ranked-pairs", "e => e.innerHTML"), "")

        page.click("#nav-ranks")
        page.click('.star[data-star="AAPL"]')
        page.wait_for_timeout(300)
        page.click("#nav-watchlist")
        self.assertTrue(page.is_hidden("#pairs"),
                         "a single starred name has no pair to rank")
        self.assertEqual(page.errors, [])

    def test_ranked_pairs_never_shown_on_ranks_destination(self):
        """The section moved into Watchlist entirely -- two or more starred
        names must not resurrect it on the Ranks screen.
        """
        page = self.page()
        page.click('.star[data-star="AAPL"]')
        page.click('.star[data-star="GOOGL"]')
        page.wait_for_timeout(300)
        self.assertTrue(page.is_hidden("#pairs"),
                         "correlation pairs must appear only in Watchlist, never on Ranks")
        self.assertEqual(page.errors, [])

    def _page_with_pair_fixture(self, rows, series, clear_score_filter=False):
        """A synthetic universe plus per-symbol shards, for exercising
        worseOfPair()'s tie-break ladder deterministically. Real committed
        ranks are unique per scored name (assigned by sorted score
        position), so a genuine rank tie never happens between two scored
        names in live data -- this is the only way to reach the null-rank
        and full-tie paths without waiting on a coincidence.
        """
        work = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work, True)
        shutil.copy(ROOT / "index.html", work / "index.html")
        (work / "data" / "returns").mkdir(parents=True)

        rep = report()
        template = rep["universe"][0]
        # A scored row outside `rows`, never starred or otherwise touched --
        # just padding so the table isn't empty under the default MIN SCORE
        # = 1 filter when every fixture row here is unscored. self.page()
        # waits for a visible "#rows tr" before returning, and an all-null
        # universe would leave it waiting forever.
        rep["universe"] = [dict(template, symbol="ZZPAD", name="ZZPAD Corp", score=10.0,
                                 lastClose=None, lastDate=None)]
        for symbol, score in rows:
            row = dict(template)
            row.update({"symbol": symbol, "name": symbol + " Corp", "score": score,
                        "lastClose": None, "lastDate": None})
            rep["universe"].append(row)
        (work / "scores.js").write_text(
            "// Generated by build.py -- do not edit.\nconst REPORT = %s;\n"
            % json.dumps(rep, indent=1))

        for sym, vals in series.items():
            (work / "data" / "returns" / (sym + ".js")).write_text(
                "RETURNS[%s]=%s;\n" % (json.dumps(sym), json.dumps(vals)))

        page = self.page(url="file://%s/index.html" % work)
        if clear_score_filter:
            # An unscored fixture row is filtered out by the default MIN
            # SCORE = 1 and never gets a star button to click.
            page.fill("#f-score", "")
            page.wait_for_timeout(200)
        for sym in series:
            page.click('.star[data-star="%s"]' % sym)
        page.click("#nav-watchlist")
        page.wait_for_selector("#ranked-pairs .crow")
        return page

    def test_ranked_pairs_remove_targets_the_lower_ranked_name(self):
        """The remove action must target the *weaker* holding -- the one
        with the worse (higher) rank number -- not just whichever symbol
        happens to come first, and removing it must immediately recompute
        every piece of state that depends on the watchlist: the ranked
        list, the star button, and the watch count.
        """
        n = 130
        base = list(range(n))
        page = self._page_with_pair_fixture(
            rows=[("HI", 5.0), ("LO", 3.0)],
            series={"HI": base,
                    "LO": [v + (5 if i % 11 == 0 else 0) for i, v in enumerate(base)]})

        self.assertEqual(page.get_attribute("#ranked-pairs .prow-remove", "data-remove"), "LO",
                          "HI outranks LO, so LO is the weaker holding and should be offered for removal")
        self.assertEqual(page.inner_text("#ranked-pairs .prow-remove"), "− LO")
        self.assertEqual(page.eval_on_selector_all("#rows tr", "e => e.length"), 2)

        page.click("#ranked-pairs .prow-remove")
        page.wait_for_timeout(200)

        self.assertTrue(page.is_hidden("#pairs"),
                         "removing one of only two watched names leaves no pair to show")
        # The Watchlist table itself is governed by membership, so removing
        # LO should drop it from the visible list, not just the star state --
        # its star button no longer exists here at all. Check the star state
        # back on Ranks, where every name (watched or not) still has a row.
        self.assertEqual(page.eval_on_selector_all("#rows tr", "e => e.length"), 1)
        page.click("#nav-ranks")
        self.assertEqual(page.get_attribute('.star[data-star="LO"]', "aria-pressed"), "false")
        self.assertEqual(page.get_attribute('.star[data-star="HI"]', "aria-pressed"), "true",
                          "removal must only affect the targeted ticker")
        self.assertEqual(page.errors, [])

    def test_ranked_pairs_remove_treats_an_unscored_name_as_the_weaker_holding(self):
        """A name with no score at all (rank null) has no momentum case for
        keeping it, so it must lose to any real ranked name regardless of
        how strong the scored name's own number is.
        """
        n = 130
        base = list(range(n))
        page = self._page_with_pair_fixture(
            rows=[("HI", 5.0), ("NS", None)],
            series={"HI": base,
                    "NS": [v + (5 if i % 11 == 0 else 0) for i, v in enumerate(base)]},
            clear_score_filter=True)

        self.assertEqual(page.get_attribute("#ranked-pairs .prow-remove", "data-remove"), "NS",
                          "an unscored name has no rank at all and should lose to any real rank")
        page.click("#ranked-pairs .prow-remove")
        page.wait_for_timeout(200)
        self.assertTrue(page.is_hidden("#pairs"))
        # NS's row no longer exists in the (membership-governed) Watchlist
        # table at all -- check the star state back on Ranks instead, where
        # NS still has a row (the score filter was cleared for this fixture).
        page.click("#nav-ranks")
        self.assertEqual(page.get_attribute('.star[data-star="NS"]', "aria-pressed"), "false")
        self.assertEqual(page.errors, [])

    def test_ranked_pairs_remove_falls_back_to_ticker_order_on_a_full_tie(self):
        """Two unscored names tie at every real level -- both rank null,
        both score null -- so the only way the choice stays deterministic
        (not flip-flopping between renders) is a fixed ticker-order rule.
        """
        n = 130
        base = list(range(n))
        page = self._page_with_pair_fixture(
            rows=[("AAAA", None), ("AAAB", None)],
            series={"AAAA": base,
                    "AAAB": [v + (5 if i % 11 == 0 else 0) for i, v in enumerate(base)]},
            clear_score_filter=True)

        self.assertEqual(page.get_attribute("#ranked-pairs .prow-remove", "data-remove"), "AAAB",
                          "a full tie should fall back to deterministic ticker order")
        self.assertEqual(page.errors, [])

    def test_ranked_pairs_remove_button_reads_as_a_button_without_a_stuck_hover(self):
        """The remove action must look tappable (a bordered control, not
        plain colored text) and must not lean on a :hover underline -- on
        touch, a tapped :hover state has no "pointer left" event to clear
        it, so it would otherwise stay visually stuck until some unrelated
        later tap.
        """
        page = self.page()
        for sym in ["AAPL", "GOOGL", "TSM"]:
            page.click('.star[data-star="%s"]' % sym)
        page.click("#nav-watchlist")
        page.wait_for_selector("#ranked-pairs .crow")

        style = page.eval_on_selector(
            "#ranked-pairs .prow-remove",
            "e => { var s = getComputedStyle(e); "
            "return {border: s.borderStyle, width: s.borderWidth, decoration: s.textDecorationLine}; }")
        self.assertEqual(style["border"], "solid",
                          "the remove action should read as a bordered button, not plain text")
        self.assertNotEqual(style["width"], "0px")
        self.assertEqual(style["decoration"], "none")

        page.hover("#ranked-pairs .prow-remove")
        hovered = page.eval_on_selector(
            "#ranked-pairs .prow-remove", "e => getComputedStyle(e).textDecorationLine")
        self.assertEqual(hovered, "none",
                          "hover must not introduce an underline that can stay visually stuck on touch")
        self.assertEqual(page.errors, [])

    def test_ranked_pairs_remove_collapses_smoothly_not_instantly(self):
        """What must never happen is an instant snap: the very first frame
        after the tap should not already show the section at its final,
        post-removal height -- the collapse must unfold smoothly across the
        transition, not jump there in one frame.

        Measures #pairs's own height, the property actually under CSS
        transition control, sampled as soon as possible after the click
        rather than after an arbitrary fixed delay -- a fixed-delay sample
        (e.g. wait 30ms, then check a value) is not robust to CI scheduler
        jitter: on a briefly stalled runner, a delayed sample can land after
        the .18s transition has already caught up, making it equal the
        settled value for a reason that has nothing to do with whether an
        instant snap actually happened. The invariant that actually matters
        -- still taller than the final, settled height on this first read --
        holds regardless of exactly how much (short of the full .18s) real
        time the round trip to sample it took. This is also why the
        assertion checks height directly rather than #pairs's
        viewport-relative position: position only moves as an indirect,
        second-order consequence of the browser's own scroll-clamping once
        the document shrinks, adding its own timing uncertainty on top.
        """
        work = self._work_with_shards()
        a, b, c = "AAPL", "GOOGL", "TSM"
        n = 130
        series = {
            a: [i for i in range(n)],
            b: [i + (15 if i % 7 == 0 else 0) for i in range(n)],
            c: [(n - 1 - i) + (15 if i % 5 == 0 else 0) for i in range(n)],
        }
        for sym, vals in series.items():
            (work / "data" / "returns" / (sym + ".js")).write_text(
                "RETURNS[%s]=%s;\n" % (json.dumps(sym), json.dumps(vals)))

        page = self.page(width=390, height=650, url="file://%s/index.html" % work)
        page.click('.star[data-star="%s"]' % a)
        page.click('.star[data-star="%s"]' % b)
        page.click('.star[data-star="%s"]' % c)
        page.click("#nav-watchlist")
        page.wait_for_selector("#ranked-pairs .crow")

        start_height = page.eval_on_selector("#pairs", "e => e.getBoundingClientRect().height")

        page.click("#ranked-pairs .prow-remove")
        immediate_height = page.eval_on_selector("#pairs", "e => e.getBoundingClientRect().height")
        page.wait_for_timeout(500)  # comfortably past the .18s collapse transition
        settled_height = page.eval_on_selector("#pairs", "e => e.getBoundingClientRect().height")

        self.assertGreater(
            immediate_height, settled_height,
            "the very first read after the tap should still be taller than "
            "the final, settled height -- not already collapsed there in "
            "one frame")
        self.assertLess(
            settled_height, start_height,
            "the section should end up shorter once the row is gone")
        # The next highest-correlated pair should have naturally taken the
        # freed slot rather than the list going empty.
        self.assertGreater(page.eval_on_selector_all("#ranked-pairs .crow", "e => e.length"), 0)
        self.assertEqual(page.errors, [])

    def _page_with_many_scored_rows(self, n=60):
        """A deterministic, large-enough universe to make both the Ranks
        table and a fully-starred Watchlist scrollable -- real committed
        data's actual score distribution is not an invariant of the system,
        so a scroll-position test needs a fixture, not a hope that enough
        real names happen to score >= 1 today.
        """
        work = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work, True)
        for name in ("index.html", "returns.js"):
            shutil.copy(ROOT / name, work / name)
        rep = report()
        template = rep["universe"][0]
        rows = []
        for i in range(n):
            row = dict(template)
            row.update({"symbol": "SYM%03d" % i, "name": "Symbol %d Corp" % i,
                        "score": 5.0 - i * 0.01, "lastClose": None, "lastDate": None})
            rows.append(row)
        rep["universe"] = rows
        (work / "scores.js").write_text(
            "// Generated by build.py -- do not edit.\nconst REPORT = %s;\n"
            % json.dumps(rep, indent=1))
        return work

    # --- bottom navigation / Watchlist destination --------------------------

    def test_bottom_nav_renders_exactly_two_destinations(self):
        page = self.page()
        labels = page.eval_on_selector_all(
            "#bottom-nav .nav-btn span", "els => els.map(e => e.textContent)")
        self.assertEqual(labels, ["Ranks", "Watchlist"])
        icons = page.eval_on_selector_all("#bottom-nav .nav-btn svg", "e => e.length")
        self.assertEqual(icons, 2, "each destination should use an inline SVG icon")
        # No emoji/unicode glyph icons riding along in the button text --
        # each button's full text should be exactly its label.
        texts = page.eval_on_selector_all(
            "#bottom-nav .nav-btn", "els => els.map(e => e.textContent.trim())")
        self.assertEqual(texts, ["Ranks", "Watchlist"])
        self.assertEqual(page.errors, [])

    def test_switching_to_watchlist_updates_active_state_and_hides_ranks_filters(self):
        page = self.page()
        self.assertEqual(page.get_attribute("#nav-ranks", "aria-current"), "page")
        self.assertEqual(page.get_attribute("#nav-watchlist", "aria-current"), "false")
        self.assertTrue(page.is_visible(".bar"), "the Ranks filter bar should show on Ranks")

        page.click("#nav-watchlist")
        self.assertEqual(page.get_attribute("#nav-watchlist", "aria-current"), "page")
        self.assertEqual(page.get_attribute("#nav-ranks", "aria-current"), "false")
        self.assertTrue(page.is_hidden(".bar"),
                         "search/MIN SCORE/MAX VOL/sector belong to Ranks, not Watchlist")
        self.assertEqual(page.errors, [])

    def test_watchlist_shows_watched_stocks_regardless_of_ranks_filters(self):
        """Membership governs Watchlist; a Ranks-screen filter that would
        hide a name on Ranks must not hide it on Watchlist.
        """
        page = self.page()
        symbol = "AAPL"
        page.click('.star[data-star="%s"]' % symbol)
        # High enough to exclude every real tracked name from Ranks, the
        # just-starred one included.
        page.fill("#f-score", "999")
        page.wait_for_timeout(200)
        self.assertEqual(page.eval_on_selector_all("#rows tr", "e => e.length"), 0,
                          "sanity check: the filter should hide every Ranks row")

        page.click("#nav-watchlist")
        self.assertEqual(page.eval_on_selector_all("#rows tr", "e => e.length"), 1,
                          "the starred name should still show on Watchlist")
        self.assertEqual(page.eval_on_selector("#rows tr td.ticker", "e => e.textContent"), symbol)
        self.assertEqual(page.errors, [])

    def test_ticker_detail_opens_from_watchlist(self):
        page = self.page()
        page.click('.star[data-star="AAPL"]')
        page.click("#nav-watchlist")
        page.click("#rows tr:first-child td.ticker")
        page.wait_for_selector("#overlay:not([hidden])")
        self.assertEqual(page.inner_text("#ov-title"), "AAPL")
        self.assertEqual(page.errors, [])

    def test_switching_tabs_closes_open_ticker_detail(self):
        """The open detail overlay is a full-screen scrim above the bottom
        nav (by design -- a modal blocking the nav underneath it is
        standard, expected behaviour, the same as any native app), so a
        real pointer tap can't reach the nav bar while it's up. What this
        guards is the underlying state: whatever eventually switches the
        active tab -- the close button then a tap, or activating a nav
        button directly by its own click() the way a keyboard/assistive
        activation would -- must never leave the overlay dangling open on
        the new destination. Invoking .click() on the element exercises
        exactly that path without depending on pointer hit-testing.
        """
        page = self.page()
        page.click("#rows tr:first-child td.ticker")
        page.wait_for_selector("#overlay:not([hidden])")
        page.eval_on_selector("#nav-watchlist", "e => e.click()")
        self.assertTrue(page.is_hidden("#overlay"),
                         "switching destinations should close any open detail overlay")
        self.assertEqual(page.get_attribute("#nav-watchlist", "aria-current"), "page")
        self.assertEqual(page.errors, [])

    def test_star_state_stays_synchronized_between_destinations(self):
        page = self.page()
        symbol = "AAPL"
        page.click('.star[data-star="%s"]' % symbol)
        page.click("#nav-watchlist")
        self.assertEqual(page.get_attribute('.star[data-star="%s"]' % symbol, "aria-pressed"), "true")

        # Unstar directly from Watchlist: the row should drop out of the
        # watchlist table itself, and Ranks should see the same state with
        # no stale star left behind.
        page.click('.star[data-star="%s"]' % symbol)
        page.wait_for_timeout(200)
        self.assertEqual(page.eval_on_selector_all("#rows tr", "e => e.length"), 0)

        page.click("#nav-ranks")
        self.assertEqual(page.get_attribute('.star[data-star="%s"]' % symbol, "aria-pressed"), "false")
        self.assertEqual(page.errors, [])

    def test_active_destination_persists_across_reload(self):
        page = self.page()
        # Star a name first -- an empty Watchlist renders zero <tr> rows,
        # and this test's own point is a successful restore, not a timeout
        # waiting for rows that were never going to exist.
        page.click('.star[data-star="AAPL"]')
        page.click("#nav-watchlist")
        page.reload()
        page.wait_for_selector("#rows tr")
        self.assertEqual(page.get_attribute("#nav-watchlist", "aria-current"), "page")
        self.assertTrue(page.is_hidden(".bar"))
        self.assertEqual(page.errors, [])

    def test_independent_scroll_positions_restore_when_switching_tabs(self):
        work = self._page_with_many_scored_rows(60)
        page = self.page(width=390, height=700, url="file://%s/index.html" % work)
        for i in range(60):
            page.click('.star[data-star="SYM%03d"]' % i)

        page.evaluate("window.scrollTo(0, 400)")
        page.wait_for_timeout(100)

        page.click("#nav-watchlist")
        page.wait_for_timeout(100)
        page.evaluate("window.scrollTo(0, 250)")
        page.wait_for_timeout(100)

        page.click("#nav-ranks")
        page.wait_for_timeout(150)
        ranks_scroll = page.evaluate("window.scrollY")
        self.assertGreater(ranks_scroll, 300,
                            "Ranks scroll position should be restored, not reset to 0")

        page.click("#nav-watchlist")
        page.wait_for_timeout(150)
        watch_scroll = page.evaluate("window.scrollY")
        self.assertLess(abs(watch_scroll - 250), 60,
                         "Watchlist should restore its own scroll position, not Ranks'")
        self.assertEqual(page.errors, [])

    def test_bottom_nav_fixed_with_safe_area_and_no_overflow(self):
        page = self.page(width=375, height=780)
        style = page.eval_on_selector(
            "#bottom-nav", "e => { var s = getComputedStyle(e); "
            "return {position: s.position, bottom: s.bottom}; }")
        self.assertEqual(style["position"], "fixed")
        self.assertEqual(style["bottom"], "0px")
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 375)

        body_padding = page.eval_on_selector(
            "body", "e => parseFloat(getComputedStyle(e).paddingBottom)")
        nav_height = page.eval_on_selector(
            "#bottom-nav", "e => e.getBoundingClientRect().height")
        self.assertGreater(body_padding, nav_height,
                            "page content must not disappear behind the fixed nav")
        self.assertEqual(page.errors, [])

    def test_filters_round_trip_and_reset(self):
        page = self.page()
        total = page.eval_on_selector_all("#rows tr", "e => e.length")
        self.assertFalse(page.is_visible("#reset-filters"),
                          "a fresh load at the default MIN SCORE = 1 has nothing to reset")

        page.fill("#f-vol", "30")
        page.wait_for_timeout(200)
        filtered = page.eval_on_selector_all("#rows tr", "e => e.length")
        self.assertLess(filtered, total)

        # An unscored name has null metrics, and null compares as 0 in JS, so a
        # ceiling filter used to let all of them through.
        notes = page.eval_on_selector_all("#rows tr td.note", "e => e.length")
        self.assertEqual(notes, 0, "unscored names leaked through a ceiling filter")

        self.assertTrue(page.is_visible("#reset-filters"))
        self.assertEqual(page.inner_text("#reset-filters"), "Reset filters")
        page.click("#reset-filters")
        page.wait_for_timeout(200)
        self.assertEqual(page.eval_on_selector_all("#rows tr", "e => e.length"), total)
        self.assertEqual(page.input_value("#f-vol"), "")
        self.assertEqual(page.errors, [])

    def test_max_dd_filter_is_removed(self):
        """Drawdown stays a sortable column and detail-panel metric -- only
        the ranking-screen threshold filter is gone.
        """
        page = self.page()
        self.assertIsNone(page.query_selector("#f-dd"), "the Max DD filter input should not exist")
        self.assertIsNotNone(page.query_selector('th[data-key="maxDrawdown"]'),
                              "the Max DD column should still be sortable")
        self.assertEqual(page.errors, [])

    def test_sector_filter_narrows_and_resets(self):
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

        self.assertTrue(page.is_visible("#reset-filters"))
        page.click("#reset-filters")
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

        # textContent, not inner_text: dt labels are styled uppercase, and
        # this should assert against the DOM's actual text, not whatever
        # CSS happens to transform it to for display.
        stats = page.eval_on_selector("#ov-stats", "e => e.textContent")
        self.assertIn("Market cap", stats)
        self.assertNotIn("Last close", stats)
        self.assertNotIn("null", stats)
        self.assertEqual(page.eval_on_selector("#ov-range", "e => e.innerHTML"), "",
                          "no current price means no meaningful marker position to show")
        self.assertEqual(page.errors, [])

    def test_52w_range_shows_low_high_and_a_centered_marker(self):
        """The marker's position comes from where lastClose sits between
        low52w and high52w -- exercised here with a close exactly midway,
        the simplest case to hand-verify against the rendered percentage.
        """
        work = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work, True)
        for name in ("index.html", "returns.js"):
            shutil.copy(ROOT / name, work / name)

        rep = report()
        victim = "AAPL"
        for row in rep["universe"]:
            if row["symbol"] == victim:
                row["lastClose"] = 150.0
                row["low52w"] = 100.0
                row["high52w"] = 200.0
        (work / "scores.js").write_text(
            "// Generated by build.py -- do not edit.\nconst REPORT = %s;\n"
            % json.dumps(rep, indent=1))

        page = self.page(url="file://%s/index.html" % work)
        page.fill("#search", victim)
        page.wait_for_timeout(200)
        page.click("#rows tr:first-child td.ticker")
        page.wait_for_selector("#overlay:not([hidden])", timeout=5000)

        self.assertEqual(page.eval_on_selector("#ov-range .rlabel", "e => e.textContent"),
                          "52W range")
        vals = page.eval_on_selector_all(
            "#ov-range .rvals span", "els => els.map(e => e.textContent)")
        self.assertEqual(vals, ["$100.00", "$200.00"])
        left = page.eval_on_selector("#ov-range .rmarker", "e => parseFloat(e.style.left)")
        self.assertEqual(left, 50.0,
                          "a close exactly midway between low and high should sit at 50%")
        self.assertEqual(page.errors, [])

    def test_52w_range_clamps_a_close_outside_the_cached_low_high(self):
        """A close outside [low52w, high52w] should never happen from real
        build.py output -- both are derived from the same cached series --
        but the presentation layer must still clamp defensively rather than
        draw the marker off the track.
        """
        work = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work, True)
        for name in ("index.html", "returns.js"):
            shutil.copy(ROOT / name, work / name)

        rep = report()
        victim = "AAPL"
        for row in rep["universe"]:
            if row["symbol"] == victim:
                row["lastClose"] = 999.0
                row["low52w"] = 100.0
                row["high52w"] = 200.0
        (work / "scores.js").write_text(
            "// Generated by build.py -- do not edit.\nconst REPORT = %s;\n"
            % json.dumps(rep, indent=1))

        page = self.page(url="file://%s/index.html" % work)
        page.fill("#search", victim)
        page.wait_for_timeout(200)
        page.click("#rows tr:first-child td.ticker")
        page.wait_for_selector("#overlay:not([hidden])", timeout=5000)

        left = page.eval_on_selector("#ov-range .rmarker", "e => parseFloat(e.style.left)")
        self.assertEqual(left, 100.0)
        self.assertEqual(page.errors, [])

    def test_52w_range_centers_the_marker_on_a_zero_width_range(self):
        """low52w == high52w (a single cached day, or a name that never
        moved) must not divide by zero or render a marker at a nonsensical
        position.
        """
        work = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work, True)
        for name in ("index.html", "returns.js"):
            shutil.copy(ROOT / name, work / name)

        rep = report()
        victim = "AAPL"
        for row in rep["universe"]:
            if row["symbol"] == victim:
                row["lastClose"] = 50.0
                row["low52w"] = 50.0
                row["high52w"] = 50.0
        (work / "scores.js").write_text(
            "// Generated by build.py -- do not edit.\nconst REPORT = %s;\n"
            % json.dumps(rep, indent=1))

        page = self.page(url="file://%s/index.html" % work)
        page.fill("#search", victim)
        page.wait_for_timeout(200)
        page.click("#rows tr:first-child td.ticker")
        page.wait_for_selector("#overlay:not([hidden])", timeout=5000)

        left = page.eval_on_selector("#ov-range .rmarker", "e => parseFloat(e.style.left)")
        self.assertEqual(left, 50.0)
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
            "maxVol": "", "sector": ""
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

    def test_reset_filters_resets_min_score_to_one(self):
        """Resetting filters should reset MIN SCORE to the default of "1",
        not to empty.
        """
        page = self.page()
        # Set MIN SCORE to a different value
        page.fill("#f-score", "3")
        page.wait_for_timeout(200)
        self.assertEqual(page.input_value("#f-score"), "3")

        page.click("#reset-filters")
        page.wait_for_timeout(200)

        # MIN SCORE should be reset to "1", not empty
        self.assertEqual(page.input_value("#f-score"), "1")
        self.assertEqual(page.errors, [])


if __name__ == "__main__":
    unittest.main()
