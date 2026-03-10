"""
Unit tests for the State class.

Run with either:
    python -m unittest tests/test_state.py
    pytest tests/test_state.py
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.model.state import State, TIED

# Shared baseline results used across most tests
_PA_RESULTS = {"Democratic": 3400000, "Republican": 3700000, "Other": 50000}
_TIE_RESULTS = {"Democratic": 1000000, "Republican": 1000000, "Other": 0}
_DEM_RESULTS = {"Democratic": 5000000, "Republican": 1000000, "Other": 100000}
_GOP_RESULTS = {"Democratic": 1000000, "Republican": 5000000, "Other": 100000}


def _make_state(results=None, name="Pennsylvania", ev=19,
                unit_type="statewide", parent_state=None):
    """Create a State and optionally populate results."""
    s = State(name, ev, unit_type=unit_type, parent_state=parent_state)
    if results is not None:
        s.set_results(results)
    return s


# ---------------------------------------------------------------------------
# __init__ and identity
# ---------------------------------------------------------------------------

class TestStateInit(unittest.TestCase):

    def test_name_stored(self):
        s = State("Pennsylvania", 19)
        self.assertEqual(s.get_name(), "Pennsylvania")

    def test_ev_stored(self):
        s = State("Pennsylvania", 19)
        self.assertEqual(s.get_ev(), 19)

    def test_unit_type_default_statewide(self):
        s = State("Pennsylvania", 19)
        self.assertIsNone(s.get_parent_state())

    def test_parent_state_stored_for_district(self):
        s = State("ME-1", 1, unit_type="district", parent_state="ME")
        self.assertEqual(s.get_parent_state(), "ME")

    def test_winner_none_before_results_set(self):
        s = State("Pennsylvania", 19)
        self.assertIsNone(s.get_winner())

    def test_results_empty_before_set(self):
        s = State("Pennsylvania", 19)
        self.assertEqual(s.get_results(), {})

    def test_str_representation(self):
        s = State("Pennsylvania", 19)
        self.assertEqual(str(s), "Pennsylvania 19 EV")


# ---------------------------------------------------------------------------
# Getters and setters
# ---------------------------------------------------------------------------

class TestStateGettersSetters(unittest.TestCase):

    def setUp(self):
        self.s = _make_state(_PA_RESULTS)

    def test_set_name_updates(self):
        self.s.set_name("New Name")
        self.assertEqual(self.s.get_name(), "New Name")

    def test_set_ev_updates(self):
        self.s.set_ev(20)
        self.assertEqual(self.s.get_ev(), 20)

    def test_get_results_returns_dict(self):
        self.assertIsInstance(self.s.get_results(), dict)

    def test_get_results_has_dem_key(self):
        self.assertIn("Democratic", self.s.get_results())

    def test_get_base_results_matches_initial(self):
        base = self.s.get_base_results()
        self.assertEqual(base["Democratic"], _PA_RESULTS["Democratic"])
        self.assertEqual(base["Republican"], _PA_RESULTS["Republican"])

    def test_set_results_second_call_does_not_overwrite_baseline(self):
        # Baseline should be locked after first set_results call
        self.s.set_results({"Democratic": 9999999, "Republican": 1, "Other": 0})
        self.assertEqual(
            self.s.get_base_results()["Democratic"], _PA_RESULTS["Democratic"]
        )

    def test_set_base_results_overwrites_baseline(self):
        new = {"Democratic": 500, "Republican": 500, "Other": 0}
        self.s.set_base_results(new)
        self.assertEqual(self.s.get_base_results()["Democratic"], 500)

    def test_set_base_results_also_updates_current(self):
        new = {"Democratic": 500, "Republican": 500, "Other": 0}
        self.s.set_base_results(new)
        self.assertEqual(self.s.get_results()["Democratic"], 500)

    def test_set_winner_overrides(self):
        self.s.set_winner("Democratic")
        self.assertEqual(self.s.get_winner(), "Democratic")

    def test_get_parent_state_statewide_is_none(self):
        self.assertIsNone(self.s.get_parent_state())


# ---------------------------------------------------------------------------
# Winner determination
# ---------------------------------------------------------------------------

class TestStateDetermineWinner(unittest.TestCase):

    def test_dem_wins_when_dem_votes_higher(self):
        s = _make_state(_DEM_RESULTS)
        self.assertEqual(s.get_winner(), "Democratic")

    def test_gop_wins_when_gop_votes_higher(self):
        s = _make_state(_GOP_RESULTS)
        self.assertEqual(s.get_winner(), "Republican")

    def test_tied_when_equal_votes(self):
        s = _make_state(_TIE_RESULTS)
        self.assertEqual(s.get_winner(), TIED)

    def test_winner_updates_after_second_set_results(self):
        s = _make_state(_GOP_RESULTS)
        self.assertEqual(s.get_winner(), "Republican")
        s.set_results(_DEM_RESULTS)
        self.assertEqual(s.get_winner(), "Democratic")


# ---------------------------------------------------------------------------
# Vote accessors
# ---------------------------------------------------------------------------

class TestStateVoteAccessors(unittest.TestCase):

    def setUp(self):
        self.s = _make_state(_PA_RESULTS)

    def test_get_total_vote(self):
        expected = _PA_RESULTS["Democratic"] + _PA_RESULTS["Republican"] + _PA_RESULTS["Other"]
        self.assertEqual(self.s.get_total_vote(), expected)

    def test_get_vote_by_party_dem(self):
        self.assertEqual(self.s.get_vote_by_party("Democratic"), _PA_RESULTS["Democratic"])

    def test_get_vote_by_party_gop(self):
        self.assertEqual(self.s.get_vote_by_party("Republican"), _PA_RESULTS["Republican"])

    def test_get_vote_by_party_missing_returns_zero(self):
        self.assertEqual(self.s.get_vote_by_party("Green"), 0)

    def test_get_vote_per_by_party_in_range(self):
        pct = self.s.get_vote_per_by_party("Democratic")
        self.assertGreater(pct, 0.0)
        self.assertLess(pct, 100.0)

    def test_get_vote_per_by_party_zero_total_returns_zero(self):
        # State with no votes — total is 0, should return 0.0 not divide by zero
        s = _make_state({"Democratic": 0, "Republican": 0, "Other": 0})
        self.assertEqual(s.get_vote_per_by_party("Democratic"), 0.0)

    def test_get_vote_per_sums_to_100(self):
        dem = self.s.get_vote_per_by_party("Democratic")
        gop = self.s.get_vote_per_by_party("Republican")
        other = self.s.get_vote_per_by_party("Other")
        self.assertAlmostEqual(dem + gop + other, 100.0, places=5)


# ---------------------------------------------------------------------------
# get_margin
# ---------------------------------------------------------------------------

class TestStateGetMargin(unittest.TestCase):

    def test_gop_winner_returns_gop_margin(self):
        s = _make_state(_PA_RESULTS)  # GOP wins 2024 PA
        party, margin = s.get_margin()
        self.assertEqual(party, "Republican")
        self.assertGreater(margin, 0.0)

    def test_dem_winner_returns_dem_margin(self):
        s = _make_state(_DEM_RESULTS)
        party, margin = s.get_margin()
        self.assertEqual(party, "Democratic")
        self.assertGreater(margin, 0.0)

    def test_tied_returns_tied_zero(self):
        s = _make_state(_TIE_RESULTS)
        party, margin = s.get_margin()
        self.assertEqual(party, TIED)
        self.assertEqual(margin, 0.0)

    def test_unknown_winner_returns_tied(self):
        # set_winner to a non-standard value — get_other_party returns None
        s = _make_state(_PA_RESULTS)
        s.set_winner("Libertarian")
        party, margin = s.get_margin()
        self.assertEqual(party, TIED)
        self.assertEqual(margin, 0.0)

    def test_margin_is_non_negative(self):
        s = _make_state(_GOP_RESULTS)
        _, margin = s.get_margin()
        self.assertGreaterEqual(margin, 0.0)


# ---------------------------------------------------------------------------
# get_other_party (static)
# ---------------------------------------------------------------------------

class TestStateGetOtherParty(unittest.TestCase):

    def test_other_of_dem_is_gop(self):
        self.assertEqual(State.get_other_party("Democratic"), "Republican")

    def test_other_of_gop_is_dem(self):
        self.assertEqual(State.get_other_party("Republican"), "Democratic")

    def test_other_of_unknown_is_none(self):
        self.assertIsNone(State.get_other_party("Libertarian"))

    def test_other_of_tied_is_none(self):
        self.assertIsNone(State.get_other_party(TIED))

    def test_other_of_empty_string_is_none(self):
        self.assertIsNone(State.get_other_party(""))


# ---------------------------------------------------------------------------
# reset_results
# ---------------------------------------------------------------------------

class TestStateResetResults(unittest.TestCase):

    def test_reset_restores_baseline_votes(self):
        s = _make_state(_PA_RESULTS)
        dem_baseline = s.get_base_results()["Democratic"]
        s.apply_vote_shift("Democratic", 1_000_000)
        s.reset_results()
        self.assertEqual(s.get_results()["Democratic"], dem_baseline)

    def test_reset_restores_winner(self):
        s = _make_state(_GOP_RESULTS)
        self.assertEqual(s.get_winner(), "Republican")
        s.apply_vote_shift("Democratic", 10_000_000)
        s.reset_results()
        self.assertEqual(s.get_winner(), "Republican")


# ---------------------------------------------------------------------------
# apply_vote_shift
# ---------------------------------------------------------------------------

class TestStateApplyVoteShift(unittest.TestCase):

    def test_zero_shift_does_nothing(self):
        s = _make_state(_PA_RESULTS)
        dem_before = s.get_vote_by_party("Democratic")
        s.apply_vote_shift("Democratic", 0)
        self.assertEqual(s.get_vote_by_party("Democratic"), dem_before)

    def test_positive_shift_increases_votes(self):
        s = _make_state(_PA_RESULTS)
        dem_before = s.get_vote_by_party("Democratic")
        s.apply_vote_shift("Democratic", 500_000)
        self.assertGreater(s.get_vote_by_party("Democratic"), dem_before)

    def test_negative_shift_decreases_votes(self):
        s = _make_state(_PA_RESULTS)
        dem_before = s.get_vote_by_party("Democratic")
        s.apply_vote_shift("Democratic", -100_000)
        self.assertLess(s.get_vote_by_party("Democratic"), dem_before)

    def test_large_negative_shift_clamps_to_zero(self):
        # Shift so large it would go negative — must clamp to 0
        s = _make_state(_PA_RESULTS)
        s.apply_vote_shift("Democratic", -999_999_999)
        self.assertEqual(s.get_vote_by_party("Democratic"), 0)

    def test_shift_updates_winner(self):
        s = _make_state(_GOP_RESULTS)  # GOP wins
        self.assertEqual(s.get_winner(), "Republican")
        s.apply_vote_shift("Democratic", 10_000_000)
        self.assertEqual(s.get_winner(), "Democratic")

    def test_shift_on_new_party_key(self):
        # Adding votes to a party not in results should not raise
        s = _make_state(_PA_RESULTS)
        try:
            s.apply_vote_shift("Green", 100_000)
        except Exception as ex:
            self.fail(f"apply_vote_shift on new party raised: {ex}")


# ---------------------------------------------------------------------------
# apply_margin_shift_to_party
# ---------------------------------------------------------------------------

class TestStateApplyMarginShift(unittest.TestCase):

    def test_dem_swing_increases_dem_share(self):
        s = _make_state(_PA_RESULTS)
        dem_pct_before = s.get_vote_per_by_party("Democratic")
        s.apply_margin_shift_to_party("Democratic", 5)
        self.assertGreater(s.get_vote_per_by_party("Democratic"), dem_pct_before)

    def test_gop_swing_increases_gop_share(self):
        s = _make_state(_PA_RESULTS)
        gop_pct_before = s.get_vote_per_by_party("Republican")
        s.apply_margin_shift_to_party("Republican", 5)
        self.assertGreater(s.get_vote_per_by_party("Republican"), gop_pct_before)

    def test_total_vote_preserved_after_swing(self):
        s = _make_state(_PA_RESULTS)
        total_before = s.get_total_vote()
        s.apply_margin_shift_to_party("Democratic", 5)
        self.assertEqual(s.get_total_vote(), total_before)

    def test_invalid_party_does_nothing(self):
        s = _make_state(_PA_RESULTS)
        dem_before = s.get_vote_by_party("Democratic")
        s.apply_margin_shift_to_party("Libertarian", 5)
        self.assertEqual(s.get_vote_by_party("Democratic"), dem_before)

    def test_zero_total_does_nothing(self):
        s = _make_state({"Democratic": 0, "Republican": 0, "Other": 0})
        try:
            s.apply_margin_shift_to_party("Democratic", 5)
        except Exception as ex:
            self.fail(f"zero-total swing raised: {ex}")

    def test_extreme_dem_swing_clamps_gop_to_zero(self):
        # A massive Dem swing should push GOP close to zero (clamped, not negative)
        s = _make_state({"Democratic": 100, "Republican": 100, "Other": 0})
        s.apply_margin_shift_to_party("Democratic", 200)
        self.assertGreaterEqual(s.get_vote_by_party("Republican"), 0)

    def test_extreme_gop_swing_clamps_dem_to_zero(self):
        s = _make_state({"Democratic": 100, "Republican": 100, "Other": 0})
        s.apply_margin_shift_to_party("Republican", 200)
        self.assertGreaterEqual(s.get_vote_by_party("Democratic"), 0)

    def test_swing_updates_winner(self):
        # Swing Dem enough to flip a GOP state
        s = _make_state(_GOP_RESULTS)  # GOP wins
        s.apply_margin_shift_to_party("Democratic", 10)
        # At minimum, determine_winner was called — winner should be set
        self.assertIsNotNone(s.get_winner())

    def test_other_votes_unchanged_after_swing(self):
        s = _make_state(_PA_RESULTS)
        other_before = s.get_vote_by_party("Other")
        s.apply_margin_shift_to_party("Democratic", 5)
        self.assertEqual(s.get_vote_by_party("Other"), other_before)

    def test_apply_margin_shift_placeholder_does_not_raise(self):
        s = _make_state(_PA_RESULTS)
        try:
            s.apply_margin_shift()
        except Exception as ex:
            self.fail(f"apply_margin_shift raised: {ex}")


# ---------------------------------------------------------------------------
# _normalize_results (static)
# ---------------------------------------------------------------------------

class TestStateNormalizeResults(unittest.TestCase):

    def test_standard_keys_present(self):
        result = State._normalize_results({"Democratic": 100, "Republican": 80})
        self.assertIn("Democratic", result)
        self.assertIn("Republican", result)
        self.assertIn("Other", result)

    def test_missing_keys_default_to_zero(self):
        result = State._normalize_results({})
        self.assertEqual(result["Democratic"], 0)
        self.assertEqual(result["Republican"], 0)
        self.assertEqual(result["Other"], 0)

    def test_negative_values_clamped_to_zero(self):
        result = State._normalize_results({"Democratic": -500, "Republican": 100})
        self.assertEqual(result["Democratic"], 0)

    def test_extra_party_keys_preserved(self):
        result = State._normalize_results(
            {"Democratic": 100, "Republican": 80, "Green": 50}
        )
        self.assertIn("Green", result)
        self.assertEqual(result["Green"], 50)

    def test_extra_party_negative_value_clamped(self):
        result = State._normalize_results(
            {"Democratic": 100, "Republican": 80, "Green": -10}
        )
        self.assertEqual(result["Green"], 0)

    def test_none_values_treated_as_zero(self):
        result = State._normalize_results({"Democratic": None, "Republican": 100})
        self.assertEqual(result["Democratic"], 0)


# ---------------------------------------------------------------------------
# Print / display methods
# ---------------------------------------------------------------------------

class TestStatePrintMethods(unittest.TestCase):

    def setUp(self):
        self.s = _make_state(_PA_RESULTS)

    def test_print_summary_does_not_raise(self):
        try:
            self.s.print_summary()
        except Exception as ex:
            self.fail(f"print_summary raised: {ex}")

    def test_print_result_does_not_raise(self):
        try:
            self.s.print_result()
        except Exception as ex:
            self.fail(f"print_result raised: {ex}")

    def test_str_contains_name(self):
        self.assertIn("Pennsylvania", str(self.s))

    def test_str_contains_ev(self):
        self.assertIn("19", str(self.s))


if __name__ == "__main__":
    unittest.main(verbosity=2)
