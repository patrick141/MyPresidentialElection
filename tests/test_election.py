"""
Unit tests for the Election class.

Run with either:
    python -m unittest tests/test_election.py
    pytest tests/test_election.py
"""

import sys
import os
import unittest
import tempfile
import shutil
import csv
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.model.election import Election
from src.model.state import State


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_temp_csv(rows, suffix="_2024_test.csv"):
    """Write a minimal election CSV to a temp file and return its path."""
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, newline=""
    )
    writer = csv.writer(f)
    writer.writerow(["State", "EV", "Democratic", "Republican", "Other"])
    for row in rows:
        writer.writerow(row)
    f.close()
    return f.name


# ---------------------------------------------------------------------------
# __init__ and year validation
# ---------------------------------------------------------------------------

class TestElectionInit(unittest.TestCase):

    def test_valid_year_string_loads(self):
        e = Election("2024")
        self.assertEqual(e.year, "2024")

    def test_states_list_populated(self):
        e = Election("2024")
        self.assertGreater(len(e.states), 0)

    def test_label_defaults_to_year(self):
        e = Election("2024")
        self.assertEqual(e.label, "2024")

    def test_custom_label_stored(self):
        e = Election("2024", label="My Label")
        self.assertEqual(e.label, "My Label")

    def test_min_ev_needed_default_270(self):
        e = Election("2024")
        self.assertEqual(e.min_ev_needed, 270)

    def test_total_ev_equals_538(self):
        e = Election("2024")
        total = sum(s.get_ev() for s in e.states)
        self.assertEqual(total, 538)

    def test_invalid_year_not_divisible_by_4(self):
        with self.assertRaises(ValueError):
            Election("2023")

    def test_invalid_year_odd(self):
        with self.assertRaises(ValueError):
            Election("2021")

    def test_invalid_year_too_early(self):
        with self.assertRaises(ValueError):
            Election("1700")

    def test_invalid_year_too_late(self):
        with self.assertRaises(ValueError):
            Election("2104")

    def test_invalid_non_year_string(self):
        with self.assertRaises(ValueError):
            Election("notayear")

    def test_validate_presidential_year_valid(self):
        # Static method — should not raise for a valid year
        Election._validate_presidential_year(2024)

    def test_validate_presidential_year_odd_raises(self):
        with self.assertRaises(ValueError):
            Election._validate_presidential_year(2023)

    def test_validate_presidential_year_too_early_raises(self):
        with self.assertRaises(ValueError):
            Election._validate_presidential_year(1700)

    def test_validate_presidential_year_too_late_raises(self):
        with self.assertRaises(ValueError):
            Election._validate_presidential_year(2104)

    def test_csv_path_constructor_loads_states(self):
        path = _make_temp_csv([
            ["Pennsylvania", 19, 3400000, 3700000, 50000],
            ["Michigan",     15, 2800000, 2700000, 40000],
        ])
        try:
            e = Election(path)
            self.assertEqual(len(e.states), 2)
        finally:
            os.unlink(path)

    def test_csv_path_label_defaults_to_stem(self):
        path = _make_temp_csv([["Pennsylvania", 19, 1000, 900, 0]])
        try:
            e = Election(path)
            self.assertEqual(e.label, os.path.splitext(os.path.basename(path))[0])
        finally:
            os.unlink(path)

    def test_csv_path_no_year_in_filename_raises(self):
        path = _make_temp_csv([["Pennsylvania", 19, 1000, 900, 0]], suffix="_badname.csv")
        try:
            with self.assertRaises(ValueError):
                Election(path)
        finally:
            os.unlink(path)

    def test_missing_data_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            Election("1792")  # valid year but no CSV on disk


# ---------------------------------------------------------------------------
# determine_winner and results aggregation
# ---------------------------------------------------------------------------

