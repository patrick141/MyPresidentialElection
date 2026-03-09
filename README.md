# MyPresidentialElection

An interactive U.S. Presidential Election modeling engine built in Python using Plotly.

This project simulates national vote swings and dynamically recalculates state outcomes and Electoral College totals in real time.

![2024 Election Results Map](assets/2024ElectionResultWithToggle.png)

---

# 🎯 Project Goal

Build a flexible election simulation engine that:

* Models all 50 states + DC
* Supports Maine & Nebraska split electoral allocation
* Applies a uniform national swing via interactive slider
* Dynamically updates:

  * State winners
  * Electoral vote totals
  * Margins
* Exports standalone interactive HTML
* Eventually allows:

  * Full state modification
  * Saving scenarios
  * Uploading external datasets
  * Extracting simulation results

The long-term vision is a modular election modeling system that can support multiple election cycles and custom workflows.

---

# 🚀 Phase 1 (Completed)

## ✅ Core Election Engine

* Object-oriented `State` and `Election` classes
* Tracks:

  * Baseline results
  * Simulated results
  * Margin (Dem-positive scale)
  * Winner
  * Electoral Votes
* Clean separation between base data and simulated data

## ✅ Uniform National Swing

* Slider range: -10 to +10 points
* 1-point increments
* Positive shift = Democratic swing
* Negative shift = Republican swing
* Each slider frame:

  * Resets to baseline
  * Applies margin swing
  * Recalculates EV totals

## ✅ Interactive Visualization

* Plotly choropleth map
* Dynamic title showing Electoral Vote totals
* Hover shows:

  * Winner
  * EV
  * Margin
  * Votes
* Play button animates swing across range
* Standalone HTML export:

  * `election_results_map.html`
  * `election_results_map_with_margin.html`

## ✅ Maine & Nebraska Support

* Correctly modeled split electoral allocation:

  * Statewide EV
  * District-level EV
* District rows treated as individual EV units
* Structured to support grouped behavior in later phases

---

# 🧠 Architecture

## State Model

Each `State` object stores:

* `base_results`
* `results`
* `unit_type` (statewide or district)
* `parent_state` (for ME/NE grouping)

Supports:

* Vote shift
* Margin shift
* Reset to baseline
* Winner recalculation

---

## Election Engine

Handles:

* CSV parsing
* EV aggregation
* Popular vote margin
* Tipping point state
* Electoral College bias
* Simulation methods
* Visualization generation

---

# 📁 Project Structure

```
├── data/
│   └── 2020.csv
├── src/
│   ├── __init__.py
│   ├── constants.py
│   ├── election.py
│   └── state.py
├── main.py
├── election_results_map.html
├── election_results_map_with_margin.html
└── README.md
```

---

# 🏁 Phase 2 (Complete)

## ✅ Multi-Election Support

* Toggle between 2020 and 2024 in a single interactive HTML
* `Election` accepts a 4-digit year string or any CSV file path
* Presidential year validation enforced on all inputs
* Single visualization engine supports multiple years simultaneously

## ✅ Full State Modification — ME/NE Districts

* ME-1, ME-2, NE-1, NE-2, NE-3 now swing with the national slider
* Results displayed as live-updating colored boxes in the right panel
* Consistent swing behavior across all statewide + district units
* Fixed: district EVs (5) and DC EVs (3) were previously missing from JS Electoral College totals — now correctly counted via `district_baselines` and `constants.py` aliases

## ✅ Scenario Saving & Import

* `export_scenario(path)` exports current simulated state to CSV or JSON
* Schema matches `data/YEAR.csv` — exported files are drop-in compatible
* `Election("scenarios/2024_D+5.csv")` loads any scenario CSV as a new election
* Presidential year auto-extracted from filename via regex and validated
* Loaded scenarios plug directly into the multi-year slider as a new toggle button
* In-browser Export CSV button captures current state including per-state overrides

## ✅ Per-State Individual Control

