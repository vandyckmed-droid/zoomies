"""Unit tests for build.py logic that doesn't need a browser or a price cache.

Lives in tests/ (not e2e/) on purpose: ci.yml's "Test" step runs
`unittest discover -s tests` and only exists when this directory does --
adding it turns that step on. e2e/'s browser suite covers the client;
this covers build.py's own maths directly, without reconstructing a
realistic price history just to exercise a few lines of ranking logic.
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import build  # noqa: E402


class RankByScoreTest(unittest.TestCase):
    def test_excludes_a_name_missing_from_the_cohort(self):
        """The regression case from PR #17's review: a name can have a
        valid score in `scores` (e.g. build.py's historical snapshot) while
        being absent from the comparable cohort (e.g. it has no valid score
        today). That name must not occupy a rank slot at all -- if it did,
        every other name below it would be shifted down by one, an
        apparent rank change caused purely by GHOST's presence rather than
        anyone's actual momentum.
        """
        scores = {"A": 5.0, "GHOST": 4.0, "B": 3.0, "C": 1.0}
        cohort = {"A", "B", "C"}   # GHOST deliberately left out

        ranks = build.rank_by_score(scores, cohort=cohort)

        self.assertEqual(ranks, {"A": 1, "B": 2, "C": 3})
        self.assertNotIn("GHOST", ranks)

    def test_a_score_of_none_never_gets_a_rank(self):
        scores = {"A": 5.0, "B": None, "C": 1.0}
        self.assertEqual(build.rank_by_score(scores), {"A": 1, "C": 2})

    def test_no_cohort_ranks_every_name_with_a_score(self):
        scores = {"A": 5.0, "B": 3.0, "C": 1.0}
        self.assertEqual(build.rank_by_score(scores), {"A": 1, "B": 2, "C": 3})

    def test_empty_input_ranks_nothing(self):
        self.assertEqual(build.rank_by_score({}), {})
        self.assertEqual(build.rank_by_score({"A": 5.0}, cohort=set()), {})


class PriceRange52wTest(unittest.TestCase):
    def test_no_cached_prices_returns_nulls(self):
        self.assertEqual(build.price_range_52w({}),
                          {"low52w": None, "high52w": None})

    def test_uses_the_trailing_52_weeks_ending_on_the_latest_cached_date(self):
        """A price from more than 52 weeks before the latest cached date must
        not pull the low/high toward it -- only the trailing window counts,
        the same way a real 52-week range excludes a year-old spike.
        """
        prices = {
            "2024-01-01": 500.0,    # far outside the window -- must be ignored
            "2025-01-15": 90.0,
            "2025-06-01": 150.0,
            "2026-01-10": 110.0,    # latest cached date
        }
        self.assertEqual(build.price_range_52w(prices),
                          {"low52w": 90.0, "high52w": 150.0})

    def test_less_than_a_year_of_history_uses_whatever_is_cached(self):
        """A recent IPO, or a name newly added to the tracked universe, has
        no artificial requirement to reach a full year before it gets a
        range -- real ticker pages show the same thing.
        """
        prices = {"2026-01-05": 20.0, "2026-01-10": 25.0, "2026-01-15": 22.0}
        self.assertEqual(build.price_range_52w(prices),
                          {"low52w": 20.0, "high52w": 25.0})

    def test_a_single_cached_day_gives_a_zero_width_range(self):
        """Degenerate, not an error -- the presentation layer is what
        decides how to render low == high, not this function.
        """
        self.assertEqual(build.price_range_52w({"2026-01-10": 42.0}),
                          {"low52w": 42.0, "high52w": 42.0})


if __name__ == "__main__":
    unittest.main()
