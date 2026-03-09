// per_state_control.js — map interaction: click-to-select, per-state slider,
// national slider sync, import/export.
// Utility functions live in utils.js (loaded before this file).
(function () {
  var plotDiv = document.getElementById("myDiv") || document.querySelector(".plotly-graph-div");
  if (!plotDiv) return;

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  var currentKey    = PER_STATE_DEFAULT_KEY;
  var currentShift  = 0;
  var selectedState = null;
  var stateOverrides = {};      // { abbr: signedDelta }  +D / -R
  var mode = "map";             // "map" = national slider active | "state" = per-state panel active
  var _suppressRelayout = false; // guards against spurious plotly_relayout from Plotly.restyle()

  // Used only by exportCurrentState — reads from the DOM title as last resort.
  function getElectionInfo() {
    var el = plotDiv.querySelector(".gtitle");
    var t  = (el && el.getAttribute("data-unformatted")) || "";
    var km = t.match(/^(.+?) US Election Results/);
    var sm = t.match(/Margin Shift:\s*(-?\d+)/);
    return {
      key:   km ? km[1] : currentKey,
      shift: sm ? parseInt(sm[1], 10) : currentShift,
    };
  }

  // ---------------------------------------------------------------------------
  // computeAndRestyle — single source of truth for map colors, tooltip, title
  // Uses currentKey/currentShift module vars kept in sync by plotly_relayout.
  // ---------------------------------------------------------------------------
  function computeAndRestyle() {
    var key   = currentKey;
    var shift = currentShift;
    // Read shift directly from Plotly's slider state — authoritative, guards
    // against stale module var if a relayout event fires and resets currentShift.
    try {
      var sl = plotDiv.layout && plotDiv.layout.sliders && plotDiv.layout.sliders[0];
      if (sl && sl.steps && sl.active !== undefined) {
        var lbl = sl.steps[sl.active] && sl.steps[sl.active].label;
        var parsed = parseInt(lbl, 10);
        if (!isNaN(parsed)) { shift = parsed; currentShift = parsed; }
      }
    } catch (e) {}
    var data  = PER_STATE_BASELINE[key];
    if (!data) return;

    // Pass 1: z codes + EV/PV accumulators
    var demEV = 0, repEV = 0, tossupEV = 0, demPV = 0, repPV = 0;
    var z = data.locations.map(function (loc, i) {
      var tot  = data.dem_votes[i] + data.rep_votes[i] + data.other_votes[i];
      var half = (shift + (stateOverrides[loc] || 0)) / 2;
      demPV += tot > 0 ? Math.round(((data.dem_votes[i]/tot)*100 + half)/100*tot) : data.dem_votes[i];
      repPV += tot > 0 ? Math.round(((data.rep_votes[i]/tot)*100 - half)/100*tot) : data.rep_votes[i];
      var adj   = data.signed_margins[i] + shift + (stateOverrides[loc] || 0);
      var zCode = adj > 0 ? -1 : adj < 0 ? 1 : 0;
      if (zCode === -1) demEV += data.evs[i];
      else if (zCode === 1) repEV += data.evs[i];
      else tossupEV += data.evs[i];
      return zCode;
    });

    // District EVs (ME-1/2, NE-1/2/3) — not on map, only national shift applies
    var demDistEV = 0, repDistEV = 0, tossupDistEV = 0;
    (data.district_baselines || []).forEach(function (d) {
      var adj = d.signed_margin + shift;
      if (adj > 0) demDistEV += d.ev;
      else if (adj < 0) repDistEV += d.ev;
      else tossupDistEV += d.ev;
    });

    var tpAbbr = computeTPAbbr(data, z, shift, stateOverrides, demDistEV, repDistEV);
    var tpArr  = tpAbbr ? [tpAbbr] : [];
    var tpIdx  = tpAbbr ? data.locations.indexOf(tpAbbr) : -1;
    var tpName = tpIdx >= 0 ? data.state_names[tpIdx] : "N/A";

    // Pass 2: customdata rows
    var customdata = data.locations.map(function (loc, i) {
      var adj = data.signed_margins[i] + shift + (stateOverrides[loc] || 0);
      var winner, votes;
      if (z[i] === -1)     { winner = "Democratic"; votes = data.dem_votes[i]; }
      else if (z[i] === 1) { winner = "Republican";  votes = data.rep_votes[i]; }
      else                 { winner = "Tossup";       votes = 0; }
      return [winner, data.evs[i], Math.abs(adj).toFixed(2), votes,
              loc === tpAbbr ? "\u2605 Tipping Point" : ""];
    });

    // Suppress any plotly_relayout that Plotly.restyle() may fire (e.g. with
    // the figure's initial title), which would incorrectly reset currentKey.
    _suppressRelayout = true;
    Plotly.restyle(plotDiv, {
      locations:  [data.locations, tpArr],
      z:          [z,              tpArr.length ? [0] : []],
      customdata: [customdata,     [[]]],
    }, [0, 1]);
    _suppressRelayout = false;

    // Fold in district EVs for the title (map colors already correct above)
    demEV += demDistEV; repEV += repDistEV; tossupEV += tossupDistEV;

    // Title written directly to the SVG element — bypasses Plotly events entirely
    var pvTot = demPV + repPV || 1;
    var pvP   = demPV >= repPV ? "Dem" : "GOP";
    var pvM   = (Math.abs(demPV - repPV) / pvTot * 100).toFixed(1);
    var newTitle = key + " US Election Results \u2014 Margin Shift: " + shift +
      " | Dem " + demEV + " - GOP " + repEV + " - Tossup " + tossupEV +
      " | PV: " + pvP + " +" + pvM + "% | TP: " + tpName;
    var el = plotDiv.querySelector(".gtitle");
    if (el) { el.textContent = newTitle; el.setAttribute("data-unformatted", newTitle); }
  }

  // ---------------------------------------------------------------------------
  // plotly_relayout — detect year/shift changes and reapply overrides.
  // Always reads from update["title.text"] (the incoming change),
  // never from plotDiv.layout which may lag or store stale values.
  // ---------------------------------------------------------------------------
  plotDiv.on("plotly_relayout", function (update) {
    // Ignore relayout events fired by our own Plotly.restyle() calls
    // (Plotly can emit these with the figure's initial title, which would
    //  incorrectly reset currentKey to the default year).
    if (_suppressRelayout) { _suppressRelayout = false; return; }

    var title = update["title.text"] || "";
    if (!title) return;
    var km = title.match(/^(.+?) US Election Results/);
    if (!km) return;
    var newKey   = km[1];
    var sm       = title.match(/Margin Shift:\s*(-?\d+)/);
    var newShift = sm ? parseInt(sm[1], 10) : currentShift;

    if (newKey !== currentKey) {
      currentKey = newKey;
      currentShift = newShift;
      resetToMapMode();  // year change → clear overrides, reset mode, update toggle
      return;
    }
    currentShift = newShift;

    if (Object.keys(stateOverrides).length > 0) computeAndRestyle();
  });

  // plotly_sliderstep fires BEFORE Plotly applies data, so we defer via
  // setTimeout to ensure computeAndRestyle runs AFTER the slider's own
  // restyle completes. This keeps per-state overrides intact on slider moves.
  plotDiv.on("plotly_sliderstep", function (data) {
    if (mode === "state") return;  // slider locked in State Swing mode
    var label = data.step && data.step.label;
    var s = parseInt(label, 10);
    if (!isNaN(s)) currentShift = s;
  });

  // ---------------------------------------------------------------------------
  // plotly_click — open per-state panel when user clicks a state
  // ---------------------------------------------------------------------------
  plotDiv.on("plotly_click", function (evt) {
    if (mode !== "state") return;       // per-state panel only in State Swing mode
    if (!evt || !evt.points || !evt.points.length) return;
    var pt = evt.points[0];
    if (pt.curveNumber !== 0) return;   // ignore TP overlay trace
    var abbr = pt.location;
    if (!abbr) return;

    var baseline = PER_STATE_BASELINE[currentKey];
    var name = abbr;
    if (baseline) {
      var idx = baseline.locations.indexOf(abbr);
      if (idx >= 0) name = baseline.state_names[idx];
    }
    openPanel(abbr, name, stateOverrides[abbr] || 0);
  });

  // ---------------------------------------------------------------------------
  // Per-state floating panel
  // ---------------------------------------------------------------------------
  var panel = null, panelSlider = null;

  function createPanel() {
    panel = document.createElement("div");
    panel.style.cssText = [
      "position:fixed;bottom:80px;left:16px;z-index:2000;",
      "background:#fff;border:1px solid #ccc;border-radius:6px;",
      "padding:12px 16px;min-width:230px;",
      "box-shadow:0 2px 10px rgba(0,0,0,0.15);",
      "font-family:sans-serif;font-size:13px;display:none;",
    ].join("");
    panel.innerHTML = [
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">',
        '<span class="psc-name" style="font-weight:700;font-size:15px;"></span>',
        '<button class="psc-close" style="border:none;background:none;',
          'cursor:pointer;font-size:18px;line-height:1;color:#888;padding:0;">&#x2715;</button>',
      '</div>',
      '<div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">',
        '<span style="font-size:11px;color:#c00;white-space:nowrap;">R+10</span>',
        '<input class="psc-slider" type="range" min="-10" max="10" step="1" value="0"',
          ' style="flex:1;cursor:pointer;accent-color:#555;">',
        '<span style="font-size:11px;color:#00c;white-space:nowrap;">D+10</span>',
      '</div>',
      '<div style="text-align:center;margin-bottom:12px;">',
        '<strong class="psc-label" style="font-size:14px;"></strong>',
      '</div>',
      '<div style="display:flex;gap:8px;">',
        '<button class="psc-reset-state" style="flex:1;padding:5px 0;cursor:pointer;',
          'font-size:12px;border:1px solid #ccc;border-radius:3px;background:#f5f5f5;">',
          'Reset State</button>',
        '<button class="psc-reset-all" style="flex:1;padding:5px 0;cursor:pointer;',
          'font-size:12px;border:1px solid #ccc;border-radius:3px;background:#f5f5f5;">',
          'Reset All</button>',
      '</div>',
    ].join("");

    panelSlider = panel.querySelector(".psc-slider");
    panelSlider.addEventListener("input", function () {
      var val = parseInt(this.value, 10);
      setPanelLabel(val);
      if (!selectedState) return;
      if (val === 0) delete stateOverrides[selectedState];
      else stateOverrides[selectedState] = val;
      computeAndRestyle();
    });
    panel.querySelector(".psc-close").addEventListener("click", closePanel);
    panel.querySelector(".psc-reset-state").addEventListener("click", function () {
      if (!selectedState) return;
      delete stateOverrides[selectedState];
      panelSlider.value = 0; setPanelLabel(0);
      computeAndRestyle();
    });
    panel.querySelector(".psc-reset-all").addEventListener("click", function () {
      stateOverrides = {};
      panelSlider.value = 0; setPanelLabel(0);
      computeAndRestyle(); closePanel();
    });
    document.body.appendChild(panel);
  }

  function setPanelLabel(val) {
    val = parseInt(val, 10);
    var el = panel.querySelector(".psc-label");
    el.style.color = val > 0 ? "#00c" : val < 0 ? "#c00" : "#555";
    el.textContent = val > 0 ? "D+" + val : val < 0 ? "R+" + Math.abs(val) : "Baseline";
  }

  function openPanel(abbr, name, override) {
    selectedState = abbr;
    panel.querySelector(".psc-name").textContent = name;
    panelSlider.value = override; setPanelLabel(override);
    panel.style.display = "block";
  }

  function closePanel() { panel.style.display = "none"; selectedState = null; }

  // ---------------------------------------------------------------------------
  // Export CSV (includes per-state overrides)
  // ---------------------------------------------------------------------------
  function getCurrentElectionState() { return getElectionInfo(); }

  function exportCurrentState() {
    var s    = getCurrentElectionState();
    var data = PER_STATE_BASELINE[s.key];
    if (!data) return;
    var rows = ["State,EV,Democratic,Republican,Other"];
    data.locations.forEach(function (abbr, i) {
      var dem = data.dem_votes[i], rep = data.rep_votes[i], other = data.other_votes[i];
      var total = dem + rep + other;
      if (total <= 0) { rows.push([data.state_names[i],data.evs[i],dem,rep,other].join(",")); return; }
      var half   = (s.shift + (stateOverrides[abbr] || 0)) / 2;
      var demAdj = Math.round(((dem/total)*100 + half) / 100 * total);
      var repAdj = Math.round(((rep/total)*100 - half) / 100 * total);
      rows.push([data.state_names[i], data.evs[i], demAdj, repAdj, other].join(","));
    });
    var label = s.shift===0?"baseline":s.shift>0?"D+"+s.shift:"R+"+Math.abs(s.shift);
    var blob  = new Blob([rows.join("\n")], { type:"text/csv" });
    var url   = URL.createObjectURL(blob);
    var a     = document.createElement("a");
    a.href = url; a.download = s.key + "_" + label + ".csv"; a.click();
    URL.revokeObjectURL(url);
  }

  // ---------------------------------------------------------------------------
  // Import CSV (orchestration — utilities from utils.js)
  // ---------------------------------------------------------------------------
  function importCSV(file) {
    if (!yearFromFilename(file.name)) {
      alert("\"" + file.name + "\" must contain a presidential year (divisible by 4, 1788–2100).");
      return;
    }
    var reader = new FileReader();
    reader.onload = function (e) {
      var rows = parseElectionCSV(e.target.result);
      if (!rows) { alert("CSV must have columns: State, EV, Democratic, Republican, Other"); return; }
      var key = file.name.replace(/\.csv$/i, "");
      if (PER_STATE_BASELINE[key] && !confirm("\"" + key + "\" already loaded. Replace?")) return;

      var steps   = plotDiv.layout.sliders[0].steps;
      var shifts  = steps.map(function (s) { return parseInt(s.label, 10); });
      var zeroIdx = shifts.indexOf(0);
      var n2a     = buildNameToAbbrMap();

      var allFrames = shifts.map(function (s) {
        var f  = buildImportFrame(rows, s, n2a);
        var tp = tpFromImportFrame(f);
        var tpName = tp ? (f.names[f.locs.indexOf(tp)] || tp) : "N/A";
        f.cd = f.cd.map(function (c, i) { c[4] = f.locs[i]===tp ? "\u2605 Tipping Point" : ""; return c; });
        f.tp = tp;
        f.title = key + " US Election Results \u2014 Margin Shift: " + s + " | " +
          "Dem " + f.dEV + " - GOP " + f.rEV + " - Tossup " + f.tEV +
          " | PV: " + f.pvP + " +" + f.pvM + "% | TP: " + tpName;
        return f;
      });

      var z0 = allFrames[zeroIdx];
      PER_STATE_BASELINE[key] = { locations:z0.locs, state_names:z0.names,
        signed_margins:z0.sm, dem_votes:z0.dv, rep_votes:z0.rv,
        other_votes:z0.ov, evs:z0.evs };

      var newSteps = allFrames.map(function (f, i) {
        var tp = f.tp ? [f.tp] : [];
        return { label:String(shifts[i]), method:"update", args:[
          { locations:[f.locs,tp], z:[f.z,[0]], customdata:[f.cd,[[]]] },
          { "title.text": f.title },
        ]};
      });

      var tp0 = z0.tp ? [z0.tp] : [];
      var newBtn = { label:key, method:"update", args:[
        { locations:[z0.locs,tp0], z:[z0.z,[0]], customdata:[z0.cd,[[]]] },
        { "title.text":z0.title, "sliders[0].steps":newSteps, "sliders[0].active":zeroIdx },
      ]};

      var mi = plotDiv.layout.updatemenus.length - 1;
      var btns = plotDiv.layout.updatemenus[mi].buttons.slice();
      btns.push(newBtn);
      var u = {}; u["updatemenus[" + mi + "].buttons"] = btns;
      Plotly.relayout(plotDiv, u);
    };
    reader.readAsText(file);
  }

  // ---------------------------------------------------------------------------
  // Mode toggle — Map Swing vs State Swing (inserted below the plot)
  // ---------------------------------------------------------------------------
  var sliderLockOverlay = null;
  var modeMapBtn = null, modeStateBtn = null, modeHint = null;
  var _btnBase = "padding:5px 16px;font-size:12px;font-weight:600;cursor:pointer;" +
                 "border-radius:4px;border:1px solid;transition:none;";

  function styleToggle() {
    if (!modeMapBtn) return;  // not yet created
    if (mode === "map") {
      modeMapBtn.style.cssText   = _btnBase + "background:#1565c0;color:#fff;border-color:#0d47a1;";
      modeStateBtn.style.cssText = _btnBase + "background:#f5f5f5;color:#444;border-color:#bbb;";
      modeHint.textContent       = "Margin slider shifts all states — click states disabled";
    } else {
      modeMapBtn.style.cssText   = _btnBase + "background:#f5f5f5;color:#444;border-color:#bbb;";
      modeStateBtn.style.cssText = _btnBase + "background:#2e7d32;color:#fff;border-color:#1b5e20;";
      modeHint.textContent       = "Click a state to set its individual swing — map slider locked";
    }
  }

  // Called on year change to reset both mode and slider state cleanly.
  function resetToMapMode() {
    mode = "map";
    stateOverrides = {};
    closePanel();
    if (sliderLockOverlay) sliderLockOverlay.style.display = "none";
    styleToggle();
  }

  function createModeToggle() {
    // Overlay that blocks the Plotly slider when in State Swing mode
    sliderLockOverlay = document.createElement("div");
    sliderLockOverlay.style.cssText = [
      "position:absolute;left:0;right:0;bottom:0;height:72px;",
      "z-index:900;cursor:not-allowed;display:none;",
      "background:rgba(220,220,220,0.70);",
      "align-items:center;justify-content:center;",
      "font-family:sans-serif;font-size:12px;color:#555;",
      "border-top:2px dashed #aaa;pointer-events:all;",
    ].join("");
    sliderLockOverlay.innerHTML =
      "<span style='background:rgba(255,255,255,0.85);padding:4px 12px;" +
      "border-radius:4px;border:1px solid #bbb;'>" +
      "&#128274;&nbsp;Map slider locked &mdash; switch to <b>Map Swing</b> to use</span>";
    plotDiv.appendChild(sliderLockOverlay);

    // Toggle bar inserted immediately after plotDiv
    var wrap = document.createElement("div");
    wrap.style.cssText = [
      "display:flex;align-items:center;gap:10px;",
      "padding:7px 14px;font-family:sans-serif;font-size:12px;",
      "background:#f8f8f8;border-top:1px solid #ddd;",
    ].join("");

    var lbl = document.createElement("span");
    lbl.textContent = "Swing Mode:";
    lbl.style.cssText = "color:#555;font-weight:700;white-space:nowrap;";

    modeMapBtn = document.createElement("button");
    modeMapBtn.textContent = "Map Swing";
    modeMapBtn.title = "Use the margin slider to shift all states together";

    modeStateBtn = document.createElement("button");
    modeStateBtn.textContent = "State Swing";
    modeStateBtn.title = "Click any state on the map to set its individual swing";

    modeHint = document.createElement("span");
    modeHint.style.cssText = "color:#888;font-size:11px;";

    modeMapBtn.onclick = function () {
      if (mode === "map") return;
      mode = "map";
      stateOverrides = {};
      closePanel();
      sliderLockOverlay.style.display = "none";
      computeAndRestyle();
      styleToggle();
    };

    modeStateBtn.onclick = function () {
      if (mode === "state") return;
      mode = "state";
      sliderLockOverlay.style.display = "flex";
      styleToggle();
    };

    styleToggle();
    wrap.appendChild(lbl);
    wrap.appendChild(modeMapBtn);
    wrap.appendChild(modeStateBtn);
    wrap.appendChild(modeHint);
    if (plotDiv.parentNode) plotDiv.parentNode.insertBefore(wrap, plotDiv.nextSibling);
  }

  // ---------------------------------------------------------------------------
  // Toolbar buttons (Import CSV + Export CSV, top-right)
  // ---------------------------------------------------------------------------
  function addButtons() {
    var style = document.createElement("style");
    style.textContent = ".modebar-container { display:none !important; }";
    document.head.appendChild(style);

    plotDiv.style.position = "relative";
    var base = "padding:4px 12px;font-size:12px;font-weight:600;cursor:pointer;" +
               "background:#f5f5f5;border:1px solid #ccc;border-radius:3px;color:#444;";

    var fi = document.createElement("input");
    fi.type = "file"; fi.accept = ".csv"; fi.style.display = "none";
    fi.addEventListener("change", function () { if (fi.files.length) importCSV(fi.files[0]); fi.value=""; });
    plotDiv.appendChild(fi);

    var ib = document.createElement("button");
    ib.textContent = "Import CSV"; ib.title = "Import a CSV election to add it to the map";
    ib.style.cssText = "position:absolute;top:6px;right:120px;z-index:1000;" + base;
    ib.onclick = function () { fi.click(); };
    plotDiv.appendChild(ib);

    var eb = document.createElement("button");
    eb.textContent = "Export CSV"; eb.title = "Export current election state as CSV";
    eb.style.cssText = "position:absolute;top:6px;right:6px;z-index:1000;" + base;
    eb.onclick = exportCurrentState;
    plotDiv.appendChild(eb);
  }

  // ---------------------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------------------
  createPanel();
  addButtons();
  createModeToggle();

  // Close panel when clicking outside plotDiv and the panel itself
  document.addEventListener("click", function (e) {
    if (!panel || panel.style.display === "none") return;
    if (!plotDiv.contains(e.target) && !panel.contains(e.target)) {
      closePanel();
    }
  });
})();