* Click any state on the map to open a floating per-state swing panel
* Independent per-state slider (±10 points) stacks on top of the state's baseline
* Panel displays D+/R+ label, state name, Reset State, and Reset All controls
* Panel closes on outside click or X button
* EV totals, popular vote margin, and tipping point state update in real time
* **Mode toggle bar** below the map separates two exclusive swing modes:
  * **Map Swing** — national margin slider shifts all states together; per-state panel disabled
  * **State Swing** — national slider locked; click any state to set its individual swing
* Switching years resets both modes to Map Swing baseline cleanly

> **Tradeoff:** Combining a national swing with simultaneous per-state overrides in one unified mode was not achievable due to Plotly's pre-computed frame rendering — slider frames hard-overwrite the map trace, destroying per-state customizations. The two modes are mutually exclusive. Unified control (national + per-state simultaneously) is carried forward to Phase 3.

## 📥 Data Source

Current CSV files (`2020.csv`, `2024.csv`) were manually sourced from Wikipedia election results pages and formatted to match the engine's expected schema:

```
State, EV, Democratic, Republican, Other
```

> **Stretch Goal:** `scripts/build_year_csv.py` is a placeholder script for automating this process via an external dataset. Not yet implemented — see Phase 3.

---

# 🗄 Phase 3 (Planned)

## 🔄 Unified Swing Control *(Carried from Phase 2)*

* Combine national margin slider and per-state overrides in one unified mode
* User sets a national swing AND independently adjusts individual states on top of it
* Requires replacing Plotly's pre-computed slider frames with a custom HTML range input that calls the JS rendering engine directly — eliminating the frame-overwrite limitation

## 📥 Automated Data Pipeline *(Stretch Goal)*

* Automate CSV generation via an external election dataset
* `scripts/build_year_csv.py` is the placeholder — wire up a reliable data source
* Extend coverage back to earlier election cycles (2012, 2008, and beyond)
* Consistent CSV schema across all years for drop-in engine compatibility

## 🧱 Database Integration

* Introduce PostgreSQL (or similar relational database)
* Store:

  * Election cycles
  * State-level results
  * Saved scenarios
* Separate data storage from simulation engine

## 🌐 Backend Refactor

* Modularize simulation logic
* Expose API endpoints
* Support external data ingestion
* Enable structured result retrieval

## 📈 Advanced Modeling

* Polling data ingestion
* Scenario comparison
* Historical election analysis
* Performance optimization

---

# 🛠 Technologies

* Python 3.8
* Pandas
* Plotly
* Object-Oriented Design

Planned:

* PostgreSQL
* Backend API layer

---

# 🔍 What This Project Covers

## 🧱 Election Modeling

* State-level electoral vote aggregation
* Split allocation modeling (Maine & Nebraska)
* Margin-based winner determination
* Popular vote vs Electoral College comparison
* Tipping point state identification
* Electoral College bias calculation

---

## 🎛 Simulation Engine

* Baseline vs simulated result tracking
* Uniform national margin swing
* State-level vote and margin adjustment methods
* Reset-to-baseline frame generation
* Deterministic recalculation per slider step

---

## 📊 Visualization Layer

* Interactive Plotly choropleth map
* Dynamic electoral vote totals in title
* Hover metadata display (EV, margin, votes)
* Frame-based animation (slider + play button)
* Standalone HTML export

---

## 🗄 Extensible Architecture

* Multi-election dataset support (planned)
* Modular State and Election classes
* Designed for future database integration
* Designed for scenario saving and data workflows

---

# 🧪 How to Run

```bash
pip install -r requirements.txt
python main.py
```

Open:

```
election_results_map_with_margin.html
```

---

# 📌 Current Status

* ✅ Phase 1: Complete
* ✅ Phase 2: Complete — per-state individual control delivered with mode toggle; unified national + per-state swing moved to Phase 3
* 🗄 Phase 3: Unified swing control, database integration, and backend modularization (planned)

---
