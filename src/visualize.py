"""
Visualization module

Standalone visualization functions for multi-year election maps.
Handles Plotly figure construction, district annotation panels,
and per-state control JS injection.
"""

from pathlib import Path
import os
import json
import pandas as pd
import plotly.graph_objects as go
from dotenv import load_dotenv

from src.constants import us_state_to_abbrev

load_dotenv()

_JS_PATH = Path(__file__).parent / "per_state_control.js"
_DISTRICT_ORDER = ["ME-1", "ME-2", "NE-1", "NE-2", "NE-3"]
_PANEL_X = 0.89
_DISTRICT_Y_POSITIONS = [0.73, 0.66, 0.59, 0.52, 0.45]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _winner_to_code(w):
    if w == "Democratic": return -1
    if w == "Republican": return 1
    return 0


def _winner_to_color(w):
    if w == "Democratic": return "royalblue"
    if w == "Republican": return "crimson"
    return "dimgray"


def _build_state_df(election_obj):
    """DataFrame of statewide results only (districts filtered out)."""
    rows = []
    for st in election_obj.states:
        winner = st.get_winner()
        party, margin = st.get_margin()
        rows.append({
            "State":      st.get_name(),
            "State Abbr": us_state_to_abbrev.get(st.get_name()),
            "Winner":     winner,
            "EV":         st.get_ev(),
            "Margin":     round(margin, 2),
            "Votes":      st.get_vote_by_party(winner) if winner not in ("Tossup", "TIED") else 0,
            "Dem_Votes":   st.get_vote_by_party("Democratic"),
            "Rep_Votes":   st.get_vote_by_party("Republican"),
            "Other_Votes": st.get_vote_by_party("Other"),
        })
    df = pd.DataFrame(rows)
    return df[df["State Abbr"].notna()]


def _collect_districts(election_obj):
    """Returns list of district annotation dicts in DISTRICT_ORDER."""
    district_map = {}
    for st in election_obj.states:
        if st.get_parent_state() is not None:
            winner = st.get_winner()
            party, margin = st.get_margin()
            text = (
                f"<b>{st.get_name()}</b>  Tossup"
                if winner in ("Tossup", "TIED")
                else f"<b>{st.get_name()}</b>  {party[0]}+{margin:.1f}%"
            )
            district_map[st.get_name()] = {"text": text, "color": _winner_to_color(winner)}
    return [
        district_map.get(d, {"text": f"<b>{d}</b>  N/A", "color": "dimgray"})
        for d in _DISTRICT_ORDER
    ]


def _district_relayout(districts):
    """Relayout keys to update district annotation boxes (indices 1–5)."""
    out = {}
    for j, d in enumerate(districts):
        out[f"annotations[{j + 1}].text"] = d["text"]
        out[f"annotations[{j + 1}].bgcolor"] = d["color"]
    return out


def _build_district_annotations(default_districts):
    """Build static header + 5 colored district box annotations."""
    annotations = [
        dict(
            text="<b>Congressional<br>Districts</b>",
            x=_PANEL_X, y=0.82,
            xref="paper", yref="paper",
            showarrow=False,
            bgcolor="white",
            bordercolor="lightgray",
            borderwidth=1,
            borderpad=6,
            font=dict(size=11, color="#333"),
            align="center",
            xanchor="left",
            yanchor="top",
        )
    ]
    for j, d in enumerate(default_districts):
        annotations.append(dict(
            text=d["text"],
            x=_PANEL_X,
            y=_DISTRICT_Y_POSITIONS[j],
            xref="paper", yref="paper",
            showarrow=False,
            bgcolor=d["color"],
            bordercolor="white",
            borderwidth=1,
            borderpad=6,
            font=dict(size=11, color="white"),
            align="left",
            xanchor="left",
            yanchor="middle",
            width=130,
        ))
    return annotations


def _capture_state_overrides(election_obj):
    """
    Returns {state_name: signed_delta} for any states that have been manually
    shifted from their baseline. Positive = D lean, negative = R lean.
    """
    overrides = {}
    for st in election_obj.states:
        if st.get_parent_state() is not None:
            continue
        party, margin = st.get_margin()
        current_signed = margin if party == "Democratic" else -margin
        br = st.get_base_results()
        total = sum(br.values()) or 1
        base_signed = (br.get("Democratic", 0) / total - br.get("Republican", 0) / total) * 100
        delta = round(current_signed - base_signed, 6)
        if abs(delta) > 0.001:
            overrides[st.get_name()] = delta
    return overrides


