"""
Election class

Manages a full presidential election cycle. Loads state-level results from CSV,
aggregates Electoral College and popular vote totals, and provides simulation
methods for applying national vote swings and turnout boosts.
"""

from pathlib import Path
import json
import pandas as pd
import re
import plotly.express as px
import plotly.graph_objects as go

from src.model.state import State
from src.model.constants import us_state_to_abbrev, DEM, GOP, OTHER, TIED

# Default directory for canonical election CSV files (data/YEAR.csv)
DATA_DIR = Path(__file__).parent.parent.parent / "data"


class Election:
    # Presidential elections occur every 4 years starting in 1788
    _VALID_YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")

    @staticmethod
    def _validate_presidential_year(year_int):
        # Raises ValueError if the year is not a valid U.S. presidential election year
        if year_int % 4 != 0 or not (1788 <= year_int <= 2100):
            raise ValueError(
                f"{year_int} is not a valid U.S. presidential election year. "
                "Must be divisible by 4 and between 1788 and 2100."
            )

    def __init__(self, year_or_path, label=None):
        """
        Args:
            year_or_path: A 4-digit year string ("2024") or a path to any CSV file
                          ("scenarios/2024_D+5.csv"). Year strings load from data/.
            label:        Optional display label for visualizations (year toggle buttons,
                          titles). Defaults to year string or CSV filename stem.
        """
        self.states = []

        p = Path(str(year_or_path))
        if p.suffix.lower() == ".csv":
            # Path-based load: extract the election year from the filename via regex
            self._data_path = p
            match = self._VALID_YEAR_RE.search(p.stem)
            if not match:
                raise ValueError(
                    f"Cannot determine election year from filename '{p.name}'. "
                    "Filename must contain a year like 2020 or 2024 (e.g. 2024_D+5.csv)."
                )
            year_int = int(match.group(1))
            self._validate_presidential_year(year_int)
            self.year = str(year_int)
            self.label = label or p.stem          # e.g. "2024_D+5"
        else:
            # Year-string load: cast directly and validate
            try:
                year_int = int(year_or_path)
            except (ValueError, TypeError):
                raise ValueError(
                    f"'{year_or_path}' is not a valid year or CSV path. "
                    "Pass a 4-digit year (e.g. '2024') or a path ending in .csv."
                )
            self._validate_presidential_year(year_int)
            self._data_path = DATA_DIR / f"{year_or_path}.csv"
            self.year = str(year_int)
            self.label = label or self.year       # e.g. "2024"

        # results dict structure:
        #   results["Democratic"] = (total_votes, total_ev)
        #   results["Republican"] = (total_votes, total_ev)
        #   results["Other"]      = total_other_votes
        #   results["TossupEV"]   = total_tossup_ev
        self.results = {}

        self.min_ev_needed = 270   # Electoral College majority threshold
        self.total_vote = 0
        self.winner = None
        self.df = None

        # Load CSV and populate self.states on instantiation
        self.read_election_data()

    # -------------------------
    # Data load / reset
    # -------------------------

    def read_election_data(self):
        """
        Reads the election CSV, validates required columns, and builds State objects.
        Districts (e.g. ME-1, NE-2) are detected by a hyphen in the state name.
        """
        if not self._data_path.exists():
            raise FileNotFoundError(f"Election data not found: {self._data_path}")

        # Validate that all required columns are present before parsing rows
        required_cols = {"State", "EV", DEM, GOP, OTHER}
        self.df = pd.read_csv(self._data_path)
        missing = required_cols - set(self.df.columns)
        if missing:
            raise ValueError(f"CSV missing required columns: {missing}")

        self.states = []
        for _, row in self.df.iterrows():
            name = row["State"]
            ev = int(row["EV"])

            # Detect congressional districts by the hyphen convention (e.g. "ME-1")
            unit_type = "district" if "-" in name else "statewide"
            parent_state = None

            if unit_type == "district":
                # Extract the two-letter parent state abbreviation from the district name
                parent_state = name.split("-")[0]   # "ME" or "NE"

            s1 = State(name, ev, unit_type=unit_type, parent_state=parent_state)

            # Coerce vote values to int, safely handling NaN or missing values
            dem = int(row.get(DEM, 0) or 0)
            gop = int(row.get(GOP, 0) or 0)
            other = int(row.get(OTHER, 0) or 0)

            s1.set_results({DEM: dem, GOP: gop, OTHER: other})
            self.states.append(s1)

        # Compute initial EV totals and popular vote winner from loaded data
        self.determine_winner()

    def reset_all_states(self):
        """Resets all states back to their original baseline results and recomputes totals."""
        for state in self.states:
            state.reset_results()
        self.determine_winner()

    # -------------------------
    # Election summary
    # -------------------------

    def determine_winner(self):
        """
        Aggregates EV and popular vote totals across all states and sets self.results.
        Note: self.winner reflects the popular vote winner, which may differ from the EC winner.
        """
        TOSSUP = "Tossup"

        dem_votes = 0
        gop_votes = 0
        dem_ev = 0
        gop_ev = 0
        tossup_ev = 0

        self.total_vote = 0

        for state in self.states:
            results = state.get_results()
            winner = state.get_winner()

            # Assign each state's EVs to the winning party or tossup bucket
            if winner == DEM:
                dem_ev += state.get_ev()
            elif winner == GOP:
                gop_ev += state.get_ev()
            elif winner in (TOSSUP, TIED):
                tossup_ev += state.get_ev()
            else:
                # Unrecognized winner label; treat as tossup
                tossup_ev += state.get_ev()

            # Accumulate national popular vote totals from statewide rows only.
            # District rows (ME-1, NE-2, etc.) are subsets of their parent statewide
            # row — counting both would double-count Maine and Nebraska votes.
            if state.get_parent_state() is None:
                dem_votes += int(results.get(DEM, 0) or 0)
                gop_votes += int(results.get(GOP, 0) or 0)
                self.total_vote += state.get_total_vote()

        # Determine popular vote winner (may differ from Electoral College winner)
        if dem_votes > gop_votes:
            self.winner = DEM
        elif gop_votes > dem_votes:
            self.winner = GOP
        else:
            self.winner = TIED

        # Store aggregated results for both parties and tossup EVs
        self.results[DEM] = (dem_votes, dem_ev)
        self.results[GOP] = (gop_votes, gop_ev)
        self.results[OTHER] = self.total_vote - (dem_votes + gop_votes)
        self.results["TossupEV"] = tossup_ev

    def get_total_votes(self):
        # Returns the total number of votes cast across all states in the current simulation
        return self.total_vote

    def print_summary(self):
        # Prints popular vote winner, party totals, and tossup EVs to stdout
        print(self.winner, " won the election (popular vote)")
        print("Dem:", self.results.get(DEM))
        print("GOP:", self.results.get(GOP))
        print("TossupEV:", self.results.get("TossupEV"))

    # -------------------------
    # Export
    # -------------------------

    def export_scenario(self, output_file="scenario.csv"):
        """
        Exports the current simulated state of all states to CSV or JSON.
        Output schema mirrors data/YEAR.csv; JSON output is a list of row objects.
        File format is auto-detected from the file extension (.csv or .json).
        """
        # Create output directory if it doesn't already exist
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        # Build one row per state/district from current simulated results
        rows = [
            {
                "State":       st.get_name(),
                "EV":          st.get_ev(),
                DEM:   int(st.get_results().get(DEM, 0)),
                GOP:   int(st.get_results().get(GOP, 0)),
                OTHER: int(st.get_results().get(OTHER, 0)),
            }
            for st in self.states
        ]

        # Write JSON or CSV based on the output file extension
        if output_file.endswith(".json"):
            with open(output_file, "w") as f:
                json.dump(rows, f, indent=2)
        else:
            pd.DataFrame(rows).to_csv(output_file, index=False)

        print(f"Scenario exported → {output_file}")

    # -------------------------
    # Sorting / lookup
    # -------------------------

    def sort_alphabetically(self):
        # Sorts self.states in place by state name alphabetically
        self.states.sort(key=lambda x: x.get_name())

    def sort_by_state_margins(self):
        """
        Sorts states by current margin: winner states descending, then loser states ascending.
        Used internally by get_tipping_point_state to identify the closest winning states.
        """
        win_party = self.winner
        other_party = State.get_other_party(win_party)

        # Separate states by which party won, then sort each group by margin
        winner_list = [s for s in self.states if s.get_winner() == win_party]
        winner_list.sort(key=lambda x: x.get_margin()[1])

        other_list = [s for s in self.states if s.get_winner() == other_party]
        other_list.sort(key=lambda x: x.get_margin()[1])

        # Winner states largest margin first, followed by loser states smallest first
        self.states = winner_list[::-1] + other_list

    def find_state_by_name(self, state_name):
        # Returns the State object matching the given name, or None if not found
        for state in self.states:
            if state.get_name() == state_name:
                return state
        return None

    def get_result_of_state_name(self, state_name):
        # Returns the current results dict for the named state, or None if not found
        s = self.find_state_by_name(state_name)
        if not s:
            print("State " + state_name + " not found")
            return None
        return s.get_results()

    # -------------------------
    # Simulation operations
    # -------------------------

    def apply_vote_boost_all_states(self, party, votes):
        """
        Adds a flat vote count to one party in every statewide state (turnout boost).
        Skips congressional districts (ME/NE splits).
        """
        for state in self.states:
            if state.get_parent_state() is not None:
                continue
            state.apply_vote_shift(party, votes)
        self.determine_winner()

    def apply_margin_swing_all_states(self, target_party, swing_points):
        """
        Swings every state's two-party split toward target_party by swing_points percentage points.
        Includes ME/NE congressional districts.
        """
        for state in self.states:
            state.apply_margin_shift_to_party(target_party, swing_points)
        self.determine_winner()

    def apply_margin_swing_to_state(self, state_name, target_party, swing_points):
        # Applies a margin swing to a single named state; skips ME/NE district rows
        st = self.find_state_by_name(state_name)
        if not st:
            return
        if st.get_parent_state() is not None:
            print("Phase 1: ME/NE split states not supported for swing yet.")
            return
        st.apply_margin_shift_to_party(target_party, swing_points)
        self.determine_winner()

    def apply_vote_boost_to_state(self, state_name, party, votes):
        # Applies a vote boost to a single named state; skips ME/NE district rows
        st = self.find_state_by_name(state_name)
        if not st:
            return
        if st.get_parent_state() is not None:
            print("Phase 1: ME/NE split states not supported for boosts yet.")
            return
        st.apply_vote_shift(party, votes)
        self.determine_winner()

    # -------------------------
    # Analytics
    # -------------------------

    def get_popular_vote_margin(self):
        """
        Returns (winning_party, margin_percent) for the popular vote winner.
        Margin is expressed as a percentage of total votes cast.
        """
        win_party = self.winner
        loser_party = State.get_other_party(win_party)
        if loser_party is None:
            return (win_party, 0.0)

        total = float(self.get_total_votes() or 0)
        if total <= 0:
            return (win_party, 0.0)

        margin = (self.results[win_party][0] - self.results[loser_party][0]) * 100.0 / total
        return (win_party, margin)

    def get_relative_to_pv_margin(self, m_state):
        """
        Returns (party, margin) representing how a given state's margin compares to the
        national popular vote margin — used to compute Electoral College bias.
        """
        win_party, win_margin = self.get_popular_vote_margin()
        m_party, m_margin = m_state.get_margin()

        other_party = State.get_other_party(win_party)
        if other_party is None:
            return (win_party, abs(win_margin))

        # Treat tossup/tied states as a zero-margin win for the popular vote winner
        if m_party in ("Tossup", "TIED"):
            m_party = win_party
            m_margin = 0.0

        rel_party = ""
        rel_margin = 0.0

        if win_party == m_party:
            # State leans same direction as national; EC bias is the difference
            rel_margin = win_margin - m_margin
            rel_party = win_party if rel_margin < 0.0 else other_party
        else:
            # State leans opposite direction; add margins to compute total EC bias
            rel_margin = win_margin + m_margin
            rel_party = other_party

        return (rel_party, abs(rel_margin))

    def get_tipping_point_state(self):
        """
        Returns the tipping point state — the EC winner's state that, when removed,
        would drop them below 270 EVs. States are sorted safest-to-closest.
        """
        # Determine EC winner from EV totals (may differ from popular vote winner)
        dem_ev = self.results.get(DEM, (0, 0))[1]
        gop_ev = self.results.get(GOP, (0, 0))[1]
        if dem_ev >= self.min_ev_needed:
            ec_winner = DEM
        elif gop_ev >= self.min_ev_needed:
            ec_winner = GOP
        else:
            return None  # 269-269 tie or no majority — no tipping point exists

        # Walk winner's states from safest to closest, accumulate EVs until 270 is reached
        winner_states = sorted(
            [s for s in self.states if s.get_winner() == ec_winner],
            key=lambda s: s.get_margin()[1],
            reverse=True,
        )
        ev_count = 0
        for state in winner_states:
            ev_count += state.get_ev()
            if ev_count >= self.min_ev_needed:
                return state
        return None

    def get_ec_bias(self):
        # Returns (party, margin) showing how much the EC favors one party over the popular vote
        tp = self.get_tipping_point_state()
        if not tp:
            return ("TIED", 0.0)
        return self.get_relative_to_pv_margin(tp)

    def get_states_as_list(self):
        # Returns the full list of State objects (statewide + districts)
        return self.states

    def get_states_won_by_party(self, party):
        # Returns a filtered list of states won by the given party
        return [state for state in self.states if state.get_winner() == party]

    @classmethod
    def combine_party_results(cls, election_a, party_a, election_b, party_b, label=None):
        """
        Creates a synthetic Election combining party_a votes from election_a
        with party_b votes from election_b. Other votes are set to 0 (pure 2-party race).

        The Democratic slot always receives party_a votes; the Republican slot receives
        party_b votes. Only states present in both elections are included.

        Example:
            synthetic = Election.combine_party_results(e2020, DEM, e2024, GOP,
                                                       label="2020 Dem vs 2024 GOP")
        """
        b_lookup = {s.get_name(): s for s in election_b.states}

        states = []
        for state_a in election_a.states:
            name = state_a.get_name()
            state_b = b_lookup.get(name)
            if state_b is None:
                continue
            dem_votes = state_a.get_vote_by_party(party_a)
            gop_votes = state_b.get_vote_by_party(party_b)
            s = State(name, state_a.get_ev(),
                      unit_type=state_a._unit_type,
                      parent_state=state_a.get_parent_state())
            s.set_results({DEM: dem_votes, GOP: gop_votes, OTHER: 0})
            states.append(s)

        inst = cls.__new__(cls)
        inst.states = states
        inst.results = {}
        inst.min_ev_needed = 270
        inst.total_vote = 0
        inst.winner = None
        inst.df = None
        inst.year = election_a.year
        inst._data_path = None
        inst.label = label or f"{election_a.label} {party_a[:3]} vs {election_b.label} {party_b[:3]}"
        inst.determine_winner()
        return inst

    # -------------------------
    # Visualization helpers
    # -------------------------

    def is_split_ev_unit(self, state):
        """
        Returns True for Maine, Nebraska, and their congressional district rows.
        These are blocked from individual swings/boosts in Phase 1.
        """
        name = state.get_name()
        return name in ("Maine", "Nebraska") or name.startswith("ME-") or name.startswith("NE-")

    def visualize(self, output_file="election_results_map.html"):
        """
        Generates a static choropleth map of the current election state and writes it to HTML.
        Uses Plotly Express for straightforward party-color rendering.
        """
        # Build a summary row per state for the choropleth data source
        state_summary = []
        for state in self.states:
            winner = state.get_winner()
            state_summary.append(
                {
                    "State": state.get_name(),
                    "Winner": winner,
                    "Votes": state.get_vote_by_party(winner) if winner not in ("Tossup", "TIED") else 0,
                    "EV": state.get_ev(),
                    "Margin": round(state.get_margin()[1], 2),
                }
            )

        df = pd.DataFrame(state_summary)
        # Map state names to two-letter abbreviations required by Plotly's USA-states mode
        df["State Abbr"] = df["State"].map(us_state_to_abbrev)

        color_map = {
            "Democratic": "blue",
            "Republican": "red",
            "Tossup": "gray",
            "TIED": "gray",
        }

        dem_ev = self.results[DEM][1]
        gop_ev = self.results[GOP][1]
        tossup_ev = self.results.get("TossupEV", 0)

        fig = px.choropleth(
            df,
            locations="State Abbr",
            locationmode="USA-states",
            color="Winner",
            color_discrete_map=color_map,
            hover_name="State",
            hover_data={
                "Winner": True,
                "EV": True,
                "Margin": True,
                "Votes": ":,",
                "State Abbr": False,
            },
            scope="usa",
            title=f"{self.year} US Election Results | Dem {dem_ev} - GOP {gop_ev} - Tossup {tossup_ev}",
        )

        fig.update_layout(
            geo=dict(lakecolor="rgb(255, 255, 255)"),
        )

        fig.show()
        fig.write_html(output_file)

    def visualize_with_margin_slider(
        self,
        output_file="election_results_map_with_margin.html",
        min_shift=-10,
        max_shift=10,
        step=1
    ):
        """
        Creates an interactive map with a national margin shift slider (single year).
        Positive shift swings toward Democrats, negative toward Republicans.
        Writes a standalone HTML file.
        """

        def build_frame_df(election_obj):
            # Builds a DataFrame of statewide results, filtering out unmapped state names
            rows = []
            for st in election_obj.states:
                winner = st.get_winner()
                party, margin = st.get_margin()

                rows.append({
                    "State": st.get_name(),
                    "State Abbr": us_state_to_abbrev.get(st.get_name()),
                    "Winner": winner,
                    "EV": st.get_ev(),
                    "Margin": round(margin, 2),
                    "Votes": st.get_vote_by_party(winner) if winner not in ("Tossup", "TIED") else 0
                })

            df = pd.DataFrame(rows)
            # Drop rows without a valid state abbreviation (e.g. district rows)
            df = df[df["State Abbr"].notna()]
            return df

        def winner_to_code(w):
            # Converts winner string to a numeric z-value for choropleth coloring (-1/0/1)
            if w == "Democratic":
                return -1
            if w == "Republican":
                return 1
            return 0  # Tossup / TIED

        shifts = list(range(min_shift, max_shift + 1, step))

        frames = []
        base_title = f"{self.year} US Election Results — Margin Shift: "

        for s in shifts:
            # Reset to baseline before applying each shift to ensure clean frames
            self.reset_all_states()

            # Apply the appropriate directional swing for this slider step
            if s > 0:
                self.apply_margin_swing_all_states(DEM, abs(s))
            elif s < 0:
                self.apply_margin_swing_all_states(GOP, abs(s))
            else:
                self.determine_winner()

            df = build_frame_df(self)
            z = df["Winner"].apply(winner_to_code)

            dem_ev = self.results[DEM][1]
            gop_ev = self.results[GOP][1]
            tossup_ev = self.results.get("TossupEV", 0)

            pv_party, pv_margin = self.get_popular_vote_margin()
            pv_label = f"{pv_party[:3]} +{pv_margin:.1f}%"

            # Build one Plotly frame per shift step with updated map data and title
            frames.append(
                go.Frame(
                    name=str(s),
                    data=[
                        go.Choropleth(
                            locations=df["State Abbr"],
                            z=z,
                            locationmode="USA-states",
                            zmin=-1,
                            zmax=1,
                            colorscale=[[0, "blue"], [0.5, "gray"], [1, "red"]],
                            showscale=False,
                            customdata=df[["Winner", "EV", "Margin", "Votes"]].values,
                            hovertemplate=(
                                "<b>%{location}</b><br>"
                                "Winner: %{customdata[0]}<br>"
                                "EV: %{customdata[1]}<br>"
                                "Margin: %{customdata[2]}%<br>"
                                "Votes: %{customdata[3]:,}"
                                "<extra></extra>"
                            ),
                        )
                    ],
                    layout=go.Layout(
                        title_text=f"{base_title}{s} | Dem {dem_ev} - GOP {gop_ev} - Tossup {tossup_ev} | PV: {pv_label}"
                    ),
                )
            )

        # Default the figure to the zero-shift (baseline) frame
        start_shift = 0 if 0 in shifts else shifts[len(shifts) // 2]
        start_frame = next(f for f in frames if f.name == str(start_shift))

        fig = go.Figure(
            data=start_frame.data,
            frames=frames,
            layout=go.Layout(
                title_text=start_frame.layout.title.text,
                geo=dict(scope="usa"),
                updatemenus=[
                    {
                        "type": "buttons",
                        "showactive": False,
                        "x": 0.02,
                        "y": 0.95,
                        "buttons": [
                            {
                                "label": "Play",
                                "method": "animate",
                                "args": [
                                    None,
                                    {
                                        "frame": {"duration": 500, "redraw": True},
                                        "fromcurrent": True,
                                        "transition": {"duration": 0},
                                    },
                                ],
                            }
                        ],
                    }
                ],
                sliders=[
                    {
                        "active": shifts.index(start_shift),
                        "currentvalue": {"prefix": "Margin Shift: "},
                        "pad": {"t": 50},
                        "steps": [
                            {
                                "label": str(s),
                                "method": "animate",
                                "args": [
                                    [str(s)],
                                    {
                                        "frame": {"duration": 0, "redraw": True},
                                        "mode": "immediate",
                                        "transition": {"duration": 0},
                                    },
                                ],
                            }
                            for s in shifts
                        ],
                    }
                ],
            ),
        )

        fig.show()
        fig.write_html(output_file)

        # Always restore baseline after generating all slider frames
        self.reset_all_states()
