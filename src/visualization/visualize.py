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

from src.model.constants import us_state_to_abbrev

load_dotenv()

# Paths to the JS files injected as post_script into the exported HTML
_JS_PATH       = Path(__file__).parent.parent / "static" / "js" / "per_state_control.js"
_JS_UTILS_PATH = Path(__file__).parent.parent / "static" / "js" / "utils.js"

# States to overlay with EV count labels: (state_name_in_csv, lat, lon)
# All 48 continental states. DC, AK, HI omitted — Plotly insets don't align
# with scattergeo lat/lon coordinates.
_EV_LABEL_STATES = [
    # West Coast
    ("Washington",     47.4, -120.5),
    ("Oregon",         43.8, -120.5),
    ("California",     37.2, -119.4),
    # Mountain West
    ("Nevada",         39.3, -116.6),
    ("Idaho",          44.5, -114.5),
    ("Montana",        46.9, -110.4),
    ("Wyoming",        43.0, -107.6),
    ("Utah",           39.4, -111.5),
    ("Colorado",       39.1, -105.6),
    ("Arizona",        34.3, -111.8),
    ("New Mexico",     34.4, -106.1),
    # Plains
    ("North Dakota",   47.5, -100.5),
    ("South Dakota",   44.4, -100.3),
    ("Nebraska",       41.5, -100.0),
    ("Kansas",         38.5,  -98.4),
    ("Oklahoma",       35.6,  -97.5),
    ("Texas",          31.5,  -99.3),
    # Midwest (west of Mississippi)
    ("Minnesota",      46.4,  -94.5),
    ("Iowa",           42.1,  -93.5),
    ("Missouri",       38.5,  -92.6),
    ("Arkansas",       34.8,  -92.5),
    ("Louisiana",      31.0,  -91.8),
    # Midwest (east of Mississippi)
    ("Wisconsin",      44.5,  -90.0),
    ("Michigan",       44.3,  -85.4),
    ("Illinois",       40.0,  -89.2),
    ("Indiana",        40.3,  -86.1),
    ("Ohio",           40.4,  -82.8),
    # South
    ("Mississippi",    32.7,  -89.7),
    ("Alabama",        32.8,  -86.8),
    ("Tennessee",      35.8,  -86.3),
    ("Kentucky",       37.5,  -85.3),
    ("Georgia",        32.7,  -83.4),
    ("Florida",        27.8,  -81.7),
    ("South Carolina", 33.8,  -80.9),
    ("North Carolina", 35.6,  -79.4),
    ("Virginia",       37.8,  -79.5),
    ("West Virginia",  38.6,  -80.6),
    # Northeast
    ("Pennsylvania",   41.2,  -77.2),
    ("New York",       42.9,  -75.6),
    ("Maine",          45.4,  -69.0),
    ("Vermont",        44.0,  -72.7),
    ("New Hampshire",  43.7,  -71.6),
    ("Massachusetts",  42.3,  -71.8),
    ("Rhode Island",   41.7,  -71.5),
    ("Connecticut",    41.6,  -72.7),
    ("New Jersey",     40.1,  -74.5),
    ("Delaware",       39.0,  -75.5),
    ("Maryland",       39.0,  -76.8),
]

# Order and y-positions for the five congressional district annotation boxes
_DISTRICT_ORDER = ["ME-1", "ME-2", "NE-1", "NE-2", "NE-3"]
_PANEL_X = 0.89
_DISTRICT_Y_POSITIONS = [0.73, 0.66, 0.59, 0.52, 0.45]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _winner_to_code(w):
    # Converts winner string to a numeric z-value used by the choropleth colorscale
    if w == "Democratic": return -1
    if w == "Republican": return 1
    return 0


def _winner_to_color(w):
    # Maps a winner string to the display color used in district annotation boxes
    if w == "Democratic": return "royalblue"
    if w == "Republican": return "crimson"
    return "dimgray"


def _build_state_df(election_obj):
    """
    Builds a DataFrame of statewide results only, filtering out congressional districts.
    Rows without a valid state abbreviation (e.g. unmapped names) are dropped.
    """
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
            "Lead":       abs(st.get_vote_lead()) if winner not in ("Tossup", "TIED") else 0,
            "Dem_Votes":   st.get_vote_by_party("Democratic"),
            "Rep_Votes":   st.get_vote_by_party("Republican"),
            "Other_Votes": st.get_vote_by_party("Other"),
        })
    df = pd.DataFrame(rows)
    # Drop any rows where the state abbreviation lookup returned None
    return df[df["State Abbr"].notna()]