def _reapply_state_overrides(election_obj, overrides):
    """Re-apply per-state overrides after a reset."""
    for state_name, delta in overrides.items():
        st = election_obj.find_state_by_name(state_name)
        if st:
            party = "Democratic" if delta > 0 else "Republican"
            st.apply_margin_shift_to_party(party, abs(delta))
    if overrides:
        election_obj.determine_winner()


def _get_tp_info(election_obj):
    """
    Returns (tp_abbr, tp_name) for the tipping point state.
    Saves and restores election_obj.states order because
    get_tipping_point_state() calls sort_by_state_margins() in-place.
    """
    saved_order = list(election_obj.states)
    tp = election_obj.get_tipping_point_state()
    election_obj.states = saved_order
    if not tp:
        return "", "N/A"
    return us_state_to_abbrev.get(tp.get_name(), ""), tp.get_name()


def _build_per_state_post_script(baseline_js, default_key):
    """
    Builds the post_script string injected into the HTML after Plotly renders.
    Embeds baseline data as JS variables and loads per_state_control.js logic.
    """
    js_template = _JS_PATH.read_text()
    return (
        f"var PER_STATE_BASELINE = {json.dumps(baseline_js)};\n"
        f"var PER_STATE_DEFAULT_KEY = {json.dumps(default_key)};\n"
        + js_template
    )


# ---------------------------------------------------------------------------
# Main visualization function
# ---------------------------------------------------------------------------