class TestElectionDetermineWinner(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.e = Election("2024")

    def test_results_has_democratic_key(self):
        self.assertIn("Democratic", self.e.results)

    def test_results_has_republican_key(self):
        self.assertIn("Republican", self.e.results)

    def test_results_has_tossup_ev_key(self):
        self.assertIn("TossupEV", self.e.results)

    def test_winner_is_valid_party(self):
        self.assertIn(self.e.winner, ("Democratic", "Republican", "TIED"))

    def test_ev_totals_sum_to_538(self):
        dem_ev   = self.e.results["Democratic"][1]
        gop_ev   = self.e.results["Republican"][1]
        tossup   = self.e.results["TossupEV"]
        self.assertEqual(dem_ev + gop_ev + tossup, 538)

    def test_total_votes_positive(self):
        self.assertGreater(self.e.get_total_votes(), 0)

    def test_results_tuple_structure(self):
        # Each party value is (total_votes, total_ev)
        dem = self.e.results["Democratic"]
        self.assertIsInstance(dem, tuple)
        self.assertEqual(len(dem), 2)


# ---------------------------------------------------------------------------
# Popular vote margin
# ---------------------------------------------------------------------------

class TestElectionPopularVoteMargin(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.e = Election("2024")

    def test_returns_tuple(self):
        self.assertIsInstance(self.e.get_popular_vote_margin(), tuple)

    def test_tuple_length_two(self):
        self.assertEqual(len(self.e.get_popular_vote_margin()), 2)

    def test_party_is_valid(self):
        party, _ = self.e.get_popular_vote_margin()
        self.assertIn(party, ("Democratic", "Republican", "TIED"))

    def test_margin_non_negative(self):
        _, margin = self.e.get_popular_vote_margin()
        self.assertGreaterEqual(margin, 0.0)

    def test_margin_under_100(self):
        _, margin = self.e.get_popular_vote_margin()
        self.assertLess(margin, 100.0)


# ---------------------------------------------------------------------------
# State lookup and filtering
# ---------------------------------------------------------------------------

class TestElectionStateLookup(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.e = Election("2024")

    def test_find_existing_state(self):
        s = self.e.find_state_by_name("Pennsylvania")
        self.assertIsNotNone(s)

    def test_find_state_returns_correct_name(self):
        s = self.e.find_state_by_name("Pennsylvania")
        self.assertEqual(s.get_name(), "Pennsylvania")

    def test_find_nonexistent_state_returns_none(self):
        self.assertIsNone(self.e.find_state_by_name("NotAState"))

    def test_get_result_found(self):
        result = self.e.get_result_of_state_name("Pennsylvania")
        self.assertIsNotNone(result)
        self.assertIn("Democratic", result)
        self.assertIn("Republican", result)

    def test_get_result_not_found_returns_none(self):
        self.assertIsNone(self.e.get_result_of_state_name("NotAState"))

    def test_get_states_as_list_returns_list(self):
        self.assertIsInstance(self.e.get_states_as_list(), list)

    def test_get_states_as_list_nonempty(self):
        self.assertGreater(len(self.e.get_states_as_list()), 0)

    def test_get_states_won_by_dem_all_dem(self):
        for s in self.e.get_states_won_by_party("Democratic"):
            self.assertEqual(s.get_winner(), "Democratic")

    def test_get_states_won_by_gop_all_gop(self):
        for s in self.e.get_states_won_by_party("Republican"):
            self.assertEqual(s.get_winner(), "Republican")

    def test_dem_plus_gop_states_leq_total(self):
        dem = len(self.e.get_states_won_by_party("Democratic"))
        gop = len(self.e.get_states_won_by_party("Republican"))
        self.assertLessEqual(dem + gop, len(self.e.states))

    def test_is_split_ev_unit_maine(self):
        maine = self.e.find_state_by_name("Maine")
        if maine:
            self.assertTrue(self.e.is_split_ev_unit(maine))

    def test_is_split_ev_unit_nebraska(self):
        nebraska = self.e.find_state_by_name("Nebraska")
        if nebraska:
            self.assertTrue(self.e.is_split_ev_unit(nebraska))

    def test_is_split_ev_unit_me1_district(self):
        me1 = self.e.find_state_by_name("ME-1")
        if me1:
            self.assertTrue(self.e.is_split_ev_unit(me1))

    def test_is_split_ev_unit_ne1_district(self):
        ne1 = self.e.find_state_by_name("NE-1")
        if ne1:
            self.assertTrue(self.e.is_split_ev_unit(ne1))

    def test_is_split_ev_unit_regular_state_false(self):
        pa = self.e.find_state_by_name("Pennsylvania")
        if pa:
            self.assertFalse(self.e.is_split_ev_unit(pa))


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------

class TestElectionSorting(unittest.TestCase):

    def setUp(self):
        self.e = Election("2024")

    def test_sort_alphabetically_orders_names(self):
        self.e.sort_alphabetically()
        names = [s.get_name() for s in self.e.states]
        self.assertEqual(names, sorted(names))

    def test_sort_alphabetically_preserves_count(self):
        count_before = len(self.e.states)
        self.e.sort_alphabetically()
        self.assertEqual(len(self.e.states), count_before)

    def test_sort_by_margins_winner_states_come_first(self):
        self.e.sort_by_state_margins()
        winner = self.e.winner
        if self.e.states and winner in ("Democratic", "Republican"):
            self.assertEqual(self.e.states[0].get_winner(), winner)

    def test_sort_by_margins_preserves_count(self):
        count_before = len(self.e.states)
        self.e.sort_by_state_margins()
        self.assertEqual(len(self.e.states), count_before)


# ---------------------------------------------------------------------------
# Simulation — swing and boost
# ---------------------------------------------------------------------------

class TestElectionSimulation(unittest.TestCase):

    def setUp(self):
        # Fresh election per test so swings never bleed through
        self.e = Election("2024")

    def test_dem_swing_increases_dem_ev(self):
        dem_ev_before = self.e.results["Democratic"][1]
        self.e.apply_margin_swing_all_states("Democratic", 10)
        self.assertGreaterEqual(self.e.results["Democratic"][1], dem_ev_before)

    def test_gop_swing_increases_gop_ev(self):
        gop_ev_before = self.e.results["Republican"][1]
        self.e.apply_margin_swing_all_states("Republican", 10)
        self.assertGreaterEqual(self.e.results["Republican"][1], gop_ev_before)

    def test_ev_total_still_538_after_swing(self):
        self.e.apply_margin_swing_all_states("Democratic", 5)
        dem = self.e.results["Democratic"][1]
        gop = self.e.results["Republican"][1]
        tossup = self.e.results["TossupEV"]
        self.assertEqual(dem + gop + tossup, 538)

    def test_large_dem_swing_gives_dem_ec_majority(self):
        self.e.apply_margin_swing_all_states("Democratic", 10)
        self.assertGreaterEqual(self.e.results["Democratic"][1], 270)

    def test_large_gop_swing_gives_gop_ec_majority(self):
        self.e.apply_margin_swing_all_states("Republican", 10)
        self.assertGreaterEqual(self.e.results["Republican"][1], 270)

    def test_reset_restores_dem_ev(self):
        dem_ev_before = self.e.results["Democratic"][1]
        self.e.apply_margin_swing_all_states("Democratic", 10)
        self.e.reset_all_states()
        self.assertEqual(self.e.results["Democratic"][1], dem_ev_before)

    def test_reset_restores_total_votes(self):
        total_before = self.e.get_total_votes()
        self.e.apply_margin_swing_all_states("Republican", 5)
        self.e.reset_all_states()
        self.assertEqual(self.e.get_total_votes(), total_before)

    def test_reset_restores_538_ev(self):
        self.e.apply_margin_swing_all_states("Democratic", 8)
        self.e.reset_all_states()
        total = sum(s.get_ev() for s in self.e.states)
        self.assertEqual(total, 538)

    def test_vote_boost_increases_dem_votes(self):
        dem_before = self.e.results["Democratic"][0]
        self.e.apply_vote_boost_all_states("Democratic", 100_000)
        self.assertGreater(self.e.results["Democratic"][0], dem_before)

    def test_vote_boost_does_not_affect_districts(self):
        # Districts (parent_state not None) are skipped by apply_vote_boost_all_states
        me1 = self.e.find_state_by_name("ME-1")
        if me1:
            dem_before = me1.get_vote_by_party("Democratic")
            self.e.apply_vote_boost_all_states("Democratic", 500_000)
            self.assertEqual(me1.get_vote_by_party("Democratic"), dem_before)

    def test_single_state_swing(self):
        pa = self.e.find_state_by_name("Pennsylvania")
        dem_before = pa.get_vote_by_party("Democratic")
        self.e.apply_margin_swing_to_state("Pennsylvania", "Democratic", 10)
        # Winner should now be set (determine_winner was called)
        self.assertIsNotNone(pa.get_winner())

    def test_single_state_vote_boost(self):
        pa = self.e.find_state_by_name("Pennsylvania")
        dem_before = pa.get_vote_by_party("Democratic")
        self.e.apply_vote_boost_to_state("Pennsylvania", "Democratic", 500_000)
        self.assertGreater(pa.get_vote_by_party("Democratic"), dem_before)

    def test_swing_to_nonexistent_state_does_not_raise(self):
        # Should silently return, not crash
        try:
            self.e.apply_margin_swing_to_state("NotAState", "Democratic", 5)
        except Exception as ex:
            self.fail(f"swing to missing state raised: {ex}")

    def test_boost_to_nonexistent_state_does_not_raise(self):
        try:
            self.e.apply_vote_boost_to_state("NotAState", "Democratic", 1000)
        except Exception as ex:
            self.fail(f"boost to missing state raised: {ex}")


# ---------------------------------------------------------------------------
# Analytics — tipping point and EC bias
# ---------------------------------------------------------------------------

class TestElectionAnalytics(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.e = Election("2024")

    def test_tipping_point_is_state_or_none(self):
        tp = self.e.get_tipping_point_state()
        self.assertTrue(tp is None or isinstance(tp, State))

    def test_tipping_point_won_by_ec_winner(self):
        dem_ev = self.e.results["Democratic"][1]
        gop_ev = self.e.results["Republican"][1]
        if dem_ev >= 270:
            ec_winner = "Democratic"
        elif gop_ev >= 270:
            ec_winner = "Republican"
        else:
            return  # no majority, skip
        tp = self.e.get_tipping_point_state()
        self.assertIsNotNone(tp)
        self.assertEqual(tp.get_winner(), ec_winner)

    def test_tipping_point_ev_at_least_one(self):
        tp = self.e.get_tipping_point_state()
        if tp:
            self.assertGreater(tp.get_ev(), 0)

    def test_get_ec_bias_returns_tuple(self):
        self.assertIsInstance(self.e.get_ec_bias(), tuple)

    def test_get_ec_bias_tuple_length_two(self):
        self.assertEqual(len(self.e.get_ec_bias()), 2)

    def test_get_ec_bias_party_valid(self):
        party, _ = self.e.get_ec_bias()
        self.assertIn(party, ("Democratic", "Republican", "TIED"))

    def test_get_ec_bias_margin_non_negative(self):
        _, margin = self.e.get_ec_bias()
        self.assertGreaterEqual(margin, 0.0)

    def test_relative_to_pv_margin_returns_tuple(self):
        pa = self.e.find_state_by_name("Pennsylvania")
        if pa:
            result = self.e.get_relative_to_pv_margin(pa)
            self.assertIsInstance(result, tuple)
            self.assertEqual(len(result), 2)

    def test_relative_to_pv_margin_non_negative(self):
        pa = self.e.find_state_by_name("Pennsylvania")
        if pa:
            _, margin = self.e.get_relative_to_pv_margin(pa)
            self.assertGreaterEqual(margin, 0.0)


# ---------------------------------------------------------------------------
# Export — CSV and JSON
# ---------------------------------------------------------------------------

class TestElectionExport(unittest.TestCase):

    def setUp(self):
        self.e = Election("2024")
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _path(self, filename):
        return os.path.join(self.tmpdir, filename)

    def test_export_csv_creates_file(self):
        path = self._path("export.csv")
        self.e.export_scenario(path)
        self.assertTrue(os.path.exists(path))

    def test_export_csv_has_required_columns(self):
        path = self._path("export.csv")
        self.e.export_scenario(path)
        with open(path) as f:
            cols = csv.DictReader(f).fieldnames
        for col in ("State", "EV", "Democratic", "Republican", "Other"):
            self.assertIn(col, cols)

    def test_export_csv_row_count_matches_states(self):
        path = self._path("export.csv")
        self.e.export_scenario(path)
        with open(path) as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), len(self.e.states))

    def test_export_json_creates_file(self):
        path = self._path("export.json")
        self.e.export_scenario(path)
        self.assertTrue(os.path.exists(path))

    def test_export_json_is_valid_list(self):
        path = self._path("export.json")
        self.e.export_scenario(path)
        with open(path) as f:
            data = json.load(f)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_export_json_first_row_has_required_keys(self):
        path = self._path("export.json")
        self.e.export_scenario(path)
        with open(path) as f:
            data = json.load(f)
        for key in ("State", "EV", "Democratic", "Republican", "Other"):
            self.assertIn(key, data[0])

    def test_export_json_row_count_matches_states(self):
        path = self._path("export.json")
        self.e.export_scenario(path)
        with open(path) as f:
            data = json.load(f)
        self.assertEqual(len(data), len(self.e.states))

    def test_export_creates_parent_directory(self):
        path = self._path("subdir/nested/export.csv")
        self.e.export_scenario(path)
        self.assertTrue(os.path.exists(path))


# ---------------------------------------------------------------------------
# Print / display methods (just verify no exceptions raised)
# ---------------------------------------------------------------------------

class TestElectionPrintMethods(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.e = Election("2024")

    def test_print_summary_does_not_raise(self):
        try:
            self.e.print_summary()
        except Exception as ex:
            self.fail(f"print_summary raised: {ex}")

    def test_str_returns_string(self):
        # Election has no __str__ but checking winner string used in print_summary
        self.assertIsInstance(self.e.winner, str)


# ---------------------------------------------------------------------------
# Edge cases targeting specific uncovered branches in election.py
# ---------------------------------------------------------------------------

class TestElectionEdgeCases(unittest.TestCase):

    # --- Line 106: CSV missing required columns ---
    def test_csv_missing_columns_raises(self):
        path = _make_temp_csv(
            [["Pennsylvania", 19, 100, 90]],
            suffix="_2024_bad.csv"
        )
        # Rewrite without "Other" column header
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["State", "EV", "Democratic"])  # missing Republican + Other
            writer.writerow(["Pennsylvania", 19, 100])
        try:
            with self.assertRaises(ValueError):
                Election(path)
        finally:
            os.unlink(path)

    # --- Lines 172-176: TIED state EVs go to tossup bucket ---
    def test_tied_state_ev_goes_to_tossup(self):
        path = _make_temp_csv([
            ["Pennsylvania", 19, 1000, 1000, 0],   # exact tie → TIED
            ["Michigan",     15, 500,  2000, 0],
        ])
        try:
            e = Election(path)
            self.assertGreater(e.results["TossupEV"], 0)
        finally:
            os.unlink(path)

    # --- Lines 175-176: unrecognized winner label → else tossup branch ---
    def test_unrecognized_winner_treated_as_tossup(self):
        path = _make_temp_csv([
            ["Pennsylvania", 19, 1000, 900, 0],
            ["Michigan",     15, 500,  200, 0],
        ])
        try:
            e = Election(path)
            pa = e.find_state_by_name("Pennsylvania")
            pa.set_winner("Libertarian")   # triggers else-branch in determine_winner
            e.determine_winner()
            total = (e.results["Democratic"][1] + e.results["Republican"][1]
                     + e.results["TossupEV"])
            self.assertEqual(total, 34)
        finally:
            os.unlink(path)

    # --- Line 189: popular vote tie → self.winner = TIED ---
    def test_national_popular_vote_tie_sets_tied_winner(self):
        path = _make_temp_csv([
            ["Pennsylvania", 19, 1000, 1000, 0],  # TIED state (equal votes)
        ])
        try:
            e = Election(path)
            self.assertEqual(e.winner, "TIED")
        finally:
            os.unlink(path)

    # --- Lines 313-314: swing to a district state skips ---
    def test_swing_to_district_state_skips(self):
        e = Election("2024")
        me1 = e.find_state_by_name("ME-1")
        if me1:
            dem_before = me1.get_vote_by_party("Democratic")
            e.apply_margin_swing_to_state("ME-1", "Democratic", 5)
            # District should be unchanged
            self.assertEqual(me1.get_vote_by_party("Democratic"), dem_before)

    # --- Lines 324-325: vote boost to a district state skips ---
    def test_boost_to_district_state_skips(self):
        e = Election("2024")
        ne1 = e.find_state_by_name("NE-1")
        if ne1:
            dem_before = ne1.get_vote_by_party("Democratic")
            e.apply_vote_boost_to_state("NE-1", "Democratic", 500_000)
            self.assertEqual(ne1.get_vote_by_party("Democratic"), dem_before)

    # --- Line 341: get_popular_vote_margin when winner is TIED ---
    def test_popular_vote_margin_when_winner_tied(self):
        path = _make_temp_csv([["Pennsylvania", 19, 1000, 1000, 0]])
        try:
            e = Election(path)
            self.assertEqual(e.winner, "TIED")
            party, margin = e.get_popular_vote_margin()
            self.assertEqual(margin, 0.0)
        finally:
            os.unlink(path)

    # --- Line 345: get_popular_vote_margin when total = 0 ---
    def test_popular_vote_margin_zero_total(self):
        path = _make_temp_csv([["Pennsylvania", 19, 0, 0, 0]])
        try:
            e = Election(path)
            party, margin = e.get_popular_vote_margin()
            self.assertEqual(margin, 0.0)
        finally:
            os.unlink(path)

    # --- Line 360: get_relative_to_pv_margin when other_party is None (TIED election) ---
    def test_relative_to_pv_margin_tied_election(self):
        path = _make_temp_csv([
            ["Pennsylvania", 19, 1000, 1000, 0],
            ["Michigan",     15, 1000, 1000, 0],
        ])
        try:
            e = Election(path)
            pa = e.find_state_by_name("Pennsylvania")
            result = e.get_relative_to_pv_margin(pa)
            self.assertIsInstance(result, tuple)
        finally:
            os.unlink(path)

    # --- Lines 364-365: get_relative_to_pv_margin with a tossup state ---
    def test_relative_to_pv_margin_tossup_state(self):
        e = Election("2024")
        # Force a state to TIED so it enters the tossup branch
        pa = e.find_state_by_name("Pennsylvania")
        if pa:
            pa.set_winner("Tossup")
            result = e.get_relative_to_pv_margin(pa)
            self.assertIsInstance(result, tuple)

    # --- Lines 376-377: state leans opposite direction to national PV winner ---
    def test_relative_to_pv_margin_opposite_direction(self):
        e = Election("2024")
        # 2024: GOP won national PV; find a Dem-winning state (e.g. California)
        california = e.find_state_by_name("California")
        if california and california.get_winner() == "Democratic":
            party, margin = e.get_relative_to_pv_margin(california)
            self.assertIsInstance(party, str)
            self.assertGreaterEqual(margin, 0.0)

    # --- Line 390: get_tipping_point_state Dem majority path ---
    def test_tipping_point_dem_majority(self):
        e = Election("2024")
        e.apply_margin_swing_all_states("Democratic", 10)
        dem_ev = e.results["Democratic"][1]
        if dem_ev >= 270:
            tp = e.get_tipping_point_state()
            self.assertIsNotNone(tp)
            self.assertEqual(tp.get_winner(), "Democratic")

    # --- Line 394: get_tipping_point_state returns None when no 270 majority ---
    def test_tipping_point_no_majority_returns_none(self):
        path = _make_temp_csv([
            ["Pennsylvania", 10, 1000, 900,  0],
            ["Michigan",     10, 900,  1000, 0],
        ])
        try:
            e = Election(path)
            # Neither party has 270 — tipping point should be None
            tp = e.get_tipping_point_state()
            self.assertIsNone(tp)
        finally:
            os.unlink(path)

    # --- Line 413: get_ec_bias returns TIED when no tipping point ---
    def test_ec_bias_no_majority_returns_tied(self):
        path = _make_temp_csv([
            ["Pennsylvania", 10, 1000, 900,  0],
            ["Michigan",     10, 900,  1000, 0],
        ])
        try:
            e = Election(path)
            party, margin = e.get_ec_bias()
            self.assertEqual(party, "TIED")
            self.assertEqual(margin, 0.0)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
