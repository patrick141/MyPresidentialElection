"""
Election class file (updated to match new State class)

- Uses snake_case State methods
- Supports baseline/current results stored inside State
- Supports:
  1) vote boost (adds votes to one party only)
  2) margin swing (moves votes between Dem/GOP toward a party)
"""

from pathlib import Path
import pandas as pd
import re
import plotly.express as px
import plotly.graph_objects as go

from src.state import State
from src.constants import us_state_to_abbrev

DATA_DIR = Path(__file__).parent.parent / "data"


class Election:
    def __init__(self, year):
        self.states = []
        self.year = year

        # results summary:
        # self.results["Democratic"] = (total_votes, total_ev)
        # self.results["Republican"] = (total_votes, total_ev)
        # self.results["Other"] = total_other_votes
        # self.results["TossupEV"] = total_tossup_ev (optional)
        self.results = {}

        self.min_ev_needed = 270
        self.total_vote = 0
        self.winner = None
        self.df = None

        self.read_election_data(year)

    # -------------------------
    # Data load / reset
    # -------------------------

    def read_election_data(self, year):
        self.df = pd.read_csv(DATA_DIR / f"{year}.csv")

        self.states = []
        for _, row in self.df.iterrows():
            name = row["State"]
            ev = int(row["EV"])

            unit_type = "district" if "-" in name else "statewide"
            parent_state = None

            if unit_type == "district":
                parent_state = name.split("-")[0]   # "ME" or "NE"

            s1 = State(name, ev, unit_type=unit_type, parent_state=parent_state)

            # Safely coerce vote values to ints (handles NaN/float)
            dem = int(row.get("Democratic", 0) or 0)
            gop = int(row.get("Republican", 0) or 0)
            other = int(row.get("Other", 0) or 0)

            s1.set_results({"Democratic": dem, "Republican": gop, "Other": other})
            self.states.append(s1)

        self.determine_winner()

    def reset_all_states(self):
        """Reset all states back to baseline results."""
        for state in self.states:
            state.reset_results()
        self.determine_winner()

    # -------------------------
    # Election summary
    # -------------------------

    def determine_winner(self):
        DEM = "Democratic"
        GOP = "Republican"
        OTHER = "Other"
        TOSSUP = "Tossup"
        TIED = "TIED"

        dem_votes = 0
        gop_votes = 0
        dem_ev = 0
        gop_ev = 0
        tossup_ev = 0

        self.total_vote = 0

        for state in self.states:

            results = state.get_results()
            winner = state.get_winner()

            # EV allocation
            if winner == DEM:
                dem_ev += state.get_ev()
            elif winner == GOP:
                gop_ev += state.get_ev()
            elif winner == TOSSUP or winner == TIED:
                tossup_ev += state.get_ev()
            else:
                # unknown label: treat as tossup
                tossup_ev += state.get_ev()

            # Popular vote totals (from CURRENT results)
            dem_votes += int(results.get(DEM, 0) or 0)
            gop_votes += int(results.get(GOP, 0) or 0)
            self.total_vote += state.get_total_vote()

        # Winner by popular vote (optional; EC winner could differ)
        if dem_votes > gop_votes:
            self.winner = DEM
        elif gop_votes > dem_votes:
            self.winner = GOP
        else:
            self.winner = TIED

        self.results[DEM] = (dem_votes, dem_ev)
        self.results[GOP] = (gop_votes, gop_ev)
        self.results[OTHER] = self.total_vote - (dem_votes + gop_votes)
        self.results["TossupEV"] = tossup_ev

    def get_total_votes(self):
        return self.total_vote

    def print_summary(self):
        print(self.winner, " won the election (popular vote)")
        print("Dem:", self.results.get("Democratic"))
        print("GOP:", self.results.get("Republican"))
        print("TossupEV:", self.results.get("TossupEV"))

    # -------------------------
    # Sorting / lookup
    # -------------------------

    def sort_alphabetically(self):
        self.states.sort(key=lambda x: x.get_name())

    def sort_by_state_margins(self):
        """
        Sorts by current margin:
        - winner states by decreasing margin
        - then loser states by increasing margin
        Note: Tossup/TIED states may behave oddly; you can customize later.
        """
        win_party = self.winner
        other_party = State.get_other_party(win_party)

        winner_list = [s for s in self.states if s.get_winner() == win_party]
        winner_list.sort(key=lambda x: x.get_margin()[1])

        other_list = [s for s in self.states if s.get_winner() == other_party]
        other_list.sort(key=lambda x: x.get_margin()[1])

        self.states = winner_list[::-1] + other_list

    def find_state_by_name(self, state_name):
        for state in self.states:
            if state.get_name() == state_name:
                return state
        return None

    def get_result_of_state_name(self, state_name):
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
        Adds votes to one party in every state (turnout boost).
        """
        for state in self.states:
            if state.get_parent_state() is not None:
                continue
            state.apply_vote_shift(party, votes)
        self.determine_winner()

    def apply_margin_swing_all_states(self, target_party, swing_points):
        """
        Swings each state's two-party results toward target_party by swing_points.
        swing_points is percentage points of two-party total.
        """
        for state in self.states:
            if state.get_parent_state() is not None:
                continue  # Block ME/NE split states in Phase 1
            state.apply_margin_shift_to_party(target_party, swing_points)
        self.determine_winner()

    def apply_margin_swing_to_state(self, state_name, target_party, swing_points):
        st = self.find_state_by_name(state_name)
        if not st:
            return
        if st.get_parent_state() is not None:
            print("Phase 1: ME/NE split states not supported for swing yet.")
            return
        st.apply_margin_shift_to_party(target_party, swing_points)
        self.determine_winner()

    def apply_vote_boost_to_state(self, state_name, party, votes):
        st = self.find_state_by_name(state_name)
        if not st:
            return
        if st.get_parent_state() is not None:
            print("Phase 1: ME/NE split states not supported for boosts yet.")
            return
        st.apply_vote_shift(party, votes)
        self.determine_winner()

    # -------------------------
    # Analytics (kept from your original, updated calls)
    # -------------------------

    def get_popular_vote_margin(self):
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
        win_party, win_margin = self.get_popular_vote_margin()
        m_party, m_margin = m_state.get_margin()

        other_party = State.get_other_party(win_party)
        if other_party is None:
            return (win_party, abs(win_margin))

        # if the state is tossup/tied, treat margin as 0
        if m_party == "Tossup" or m_party == "TIED":
            m_party = win_party
            m_margin = 0.0

        rel_party = ""
        rel_margin = 0.0

        if win_party == m_party:
            rel_margin = win_margin - m_margin
            rel_party = win_party if rel_margin < 0.0 else other_party
        else:
            rel_margin = win_margin + m_margin
            rel_party = other_party

        return (rel_party, abs(rel_margin))

    def get_tipping_point_state(self):
        self.sort_by_state_margins()
        ev_count = 0
        for state in self.states:
            ev_count += state.get_ev()
            if ev_count > self.min_ev_needed:
                return state
        return None

    def get_ec_bias(self):
        tp = self.get_tipping_point_state()
        if not tp:
            return ("TIED", 0.0)
        return self.get_relative_to_pv_margin(tp)

    def get_states_as_list(self):
        return self.states

    def get_states_won_by_party(self, party):
        return [state for state in self.states if state.get_winner() == party]

    # -------------------------
    # Visualization (same as before, updated for snake_case + tossup)
    # -------------------------

    def is_split_ev_unit(self, state):
        """
        Returns True for Maine/Nebraska and their district rows.
        We block applying swings/boosts to these in Phase 1.
        """
        name = state.get_name()
        return name in ("Maine", "Nebraska") or name.startswith("ME-") or name.startswith("NE-")

    def visualize(self, output_file="election_results_map.html"):
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
        df["State Abbr"] = df["State"].map(us_state_to_abbrev)

        color_map = {
            "Democratic": "blue",
            "Republican": "red",
            "Tossup": "gray",
            "TIED": "gray",
        }

        dem_ev = self.results["Democratic"][1]
        gop_ev = self.results["Republican"][1]
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
        Creates an interactive map with a national margin shift slider.
        Positive shift swings toward Democrats, negative toward Republicans.
        Writes a standalone HTML file.
        """

        # --- helpers ---
        def build_frame_df(election_obj):
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
            # drop anything that doesn't map (safety)
            df = df[df["State Abbr"].notna()]
            return df

        def winner_to_code(w):
            if w == "Democratic":
                return -1
            if w == "Republican":
                return 1
            return 0  # Tossup/TIED

        shifts = list(range(min_shift, max_shift + 1, step))

        # Build frames
        frames = []
        base_title = f"{self.year} US Election Results — Margin Shift: "

        for s in shifts:
            # Reset back to baseline for a clean frame
            self.reset_all_states()

            # Apply swing: positive = Democratic, negative = Republican
            if s > 0:
                self.apply_margin_swing_all_states("Democratic", abs(s))
            elif s < 0:
                self.apply_margin_swing_all_states("Republican", abs(s))
            else:
                self.determine_winner()

            df = build_frame_df(self)
            z = df["Winner"].apply(winner_to_code)

            dem_ev = self.results["Democratic"][1]
            gop_ev = self.results["Republican"][1]
            tossup_ev = self.results.get("TossupEV", 0)

            pv_party, pv_margin = self.get_popular_vote_margin()
            pv_label = f"{pv_party[:3]} +{pv_margin:.1f}%"

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

        # Start at 0 shift
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

        # IMPORTANT: return to baseline after generating frames
        self.reset_all_states()