def visualize_multi_year_slider(
    elections,
    output_file="election_results_map_with_margin.html",
    min_shift=-10,
    max_shift=10,
    step=1,
):
    """
    Builds a single interactive HTML map supporting multiple election years.
    - Year toggle buttons swap the map and rewire the margin slider.
    - Congressional district results shown as colored boxes on the right panel.
    - Per-state individual control via click-on-map + JS-injected slider.
    - No animation — slider directly redraws the map on each step.
    """
    shifts = list(range(min_shift, max_shift + 1, step))
    zero_idx = shifts.index(0) if 0 in shifts else len(shifts) // 2

    # ------------------------------------------------------------------
    # Precompute all data: year_data[key][shift_idx]
    # ------------------------------------------------------------------
    year_data = {}
    baseline_js = {}   # signed margins at shift=0 for JS per-state control

    for election in elections:
        key = election.label
        year_data[key] = []
        state_overrides = _capture_state_overrides(election)

        for i, s in enumerate(shifts):
            election.reset_all_states()
            for st in election.states:
                if s > 0:
                    st.apply_margin_shift_to_party("Democratic", abs(s))
                elif s < 0:
                    st.apply_margin_shift_to_party("Republican", abs(s))
            election.determine_winner()
            _reapply_state_overrides(election, state_overrides)

            df = _build_state_df(election)
            z = df["Winner"].apply(_winner_to_code).tolist()

            tp_abbr, tp_name = _get_tp_info(election)
            df["TP_Flag"] = df["State Abbr"].apply(
                lambda a: "★ Tipping Point" if a == tp_abbr else ""
            )

            dem_ev = election.results["Democratic"][1]
            gop_ev = election.results["Republican"][1]
            tossup_ev = election.results.get("TossupEV", 0)
            pv_party, pv_margin = election.get_popular_vote_margin()
            pv_label = f"{pv_party[:3]} +{pv_margin:.1f}%"
            title = (
                f"{key} US Election Results — Margin Shift: {s} | "
                f"Dem {dem_ev} - GOP {gop_ev} - Tossup {tossup_ev} | PV: {pv_label} | TP: {tp_name}"
            )

            year_data[key].append({
                "locations":  df["State Abbr"].tolist(),
                "z":          z,
                "customdata": df[["Winner", "EV", "Margin", "Votes", "TP_Flag"]].values.tolist(),
                "title":      title,
                "districts":  _collect_districts(election),
                "tp_abbr":    tp_abbr,
            })

            # Capture signed margins + vote data at shift=0 for JS per-state control
            if i == zero_idx:
                signed = [
                    row["Margin"] if row["Winner"] == "Democratic" else -row["Margin"]
                    for _, row in df.iterrows()
                ]
                baseline_js[key] = {
                    "locations":      df["State Abbr"].tolist(),
                    "state_names":    df["State"].tolist(),
                    "signed_margins": signed,
                    "dem_votes":      df["Dem_Votes"].tolist(),
                    "rep_votes":      df["Rep_Votes"].tolist(),
                    "other_votes":    df["Other_Votes"].tolist(),
                    "evs":            df["EV"].tolist(),
                }

        election.reset_all_states()

    # ------------------------------------------------------------------
    # Build slider steps and year buttons
    # ------------------------------------------------------------------
    default_key = elections[0].label
    default = year_data[default_key][zero_idx]

    def make_slider_steps(key):
        steps = []
        for i, s in enumerate(shifts):
            d = year_data[key][i]
            relayout = {"title.text": d["title"]}
            relayout.update(_district_relayout(d["districts"]))
            tp = [d["tp_abbr"]] if d["tp_abbr"] else []
            steps.append({
                "label": str(s),
                "method": "update",
                "args": [
                    {
                        "locations":  [d["locations"], tp],
                        "z":          [d["z"],          [0] if tp else []],
                        "customdata": [d["customdata"], [[]]],
                    },
                    relayout,
                ],
            })
        return steps

    year_buttons = []
    for election in elections:
        key = election.label
        d = year_data[key][zero_idx]
        relayout = {
            "title.text":        d["title"],
            "sliders[0].steps":  make_slider_steps(key),
            "sliders[0].active": zero_idx,
        }
        relayout.update(_district_relayout(d["districts"]))
        tp = [d["tp_abbr"]] if d["tp_abbr"] else []
        year_buttons.append({
            "label": key,
            "method": "update",
            "args": [
                {
                    "locations":  [d["locations"], tp],
                    "z":          [d["z"],          [0] if tp else []],
                    "customdata": [d["customdata"], [[]]],
                },
                relayout,
            ],
        })

    # ------------------------------------------------------------------
    # Optional Play button + frames
    # ------------------------------------------------------------------
    show_play = os.getenv("SHOW_PLAY_BUTTON", "false").lower() == "true"
    all_frames = []
    if show_play:
        for election in elections:
            key = election.label
            for i, s in enumerate(shifts):
                d = year_data[key][i]
                all_frames.append(go.Frame(
                    name=f"{key}_{s}",
                    data=[go.Choropleth(
                        locations=d["locations"], z=d["z"],
                        locationmode="USA-states", zmin=-1, zmax=1,
                        colorscale=[[0, "blue"], [0.5, "gray"], [1, "red"]],
                        showscale=False, customdata=d["customdata"],
                        hovertemplate=(
                            "<b>%{location}</b><br>Winner: %{customdata[0]}<br>"
                            "EV: %{customdata[1]}<br>Margin: %{customdata[2]}%<br>"
                            "Votes: %{customdata[3]:,}<extra></extra>"
                        ),
                    )],
                    layout=go.Layout(title_text=d["title"]),
                ))

    updatemenus = []
    if show_play:
        updatemenus.append({
            "type": "buttons", "showactive": False, "x": 0.02, "y": 0.95,
            "buttons": [{"label": "Play", "method": "animate",
                         "args": [[f"{default_key}_{s}" for s in shifts],
                                  {"frame": {"duration": 500, "redraw": True},
                                   "fromcurrent": False, "transition": {"duration": 0}}]}],
        })
    updatemenus.append({
        "type": "buttons", "showactive": True,
        "x": 0.86, "y": 0.98, "xanchor": "right", "yanchor": "top", "direction": "right",
        "buttons": year_buttons,
    })

    # ------------------------------------------------------------------
    # Build figure
    # ------------------------------------------------------------------
    default_tp = [default["tp_abbr"]] if default["tp_abbr"] else []
    fig = go.Figure(
        frames=all_frames,
        data=[
            go.Choropleth(
                locations=default["locations"],
                z=default["z"],
                locationmode="USA-states",
                zmin=-1, zmax=1,
                colorscale=[[0, "blue"], [0.5, "gray"], [1, "red"]],
                showscale=False,
                customdata=default["customdata"],
                hovertemplate=(
                    "<b>%{location}</b><br>Winner: %{customdata[0]}<br>"
                    "EV: %{customdata[1]}<br>Margin: %{customdata[2]}%<br>"
                    "Votes: %{customdata[3]:,}<br>%{customdata[4]}<extra></extra>"
                ),
            ),
            go.Choropleth(
                locations=default_tp,
                z=[0] if default_tp else [],
                locationmode="USA-states",
                zmin=0, zmax=0,
                colorscale=[[0, "rgba(255,215,0,0.45)"], [1, "rgba(255,215,0,0.45)"]],
                showscale=False,
                hoverinfo="skip",
            ),
        ],
        layout=go.Layout(
            title_text=default["title"],
            geo=dict(scope="usa", domain=dict(x=[0.0, 0.88], y=[0.0, 1.0])),
            annotations=_build_district_annotations(default["districts"]),
            updatemenus=updatemenus,
            sliders=[{
                "active": zero_idx,
                "currentvalue": {"prefix": "Margin Shift: "},
                "pad": {"t": 50},
                "steps": make_slider_steps(default_key),
            }],
        ),
    )

    post_script = _build_per_state_post_script(baseline_js, default_key)
    fig.show()
    fig.write_html(output_file, post_script=post_script)
