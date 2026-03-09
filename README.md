# MyPresidentialElection

An interactive U.S. Presidential Election modeling engine built in Python and Plotly. Simulates national and state-level vote swings with real-time Electoral College recalculation — exported as a fully standalone interactive HTML file.

![2024 Election Results Map](assets/2024ElectionResultWithToggle.png)

---

# 🎯 Project Goal

Build a flexible, multi-cycle election simulation engine that models all 50 states + DC, supports Maine & Nebraska split electoral allocation, and allows users to explore vote swing scenarios interactively. The long-term vision is a modular system with a backend API, database storage, and automated data pipelines.

---

# 🛠 Technologies

* Python 3.8 · Pandas · Plotly · Object-Oriented Design · JavaScript (vanilla)

Planned: PostgreSQL · Backend API layer

---

# 📁 Project Structure

```
├── data/               # Election CSVs (2020, 2024)
├── scenarios/          # Exported scenario files
├── src/
│   ├── election.py     # Election engine
│   ├── state.py        # State model
│   ├── visualize.py    # Plotly visualization layer
│   ├── per_state_control.js  # In-browser interaction logic
│   ├── utils.js        # JS utility functions
│   └── constants.py    # State abbreviation mappings
├── main.py
└── election_results_map_with_margin.html
```

---

# 🧪 How to Run

```bash
pip install -r requirements.txt
python main.py
```

Open `election_results_map_with_margin.html` in any browser.

---

# 🚀 Phase 1 (Complete)

Built the core engine and interactive visualization from scratch.

* **Election engine** — object-oriented `State` and `Election` classes with clean separation between baseline and simulated data
* **National swing slider** — ±10 point range, dynamically recalculates state winners and Electoral College totals on each step
* **Interactive choropleth map** — hover shows winner, EV, margin, and vote counts; exports as a standalone HTML file
* **Maine & Nebraska support** — correctly models split electoral allocation at both the statewide and district level

---

# 🏁 Phase 2 (Complete)

Expanded the engine to support multiple election years, scenario workflows, and per-state swing control.

## ✅ Multi-Election Year Toggle

Supports toggling between 2020 and 2024 (or any imported year) within a single HTML page. The `Election` class accepts a year string or CSV path with automatic presidential year validation.

## ✅ Scenario Save & Import

Export any simulated state to CSV or JSON via `export_scenario()`. Import any compatible CSV directly in the browser — it registers as a new year toggle button on the map. Exported files are drop-in compatible with the engine's data schema.

## ✅ Per-State Individual Control

Click any state on the map to open a floating swing panel with an independent ±10 point slider. EV totals, popular vote margin, and tipping point update in real time. A **mode toggle bar** below the map switches between:

* **Map Swing** — national slider shifts all states together
* **State Swing** — national slider locked; click any state to adjust it individually

> **Note:** Combining a national swing with per-state overrides simultaneously was not achievable within Plotly's pre-computed frame rendering model. The two modes are intentionally kept separate. Unified control is planned for Phase 3.

---

# 🗄 Phase 3 (Planned)

* **Unified Swing Control** *(carried from Phase 2)* — replace Plotly's pre-computed slider with a custom JS-driven range input, enabling national and per-state swings to work simultaneously
* **Automated Data Pipeline** — automate CSV generation from external datasets; extend coverage to 2008, 2012, and earlier cycles
* **Database Integration** — PostgreSQL storage for election cycles, state results, and saved scenarios
* **Backend API** — modularize simulation logic and expose endpoints for external data ingestion and result retrieval
* **Advanced Modeling** — polling data ingestion, scenario comparison, historical analysis

---

# 🔍 What This Project Covers

**Election Modeling** — state-level EV aggregation, split allocation for Maine & Nebraska, margin-based winner determination, popular vote vs Electoral College comparison, tipping point state identification, and Electoral College bias calculation.

**Simulation Engine** — baseline vs simulated result tracking, uniform national margin swing, per-state vote and margin adjustment, reset-to-baseline on each frame, and deterministic recalculation per slider step.

**Visualization Layer** — interactive Plotly choropleth map with dynamic EV totals, hover metadata, frame-based margin slider, and fully standalone HTML export.

**Extensible Architecture** — modular `State` and `Election` classes, multi-year dataset support, scenario save/load workflows, and designed for future database and API integration.

---

# 📌 Current Status

* ✅ Phase 1: Complete
* ✅ Phase 2: Complete — per-state individual control delivered with mode toggle; unified national + per-state swing moved to Phase 3
* 🗄 Phase 3: Unified swing control, database integration, and backend modularization (planned)

---