def _collect_districts(election_obj):
    """
    Returns a list of annotation dicts for the five congressional districts in DISTRICT_ORDER.
    Districts missing from the election data fall back to an N/A gray box.
    """
    district_map = {}
    for st in election_obj.states:
        if st.get_parent_state() is not None:
            winner = st.get_winner()
            party, margin = st.get_margin()
            # Format the annotation text based on whether the district is a tossup
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
    """
    Builds a relayout dict that updates district annotation text and background color.
    Indices 1–5 correspond to the five district boxes (index 0 is the header).
    """
    out = {}
    for j, d in enumerate(districts):
        out[f"annotations[{j + 1}].text"] = d["text"]
        out[f"annotations[{j + 1}].bgcolor"] = d["color"]
    return out


def _build_district_annotations(default_districts):
    """
    Builds the static Plotly annotations list: one header box and five colored district boxes.
    These are placed to the right of the map using paper-relative coordinates.
    """
    # Header label above the district boxes
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
    # One colored annotation box per district in display order
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
    Returns a dict of {state_name: signed_delta} for states manually shifted from baseline.
    Positive delta = Democratic lean; negative = Republican lean.
    """
    overrides = {}
    for st in election_obj.states:
        # Skip congressional districts — only statewide states can be overridden
        if st.get_parent_state() is not None:
            continue
        party, margin = st.get_margin()
        current_signed = margin if party == "Democratic" else -margin
        br = st.get_base_results()
        total = sum(br.values()) or 1
        base_signed = (br.get("Democratic", 0) / total - br.get("Republican", 0) / total) * 100
        delta = round(current_signed - base_signed, 6)
        # Only record states that have meaningfully diverged from baseline
        if abs(delta) > 0.001:
            overrides[st.get_name()] = delta
    return overrides


def _reapply_state_overrides(election_obj, overrides):
    """
    Re-applies previously captured per-state overrides after a national reset.
    Called inside the slider frame loop to preserve per-state adjustments across shifts.
    """
    for state_name, delta in overrides.items():
        st = election_obj.find_state_by_name(state_name)
        if st:
            party = "Democratic" if delta > 0 else "Republican"
            st.apply_margin_shift_to_party(party, abs(delta))
    if overrides:
        election_obj.determine_winner()


def _build_ev_label_trace_data(election_obj):
    """
    Returns (lats, lons, texts) for the EV label scattergeo trace.
    Only includes states defined in _EV_LABEL_STATES that exist in the election.
    """
    lats, lons, texts = [], [], []
    for name, lat, lon in _EV_LABEL_STATES:
        st = election_obj.find_state_by_name(name)
        if st:
            lats.append(lat)
            lons.append(lon)
            texts.append(str(st.get_ev()))
    return lats, lons, texts


def _get_ec_bias_label(election_obj):
    """
    Returns a formatted EC bias string e.g. 'GOP +1.82%'.
    Saves and restores states order because get_ec_bias sorts in place.
    """
    saved_order = list(election_obj.states)
    bias_party, bias_margin = election_obj.get_ec_bias()
    election_obj.states = saved_order
    if bias_party == "TIED":
        return "Even"
    return f"{bias_party[:3]} +{bias_margin:.2f}%"


def _get_tp_info(election_obj):
    """
    Returns (tp_abbr, tp_name) for the current tipping point state.
    Saves and restores self.states order because get_tipping_point_state sorts in place.
    """
    saved_order = list(election_obj.states)
    tp = election_obj.get_tipping_point_state()
    election_obj.states = saved_order   # restore order after in-place sort
    if not tp:
        return "", "N/A"
    return us_state_to_abbrev.get(tp.get_name(), ""), tp.get_name()


def _build_per_state_post_script(baseline_js, default_key):
    """
    Builds the JavaScript post_script injected into the HTML after Plotly renders.
    Embeds baseline data as JS variables and concatenates utils.js + per_state_control.js.
    """
    return (
        f"var PER_STATE_BASELINE = {json.dumps(baseline_js)};\n"
        f"var PER_STATE_DEFAULT_KEY = {json.dumps(default_key)};\n"
        + _JS_UTILS_PATH.read_text() + "\n"
        + _JS_PATH.read_text()
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
    Year toggle buttons swap the map and rewire the margin slider for that year.
    Congressional district results are shown as colored annotation boxes on the right.
    Per-state swing is available via the mode toggle bar injected below the map.
    """
    shifts = list(range(min_shift, max_shift + 1, step))
    # Index of the zero-shift (baseline) frame within the shifts list
    zero_idx = shifts.index(0) if 0 in shifts else len(shifts) // 2

    # ------------------------------------------------------------------
    # Precompute all slider frames: year_data[key][shift_idx]
    # ------------------------------------------------------------------
    year_data = {}
    baseline_js = {}   # signed margins + vote data at shift=0, used by JS per-state control

    for election in elections:
        key = election.label
        year_data[key] = []
        # Capture any pre-existing per-state overrides before the frame loop resets them
        state_overrides = _capture_state_overrides(election)

        for i, s in enumerate(shifts):
            # Always reset to baseline before applying each shift for clean frame data
            election.reset_all_states()
            for st in election.states:
                if s > 0:
                    st.apply_margin_shift_to_party("Democratic", abs(s))
                elif s < 0:
                    st.apply_margin_shift_to_party("Republican", abs(s))
            election.determine_winner()
            # Re-apply any pre-existing per-state overrides on top of the national shift
            _reapply_state_overrides(election, state_overrides)

            df = _build_state_df(election)
            z = df["Winner"].apply(_winner_to_code).tolist()

            tp_abbr, tp_name = _get_tp_info(election)
            # Flag the tipping point state in the hover tooltip customdata
            df["TP_Flag"] = df["State Abbr"].apply(
                lambda a: "★ Tipping Point" if a == tp_abbr else ""
            )

            dem_ev    = election.results["Democratic"][1]
            gop_ev    = election.results["Republican"][1]
            tossup_ev = election.results.get("TossupEV", 0)
            dem_votes = election.results["Democratic"][0]
            gop_votes = election.results["Republican"][0]
            total_votes = election.total_vote or 1
            dem_pct = dem_votes / total_votes * 100
            gop_pct = gop_votes / total_votes * 100
            pv_party, pv_margin = election.get_popular_vote_margin()
            pv_label   = f"{pv_party[:3]} +{pv_margin:.2f}%"
            bias_label = _get_ec_bias_label(election)
            title = (
                f"{key} US Election Results — Shift: {s} | "
                f"Dem {dem_ev} EV · {dem_votes/1e6:.2f}M ({dem_pct:.2f}%)  vs  "
                f"GOP {gop_ev} EV · {gop_votes/1e6:.2f}M ({gop_pct:.2f}%)"
                f"  |  PV: {pv_label}  |  TP: {tp_name}  |  Bias: {bias_label}"
            )

            year_data[key].append({
                "locations":  df["State Abbr"].tolist(),
                "z":          z,
                "customdata": df[["Winner", "EV", "Margin", "Lead", "TP_Flag"]].values.tolist(),
                "title":      title,
                "districts":  _collect_districts(election),
                "tp_abbr":    tp_abbr,
            })

            # At shift=0, capture baseline signed margins and vote counts for the JS layer
            if i == zero_idx:
                signed = [
                    row["Margin"] if row["Winner"] == "Democratic" else -row["Margin"]
                    for _, row in df.iterrows()
                ]
                # Congressional districts are not in the choropleth df; collect their
                # EVs separately so the JS can include them in the 270-check and title
                dist_baselines = []
                for st in election.states:
                    if st.get_parent_state() is None:
                        continue
                    dparty, dmargin = st.get_margin()
                    dsigned = dmargin if dparty == "Democratic" else -dmargin
                    dist_baselines.append({
                        "ev": st.get_ev(),
                        "signed_margin": round(dsigned, 4),
                    })
                baseline_js[key] = {
                    "locations":          df["State Abbr"].tolist(),
                    "state_names":        df["State"].tolist(),
                    "signed_margins":     signed,
                    "dem_votes":          df["Dem_Votes"].tolist(),
                    "rep_votes":          df["Rep_Votes"].tolist(),
                    "other_votes":        df["Other_Votes"].tolist(),
                    "evs":                df["EV"].tolist(),
                    "district_baselines": dist_baselines,
                }

        # Always return the election to baseline after all frames are built
        election.reset_all_states()

    # ------------------------------------------------------------------
    # Build slider steps and year toggle buttons
    # ------------------------------------------------------------------
    default_key = elections[0].label
    default = year_data[default_key][zero_idx]

    def make_slider_steps(key):
        """Builds the list of Plotly slider step dicts for a given election year."""
        ev = ev_label_data[key]
        steps = []
        for i, s in enumerate(shifts):
            d = year_data[key][i]
            # Each step updates the map trace (restyle) and the title + annotations (relayout).
            # EV label trace (index 2) is re-asserted on every step so it persists through
            # slider moves — Plotly drops unreferenced traces during partial re-renders.
            relayout = {"title.text": d["title"]}
            relayout.update(_district_relayout(d["districts"]))
            tp = [d["tp_abbr"]] if d["tp_abbr"] else []
            steps.append({
                "label": str(s),
                "method": "update",
                "args": [
                    {
                        "locations":  [d["locations"], tp,    None],
                        "z":          [d["z"],  [0] if tp else [], None],
                        "customdata": [d["customdata"], [[]],  None],
                        "lat":        [None,    None,           ev["lat"]],
                        "lon":        [None,    None,           ev["lon"]],
                        "text":       [None,    None,           ev["text"]],
                    },
                    relayout,
                ],
            })
        return steps

    # Precompute EV label trace data per year (EV values are fixed per year, not per shift)
    ev_label_data = {}
    for election in elections:
        lats, lons, texts = _build_ev_label_trace_data(election)
        ev_label_data[election.label] = {"lat": lats, "lon": lons, "text": texts}

    # Each year button swaps the map to that year's baseline and rewires slider steps
    year_buttons = []
    for election in elections:
        key = election.label
        d = year_data[key][zero_idx]
        ev = ev_label_data[key]
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
                    "locations":  [d["locations"], tp,       None],
                    "z":          [d["z"],          [0] if tp else [], None],
                    "customdata": [d["customdata"], [[]],    None],
                    "lat":        [None,            None,    ev["lat"]],
                    "lon":        [None,            None,    ev["lon"]],
                    "text":       [None,            None,    ev["text"]],
                },
                relayout,
            ],
        })

    # ------------------------------------------------------------------
    # Optional Play button + animation frames (controlled by env var)
    # ------------------------------------------------------------------
    show_play = os.getenv("SHOW_PLAY_BUTTON", "false").lower() == "true"
    all_frames = []
    if show_play:
        # Build one go.Frame per shift per year for the Play animation
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
                            "Lead: %{customdata[3]:,}<extra></extra>"
                        ),
                    )],
                    layout=go.Layout(title_text=d["title"]),
                ))

    # Build the updatemenus list — always includes year buttons; Play is optional
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
    # Assemble the Plotly figure with two traces:
    #   trace 0 — main choropleth (state colors)
    #   trace 1 — tipping point overlay (gold highlight)
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
                    "Lead: %{customdata[3]:,}<br>%{customdata[4]}<extra></extra>"
                ),
            ),
            # Semi-transparent gold overlay that marks the tipping point state
            go.Choropleth(
                locations=default_tp,
                z=[0] if default_tp else [],
                locationmode="USA-states",
                zmin=0, zmax=0,
                colorscale=[[0, "rgba(255,215,0,0.45)"], [1, "rgba(255,215,0,0.45)"]],
                showscale=False,
                hoverinfo="skip",
            ),
            # EV count labels rendered as white text over large states
            go.Scattergeo(
                lat=ev_label_data[default_key]["lat"],
                lon=ev_label_data[default_key]["lon"],
                text=ev_label_data[default_key]["text"],
                mode="text",
                textfont=dict(size=18, color="white", family="Arial Black"),
                hoverinfo="skip",
                showlegend=False,
            ),
        ],
        layout=go.Layout(
            title_text=default["title"],
            # Map occupies ~88% of width; right 12% reserved for district annotation panel
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

    # Inject JS baseline data and interaction logic as a post-render script
    post_script = _build_per_state_post_script(baseline_js, default_key)
    fig.show()
    fig.write_html(output_file, post_script=post_script)
