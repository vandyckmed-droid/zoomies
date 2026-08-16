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
        page = self.page()
        rows = page.eval_on_selector_all("#rows tr", "e => e.length")
        self.assertEqual(rows, self.report["displayCount"])
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
        page.click('.star[data-star="%s"]' % self.report["universe"][0]["symbol"])
        page.click('.star[data-star="%s"]' % self.report["universe"][1]["symbol"])
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

        a, b = self.report["universe"][0]["symbol"], self.report["universe"][1]["symbol"]
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
        page.click('.star[data-star="%s"]' % self.report["universe"][0]["symbol"])
        page.click('.star[data-star="%s"]' % self.report["universe"][1]["symbol"])
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

        a, b, victim = (self.report["universe"][i]["symbol"] for i in (0, 1, 2))
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
        page = self.page()
        page.evaluate(
            "localStorage.setItem('zoomies.view', "
            "JSON.stringify({key: 'rank', sector: 'Sector That No Longer Exists'}))")
        page.reload()
        page.wait_for_selector("#rows tr")

        self.assertEqual(page.input_value("#f-sector"), "")
        self.assertEqual(page.eval_on_selector_all("#rows tr", "e => e.length"),
                          self.report["displayCount"])
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

    def test_search_survives_a_reload(self):
        page = self.page()
        symbol = self.report["universe"][0]["symbol"]
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
        victim = rep["universe"][3]["symbol"]
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


if __name__ == "__main__":
    unittest.main()
