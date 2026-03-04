"""
State class (improved)

- Keeps baseline results (base_results) and current simulated results (results)
- Supports:
  1) apply_vote_shift: add votes to one party only (total votes increases)
  2) apply_margin_shift_to_party: swing margin toward Dem/GOP by moving votes (total constant for Dem+GOP)
- All original methods exist, but in snake_case
- Python 3.8 compatible (no list[str], no PEP604 unions, no typing.List)
"""

OTHER_PARTY = "Other"
TIED = "TIED"


class State:
    def __init__(self, name, ev, unit_type="statewide", parent_state=None):
        self._name = name
        self._ev = ev
        self._unit_type = unit_type          # "statewide" or "district"
        self._parent_state = parent_state    # "ME", "NE", or None

        self._base_results = {}
        self._results = {}
        self._winner = None

    # -------------------------
    # Original methods -> snake_case
    # -------------------------

    def get_name(self):
        return self._name

    def set_name(self, name):
        self._name = name

    def get_ev(self):
        return self._ev

    def set_ev(self, new_ev):
        self._ev = new_ev

    def get_results(self):
        """
        Current simulated results dict.
        """
        return self._results

    def get_base_results(self):
        """
        Baseline results dict (original loaded results).
        """
        return self._base_results

    def set_results(self, p_results):
        """
        Set baseline + current results from input.
        This mirrors your original behavior but now also stores a baseline copy.

        Expected keys:
          - 'Democratic'
          - 'Republican'
          - optional 'Other'
        """
        normalized = self._normalize_results(p_results)

        # If baseline isn't set yet, set it.
        if not self._base_results:
            self._base_results = normalized.copy()

        # Always set current results
        self._results = normalized.copy()
        self.determine_winner()

    def set_base_results(self, p_results):
        """
        Explicitly set baseline results (overwrites baseline) and resets current to baseline.
        Useful if you ever load/replace data.
        """
        normalized = self._normalize_results(p_results)
        self._base_results = normalized.copy()
        self._results = normalized.copy()
        self.determine_winner()

    def reset_results(self):
        """
        Reset current results back to baseline.
        """
        self._results = self._base_results.copy()
        self.determine_winner()

    def get_parent_state(self):
        return self._parent_state

    def determine_winner(self):
        dem_vote = int(self._results.get("Democratic", 0) or 0)
        gop_vote = int(self._results.get("Republican", 0) or 0)

        if dem_vote > gop_vote:
            self._winner = "Democratic"
        elif gop_vote > dem_vote:
            self._winner = "Republican"
        else:
            self._winner = TIED

    def print_summary(self):
        print(self)
        print("BASE:", self._base_results)
        print("CURR:", self._results)
        print("WINNER:", self._winner)

    def print_result(self):
        # kept for parity with your original; you can customize later
        print(self._results)

    def get_total_vote(self):
        return int(sum(self._results.values()))

    def get_vote_by_party(self, party):
        return int(self._results.get(party, 0) or 0)

    def get_vote_per_by_party(self, party):
        total = self.get_total_vote()
        if total <= 0:
            return 0.0
        return (self.get_vote_by_party(party) / total) * 100.0

    def get_winner(self):
        return self._winner

    def set_winner(self, p_winner):
        self._winner = p_winner

    @staticmethod
    def get_other_party(o_party):
        if o_party == "Democratic":
            return "Republican"
        if o_party == "Republican":
            return "Democratic"
        # For TIED or anything else, return None (safer than a string that breaks dict lookups)
        return None

    def get_margin(self):
        """
        Returns (winner, margin_percent) using CURRENT results.
        Margin is computed as (winner% - other_major_party%).
        If tied or cannot compute, returns (TIED, 0.0).
        """
        if self._winner == TIED:
            return (TIED, 0.0)

        other_party = self.get_other_party(self._winner)
        if other_party is None:
            return (TIED, 0.0)

        winner_per = self.get_vote_per_by_party(self._winner)
        other_per = self.get_vote_per_by_party(other_party)
        return (self._winner, winner_per - other_per)

    # -------------------------
    # Simulation operations
    # -------------------------

    def apply_vote_shift(self, party, shift_votes):
        """
        Add votes to ONE party only (turnout/boost). Total votes increase.
        Updates winner afterwards.
        """
        shift_votes = int(shift_votes)

        if shift_votes == 0:
            return

        # Copy so we don't accidentally mutate external references
        new_results = self._results.copy()
        new_results[party] = int(new_results.get(party, 0) or 0) + shift_votes

        # Prevent negatives (if someone passes negative votes)
        if new_results[party] < 0:
            new_results[party] = 0

        self._results = self._normalize_results(new_results)
        self.determine_winner()

    def apply_margin_shift_to_party(self, target_party, swing_points):
        """
        Apply a TRUE X-point swing toward target_party measured in TOTAL-vote percentage points,
        keeping 'Other' votes unchanged.

        Interpretation:
          - Add +X/2 points to target party's TOTAL-vote share
          - Subtract -X/2 points from opposing party's TOTAL-vote share
          - Keep Other votes unchanged
          - Total votes stay constant
        Example:
          48D 49R 3O, swing +5 to Dem => 50.5D 46.5R 3O
        """
        if target_party not in ("Democratic", "Republican"):
            return

        self._results = self._normalize_results(self._results)

        dem = int(self._results.get("Democratic", 0) or 0)
        gop = int(self._results.get("Republican", 0) or 0)
        other = int(self._results.get("Other", 0) or 0)

        total = dem + gop + other
        if total <= 0:
            return

        # Convert swing toward party into (+X/2 to target, -X/2 from opponent)
        half = float(swing_points) / 2.0
        if target_party == "Democratic":
            dem_target_pct = (dem / total) * 100.0 + half
            gop_target_pct = (gop / total) * 100.0 - half
        else:
            dem_target_pct = (dem / total) * 100.0 - half
            gop_target_pct = (gop / total) * 100.0 + half

        # Clamp to [0, 100] while respecting that Other stays fixed
        other_pct = (other / total) * 100.0

        # Dem + GOP must equal (100 - Other%)
        two_party_pct_total = 100.0 - other_pct

        # Clamp Dem% and GOP% within feasible range
        if dem_target_pct < 0.0:
            dem_target_pct = 0.0
        if gop_target_pct < 0.0:
            gop_target_pct = 0.0

        # Renormalize Dem/GOP to sum to two_party_pct_total (in case of clamping)
        sum_two = dem_target_pct + gop_target_pct
        if sum_two <= 0:
            # fallback: split evenly
            dem_target_pct = two_party_pct_total / 2.0
            gop_target_pct = two_party_pct_total / 2.0
        else:
            scale = two_party_pct_total / sum_two
            dem_target_pct *= scale
            gop_target_pct *= scale

        # Convert target percents back to votes
        new_dem = int(round((dem_target_pct / 100.0) * total))
        new_gop = int(round((gop_target_pct / 100.0) * total))

        # Keep other votes exactly the same; fix rounding drift by adjusting GOP
        new_other = other
        # Ensure totals match exactly
        drift = total - (new_dem + new_gop + new_other)
        new_gop += drift

        if new_dem < 0:
            new_dem = 0
        if new_gop < 0:
            new_gop = 0

        self._results["Democratic"] = new_dem
        self._results["Republican"] = new_gop
        self._results["Other"] = new_other

        self.determine_winner()

    def apply_margin_shift(self):
        """
        Placeholder kept from your original file.
        You can remove later, but keeping it for parity.
        """
        pass

    # -------------------------
    # Helpers
    # -------------------------

    @staticmethod
    def _normalize_results(results):
        """
        Ensure expected keys exist and values are non-negative ints.
        """
        normalized = {}
        normalized["Democratic"] = int(results.get("Democratic", 0) or 0)
        normalized["Republican"] = int(results.get("Republican", 0) or 0)
        normalized[OTHER_PARTY] = int(results.get(OTHER_PARTY, 0) or 0)

        # Clamp negatives
        for k in list(normalized.keys()):
            if normalized[k] < 0:
                normalized[k] = 0

        # Preserve any extra parties if present (optional)
        for k, v in results.items():
            if k not in normalized:
                vv = int(v or 0)
                normalized[k] = 0 if vv < 0 else vv

        return normalized

    def __str__(self):
        return self._name + " " + str(self._ev) + " EV"
