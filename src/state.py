"""
State class

Represents a single state (or ME/NE congressional district) in a presidential election.
Stores both baseline and simulated vote results, tracks the winner, and supports
vote shift and margin swing operations for simulation purposes.
"""

OTHER_PARTY = "Other"
TIED = "TIED"


class State:
    def __init__(self, name, ev, unit_type="statewide", parent_state=None):
        # Core identity fields
        self._name = name
        self._ev = ev
        self._unit_type = unit_type          # "statewide" or "district"
        self._parent_state = parent_state    # "ME", "NE", or None for regular states

        # Baseline is the original loaded results; results is the current simulated state
        self._base_results = {}
        self._results = {}
        self._winner = None

    # -------------------------
    # Getters and setters
    # -------------------------

    def get_name(self):
        # Returns the state or district name (e.g. "Pennsylvania" or "ME-1")
        return self._name

    def set_name(self, name):
        # Overrides the display name; use carefully as it may break lookups
        self._name = name

    def get_ev(self):
        # Returns the number of Electoral College votes for this state/district
        return self._ev

    def set_ev(self, new_ev):
        # Updates the EV count; used if EV reapportionment is needed
        self._ev = new_ev

    def get_results(self):
        """Current simulated results dict."""
        return self._results

    def get_base_results(self):
        """Baseline results dict (original loaded results, never modified by swings)."""
        return self._base_results

    def set_results(self, p_results):
        """
        Set baseline + current results from input dict.
        Stores a baseline copy on first call; subsequent calls only update current results.

        Expected keys: 'Democratic', 'Republican', and optionally 'Other'.
        """
        normalized = self._normalize_results(p_results)

        # Only set baseline once — on initial data load
        if not self._base_results:
            self._base_results = normalized.copy()

        # Always update current simulated results
        self._results = normalized.copy()
        self.determine_winner()

    def set_base_results(self, p_results):
        """
        Explicitly overwrites the baseline and resets current results to match.
        Used when replacing loaded data entirely.
        """
        normalized = self._normalize_results(p_results)
        self._base_results = normalized.copy()
        self._results = normalized.copy()
        self.determine_winner()

    def reset_results(self):
        """Resets current simulated results back to the original baseline."""
        self._results = self._base_results.copy()
        self.determine_winner()

    def get_parent_state(self):
        # Returns the two-letter parent state code for districts (e.g. "ME"), or None for regular states
        return self._parent_state

    # -------------------------
    # Winner logic
    # -------------------------

    def determine_winner(self):
        # Compares Democratic vs Republican vote totals to set the winner; ties become TIED
        dem_vote = int(self._results.get("Democratic", 0) or 0)
        gop_vote = int(self._results.get("Republican", 0) or 0)

        if dem_vote > gop_vote:
            self._winner = "Democratic"
        elif gop_vote > dem_vote:
            self._winner = "Republican"
        else:
            self._winner = TIED

    def get_winner(self):
        # Returns the current winner string: "Democratic", "Republican", or "TIED"
        return self._winner

    def set_winner(self, p_winner):
        # Manually overrides the winner; normally set automatically by determine_winner()
        self._winner = p_winner

    # -------------------------
    # Vote accessors
    # -------------------------

    def get_total_vote(self):
        # Returns the sum of all party votes in the current simulated results
        return int(sum(self._results.values()))

    def get_vote_by_party(self, party):
        # Returns the raw vote count for the given party from current results
        return int(self._results.get(party, 0) or 0)

    def get_vote_per_by_party(self, party):
        # Returns the given party's share of the total vote as a percentage (0–100)
        total = self.get_total_vote()
        if total <= 0:
            return 0.0
        return (self.get_vote_by_party(party) / total) * 100.0

    def get_margin(self):
        """
        Returns (winner, margin_percent) using current results.
        Margin is computed as (winner% - opposing_major_party%); returns (TIED, 0.0) if tied.
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
    # Static helpers
    # -------------------------

    @staticmethod
    def get_other_party(o_party):
        # Returns the opposing major party; returns None for TIED or unknown inputs
        if o_party == "Democratic":
            return "Republican"
        if o_party == "Republican":
            return "Democratic"
        return None

    # -------------------------
    # Simulation operations
    # -------------------------

    def apply_vote_shift(self, party, shift_votes):
        """
        Adds votes to one party only (turnout boost); total vote count increases.
        Updates the winner after applying the shift.
        """
        shift_votes = int(shift_votes)

        if shift_votes == 0:
            return

        # Copy results to avoid mutating external references
        new_results = self._results.copy()
        new_results[party] = int(new_results.get(party, 0) or 0) + shift_votes

        # Clamp to zero in case a negative shift_votes was passed
        if new_results[party] < 0:
            new_results[party] = 0

        self._results = self._normalize_results(new_results)
        self.determine_winner()

    def apply_margin_shift_to_party(self, target_party, swing_points):
        """
        Swings the two-party split by swing_points percentage points toward target_party.
        Adds +X/2 to target and subtracts -X/2 from opponent, keeping Other votes fixed.

        Example: 48D 49R 3O, swing D+5 => 50.5D 46.5R 3O
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

        # Compute shifted percentages — half the swing added/removed from each side
        half = float(swing_points) / 2.0
        if target_party == "Democratic":
            dem_target_pct = (dem / total) * 100.0 + half
            gop_target_pct = (gop / total) * 100.0 - half
        else:
            dem_target_pct = (dem / total) * 100.0 - half
            gop_target_pct = (gop / total) * 100.0 + half

        # Other share stays fixed; Dem + GOP must fill the remaining percentage
        other_pct = (other / total) * 100.0
        two_party_pct_total = 100.0 - other_pct

        # Clamp to zero before renormalizing to prevent negative vote shares
        if dem_target_pct < 0.0:
            dem_target_pct = 0.0
        if gop_target_pct < 0.0:
            gop_target_pct = 0.0

        # Rescale Dem/GOP so they sum to the available two-party share
        sum_two = dem_target_pct + gop_target_pct
        if sum_two <= 0:
            dem_target_pct = two_party_pct_total / 2.0
            gop_target_pct = two_party_pct_total / 2.0
        else:
            scale = two_party_pct_total / sum_two
            dem_target_pct *= scale
            gop_target_pct *= scale

        # Convert percentages back to integer vote counts
        new_dem = int(round((dem_target_pct / 100.0) * total))
        new_gop = int(round((gop_target_pct / 100.0) * total))
        new_other = other

        # Fix rounding drift so vote totals remain exactly equal to original total
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
        """Placeholder kept for API parity; not implemented."""
        pass

    # -------------------------
    # Helpers
    # -------------------------

    @staticmethod
    def _normalize_results(results):
        """
        Ensures all expected party keys exist with non-negative integer values.
        Preserves any extra party keys found in the input dict.
        """
        normalized = {}
        normalized["Democratic"] = int(results.get("Democratic", 0) or 0)
        normalized["Republican"] = int(results.get("Republican", 0) or 0)
        normalized[OTHER_PARTY] = int(results.get(OTHER_PARTY, 0) or 0)

        # Clamp any negatives to zero
        for k in list(normalized.keys()):
            if normalized[k] < 0:
                normalized[k] = 0

        # Carry over any additional party keys not in the standard set
        for k, v in results.items():
            if k not in normalized:
                vv = int(v or 0)
                normalized[k] = 0 if vv < 0 else vv

        return normalized

    # -------------------------
    # Debug / display
    # -------------------------

    def print_summary(self):
        # Prints baseline, current results, and winner to stdout for debugging
        print(self)
        print("BASE:", self._base_results)
        print("CURR:", self._results)
        print("WINNER:", self._winner)

    def print_result(self):
        # Prints current simulated results dict to stdout
        print(self._results)

    def __str__(self):
        return self._name + " " + str(self._ev) + " EV"
