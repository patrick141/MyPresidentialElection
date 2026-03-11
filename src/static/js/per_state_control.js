// per_state_control.js
// Map interaction: click-to-select, per-state slider, import/export, and
// robust year/shift synchronization (no title-based year parsing).

(function () {
  var plotDiv = document.getElementById("myDiv") || document.querySelector(".plotly-graph-div");
  if (!plotDiv) return;

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  var currentKey     = PER_STATE_DEFAULT_KEY;
  var currentShift   = 0;
  var selectedState  = null;
  var stateOverrides = {};    // { abbr: signedDelta }  +D / -R
  var mode           = "map"; // "map" = national slider | "state" = per-state panel
  var _suppressUntil = 0;

  function _suppress(ms) { _suppressUntil = Date.now() + (ms || 350); }
  function _isSuppressed() { return Date.now() < _suppressUntil; }

  function getLiveShift() {
    try {
      var sl = plotDiv.layout && plotDiv.layout.sliders && plotDiv.layout.sliders[0];
      if (sl && sl.steps && sl.active !== undefined) {
        var lbl = sl.steps[sl.active] && sl.steps[sl.active].label;
        var parsed = parseInt(lbl, 10);
        if (!isNaN(parsed)) return parsed;
      }
    } catch (e) {}
    return currentShift || 0;
  }

  // ---------------------------------------------------------------------------
  // Toast + Modal
  // ---------------------------------------------------------------------------
  function showToast(message) {
    var t = document.createElement("div");
    t.style.cssText = [
      "position:fixed;bottom:24px;right:24px;z-index:9999;",
      "background:#323232;color:#fff;font-family:sans-serif;font-size:13px;",
      "padding:10px 16px;border-radius:5px;max-width:340px;line-height:1.4;",
      "box-shadow:0 2px 10px rgba(0,0,0,0.4);opacity:0;",
      "transition:opacity 0.3s;"
    ].join("");
    t.textContent = message;
    document.body.appendChild(t);
    requestAnimationFrame(function () { t.style.opacity = "1"; });
    setTimeout(function () {
      t.style.opacity = "0";
      setTimeout(function () { if (t.parentNode) document.body.removeChild(t); }, 350);
    }, 3000);
  }

  function showModal(message, onExportAndContinue, onContinue, title) {
    var overlay = document.createElement("div");
    overlay.style.cssText = [
      "position:fixed;top:0;left:0;right:0;bottom:0;",
      "background:rgba(0,0,0,0.55);z-index:9998;",
      "display:flex;align-items:center;justify-content:center;"
    ].join("");

    var box = document.createElement("div");
    box.style.cssText = [
      "background:#fff;border-radius:8px;padding:22px 24px;",
      "max-width:420px;width:90%;",
      "box-shadow:0 6px 24px rgba(0,0,0,0.35);",
      "font-family:sans-serif;font-size:13px;line-height:1.55;color:#333;"
    ].join("");

    var modalTitle = title || "Unsaved Changes";
    box.innerHTML =
      "<div style='font-weight:700;font-size:15px;margin-bottom:10px;'>" +
      "⚠️ " + modalTitle + "</div>" +
      "<p style='margin:0 0 18px;'>" + message + "</p>" +
      "<div style='display:flex;gap:8px;justify-content:flex-end;'>" +
      "<button class='m-cancel' style='padding:6px 14px;font-size:12px;font-weight:600;" +
      "cursor:pointer;border:1px solid #bbb;border-radius:4px;background:#f5f5f5;color:#444;'>Cancel</button>" +
      "<button class='m-export' style='padding:6px 14px;font-size:12px;font-weight:600;" +
      "cursor:pointer;border:1px solid #1565c0;border-radius:4px;background:#1565c0;color:#fff;'>Export CSV &amp; Continue</button>" +
      "<button class='m-discard' style='padding:6px 14px;font-size:12px;font-weight:600;" +
      "cursor:pointer;border:1px solid #c62828;border-radius:4px;background:#c62828;color:#fff;'>Discard Changes</button>" +
      "</div>";

    function close() { document.body.removeChild(overlay); }

    box.querySelector(".m-cancel").addEventListener("click", close);
    box.querySelector(".m-export").addEventListener("click", function () {
      close();
      exportCurrentState();
      if (onExportAndContinue) onExportAndContinue();
    });
    box.querySelector(".m-discard").addEventListener("click", function () {
      close();
      if (onContinue) onContinue();
    });
    overlay.addEventListener("click", function (e) { if (e.target === overlay) close(); });

    overlay.appendChild(box);
    document.body.appendChild(overlay);
  }

  // ---------------------------------------------------------------------------
  // Mode toggle
  // ---------------------------------------------------------------------------
  var sliderLockOverlay = null;
  var modeMapBtn = null, modeStateBtn = null, modeHint = null;
  var panel = null, panelSlider = null;

  function setYearButtonsLocked(locked) {
    var menus = plotDiv.querySelectorAll(".updatemenu-container");
    if (!menus.length) return;
    var yearMenu = menus[menus.length - 1];
    yearMenu.style.pointerEvents = locked ? "none" : "";
    yearMenu.style.opacity = locked ? "0.35" : "";
    yearMenu.title = locked ? "Switch to Map Swing first to change year" : "";
  }

  function resetToMapMode() {
    mode = "map";
    stateOverrides = {};
    closePanel();
    if (sliderLockOverlay) sliderLockOverlay.style.display = "none";
    setYearButtonsLocked(false);
    styleToggle();
  }

  function styleToggle() {
    if (!modeMapBtn) return;
    var base = "padding:5px 16px;font-size:12px;font-weight:600;cursor:pointer;border-radius:4px;border:1px solid;";
    if (mode === "map") {
      modeMapBtn.style.cssText = base + "background:#1565c0;color:#fff;border-color:#0d47a1;";
      modeStateBtn.style.cssText = base + "background:#f5f5f5;color:#444;border-color:#bbb;";
      modeHint.textContent = "Margin slider shifts all states — click states disabled";
    } else {
      modeMapBtn.style.cssText = base + "background:#f5f5f5;color:#444;border-color:#bbb;";
      modeStateBtn.style.cssText = base + "background:#2e7d32;color:#fff;border-color:#1b5e20;";
      modeHint.textContent = "Click a state to set its individual swing — map slider locked";
    }
  }

  // ---------------------------------------------------------------------------
  // Core: computeAndRestyle (single source of truth for map + title)
  // ---------------------------------------------------------------------------
  function computeAndRestyle() {
    var key = currentKey;
    var shift = getLiveShift();
    currentShift = shift;

    var data = PER_STATE_BASELINE[key];
    if (!data) return;

    // Pass 1: z codes + EV/PV accumulators
    var demEV = 0, repEV = 0, tossupEV = 0, demPV = 0, repPV = 0;

    var z = data.locations.map(function (loc, i) {
      var tot = data.dem_votes[i] + data.rep_votes[i] + data.other_votes[i];
      var half = (shift + (stateOverrides[loc] || 0)) / 2;

      // PV approximations (kept consistent with your existing approach)
      demPV += tot > 0 ? Math.round((((data.dem_votes[i] / tot) * 100 + half) / 100) * tot) : data.dem_votes[i];
      repPV += tot > 0 ? Math.round((((data.rep_votes[i] / tot) * 100 - half) / 100) * tot) : data.rep_votes[i];

      var adj = data.signed_margins[i] + shift + (stateOverrides[loc] || 0);
      var zCode = adj > 0 ? -1 : adj < 0 ? 1 : 0;

      if (zCode === -1) demEV += data.evs[i];
      else if (zCode === 1) repEV += data.evs[i];
      else tossupEV += data.evs[i];

      return zCode;
    });

    // District EVs (not on map)
    var demDistEV = 0, repDistEV = 0, tossupDistEV = 0;
    (data.district_baselines || []).forEach(function (d) {
      var adj = d.signed_margin + shift;
      if (adj > 0) demDistEV += d.ev;
      else if (adj < 0) repDistEV += d.ev;
      else tossupDistEV += d.ev;
    });

    var tpAbbr = computeTPAbbr(data, z, shift, stateOverrides, demDistEV, repDistEV);
    var tpArr = tpAbbr ? [tpAbbr] : [];
    var tpIdx = tpAbbr ? data.locations.indexOf(tpAbbr) : -1;
    var tpName = tpIdx >= 0 ? data.state_names[tpIdx] : "N/A";

    // Pass 2: customdata
    var customdata = data.locations.map(function (loc, i) {
      var adj = data.signed_margins[i] + shift + (stateOverrides[loc] || 0);
      var winner, votes;
      if (z[i] === -1)     { winner = "Democratic"; votes = data.dem_votes[i]; }
      else if (z[i] === 1) { winner = "Republican"; votes = data.rep_votes[i]; }
      else                 { winner = "Tossup";     votes = 0; }

      return [winner, data.evs[i], Math.abs(adj).toFixed(2), votes, loc === tpAbbr ? "★ Tipping Point" : ""];
    });

    // Apply restyle (trace 0 map, trace 1 TP overlay)
    _suppress();
    Plotly.restyle(plotDiv, {
      locations: [data.locations, tpArr],
      z: [z, tpArr.length ? [0] : []],
      customdata: [customdata, [[]]]
    }, [0, 1]);

    // Fold district EV into title totals
    demEV += demDistEV; repEV += repDistEV; tossupEV += tossupDistEV;

    var pvTot = demPV + repPV || 1;
    var pvP = demPV >= repPV ? "Dem" : "GOP";
    var pvM = (Math.abs(demPV - repPV) / pvTot * 100).toFixed(2);
    var demPct = (demPV / pvTot * 100).toFixed(2);
    var gopPct = (repPV / pvTot * 100).toFixed(2);
    var demM = (demPV / 1e6).toFixed(2);
    var gopM = (repPV / 1e6).toFixed(2);

    // EC Bias (matches your existing logic style)
    var biasLabel = "N/A";
    if (tpIdx >= 0) {
      var tpAdj = data.signed_margins[tpIdx] + shift + (stateOverrides[tpAbbr] || 0);
      var tpParty = tpAdj >= 0 ? "Dem" : "GOP";
      var tpMargAbs = Math.abs(tpAdj);
      var pvMargAbs = parseFloat(pvM);
      var winParty = pvP;
      var otherParty = winParty === "Dem" ? "GOP" : "Dem";
      var relMargin, relParty;
      if (winParty === tpParty) {
        relMargin = pvMargAbs - tpMargAbs;
        relParty = relMargin < 0 ? winParty : otherParty;
      } else {
        relMargin = pvMargAbs + tpMargAbs;
        relParty = otherParty;
      }
      biasLabel = relParty + " +" + Math.abs(relMargin).toFixed(2) + "%";
    }

    var newTitle =
      key + " US Election Results — Shift: " + shift +
      " | Dem " + demEV + " EV · " + demM + "M (" + demPct + "%)  vs  " +
      "GOP " + repEV + " EV · " + gopM + "M (" + gopPct + "%)" +
      " | Tossup " + tossupEV +
      " | PV: " + pvP + " +" + pvM + "% | TP: " + tpName + " | Bias: " + biasLabel;

    var el = plotDiv.querySelector(".gtitle");
    if (el) { el.textContent = newTitle; el.setAttribute("data-unformatted", newTitle); }
  }

  // ---------------------------------------------------------------------------
  // Year changes: ONLY from button clicks (no title parsing)
  // ---------------------------------------------------------------------------
  plotDiv.on("plotly_buttonclicked", function (e) {
    if (!e || !e.button || typeof e.button.label !== "string") return;

    var label = e.button.label; // year key, e.g. "2024"
    if (!PER_STATE_BASELINE[label]) return; // ignore Play etc.

    var hadOverrides = Object.keys(stateOverrides).length > 0;

    currentKey = label;
    currentShift = getLiveShift();

    resetToMapMode();

    if (hadOverrides) {
      showToast(
        "Switched to " + label + " — state overrides were cleared. " +
        "Use “Export CSV” next time to save them first."
      );
    }
  });

  // Relayout: never infer year; only keep shift in sync and preserve overrides
  plotDiv.on("plotly_relayout", function () {
    if (_isSuppressed()) return;
    currentShift = getLiveShift();
    if (Object.keys(stateOverrides).length > 0) computeAndRestyle();
  });

  // Slider step: update shift var (computeAndRestyle will run when overrides exist)
  plotDiv.on("plotly_sliderstep", function (evt) {
    if (mode === "state") return;
    var s = parseInt(evt.step && evt.step.label, 10);
    if (!isNaN(s)) currentShift = s;
  });

  // ---------------------------------------------------------------------------
  // Per-state click (only active in State Swing mode)
  // ---------------------------------------------------------------------------
  plotDiv.on("plotly_click", function (evt) {
    if (mode !== "state") return;
    if (!evt || !evt.points || !evt.points.length) return;

    var pt = evt.points[0];
    if (pt.curveNumber !== 0) return; // ignore TP overlay

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
  // Panel
  // ---------------------------------------------------------------------------
  function setPanelLabel(val) {
    val = parseInt(val, 10);
    var el = panel.querySelector(".psc-label");
    el.style.color = val > 0 ? "#00c" : val < 0 ? "#c00" : "#555";
    el.textContent = val > 0 ? "D+" + val : val < 0 ? "R+" + Math.abs(val) : "Baseline";
  }

  function createPanel() {
    panel = document.createElement("div");
    panel.style.cssText = [
      "position:fixed;bottom:80px;left:16px;z-index:2000;",
      "background:#fff;border:1px solid #ccc;border-radius:6px;",
      "padding:12px 16px;min-width:230px;",
      "box-shadow:0 2px 10px rgba(0,0,0,0.15);",
      "font-family:sans-serif;font-size:13px;display:none;"
    ].join("");

    panel.innerHTML = [
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">',
      '<span class="psc-name" style="font-weight:700;font-size:15px;"></span>',
      '<button class="psc-close" style="border:none;background:none;cursor:pointer;font-size:18px;line-height:1;color:#888;padding:0;">✕</button>',
      '</div>',
      '<div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">',
      '<span style="font-size:11px;color:#c00;white-space:nowrap;">R+10</span>',
      '<input class="psc-slider" type="range" min="-10" max="10" step="1" value="0" style="flex:1;cursor:pointer;accent-color:#555;">',
      '<span style="font-size:11px;color:#00c;white-space:nowrap;">D+10</span>',
      '</div>',
      '<div style="text-align:center;margin-bottom:12px;"><strong class="psc-label" style="font-size:14px;"></strong></div>',
      '<div style="display:flex;gap:8px;">',
      '<button class="psc-reset-state" style="flex:1;padding:5px 0;cursor:pointer;font-size:12px;border:1px solid #ccc;border-radius:3px;background:#f5f5f5;">Reset State</button>',
      '<button class="psc-reset-all" style="flex:1;padding:5px 0;cursor:pointer;font-size:12px;border:1px solid #ccc;border-radius:3px;background:#f5f5f5;">Reset All</button>',
      "</div>"
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
      computeAndRestyle();
      closePanel();
    });

    document.body.appendChild(panel);
  }

  function openPanel(abbr, name, override) {
    selectedState = abbr;
    panel.querySelector(".psc-name").textContent = name;
    panelSlider.value = override;
    setPanelLabel(override);
    panel.style.display = "block";
  }

  function closePanel() {
    panel.style.display = "none";
    selectedState = null;
  }

  // ---------------------------------------------------------------------------
  // Export CSV
  // ---------------------------------------------------------------------------
  function exportCurrentState() {
    var key = currentKey;
    var shift = getLiveShift();
    var data = PER_STATE_BASELINE[key];
    if (!data) return;

    var rows = ["State,EV,Democratic,Republican,Other"];
    data.locations.forEach(function (abbr, i) {
      var dem = data.dem_votes[i], rep = data.rep_votes[i], other = data.other_votes[i];
      var total = dem + rep + other;

      if (total <= 0) {
        rows.push([data.state_names[i], data.evs[i], dem, rep, other].join(","));
        return;
      }

      var half = (shift + (stateOverrides[abbr] || 0)) / 2;
      var demAdj = Math.round((((dem / total) * 100 + half) / 100) * total);
      var repAdj = Math.round((((rep / total) * 100 - half) / 100) * total);

      rows.push([data.state_names[i], data.evs[i], demAdj, repAdj, other].join(","));
    });

    var label = shift === 0 ? "baseline" : shift > 0 ? "D+" + shift : "R+" + Math.abs(shift);
    var blob = new Blob([rows.join("\n")], { type: "text/csv" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = key + "_" + label + ".csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  // ---------------------------------------------------------------------------
  // Import CSV (same behavior, but safe year parsing)
  // ---------------------------------------------------------------------------
  function importCSV(file) {
    var fileName = sanitizeFilename(file.name);
    if (!yearFromFilename(fileName)) {
      showToast("“" + fileName + "” must contain a presidential year (divisible by 4, 1788–2100).");
      return;
    }

    var reader = new FileReader();
    reader.onload = function (e) {
      var rows = parseElectionCSV(e.target.result);
      if (!rows) { showToast("CSV must have columns: State, EV, Democratic, Republican (Other optional)"); return; }

      var key = file.name.replace(/\.csv$/i, "");
      if (PER_STATE_BASELINE[key]) {
        showModal(
          "“" + sanitizeFilename(key) + "” is already loaded. Replace it? This cannot be undone.",
          function () { doImport(key, rows); },
          function () { doImport(key, rows); }
        );
        return;
      }
      doImport(key, rows);
    };
    reader.readAsText(file);
  }

  function doImport(key, rows) {
    var steps = plotDiv.layout.sliders[0].steps;
    var shifts = steps.map(function (s) { return parseInt(s.label, 10); });
    var zeroIdx = shifts.indexOf(0);
    var n2a = buildNameToAbbrMap();

    var allFrames = shifts.map(function (s) {
      var f = buildImportFrame(rows, s, n2a);
      var tp = tpFromImportFrame(f);
      var tpName = tp ? (f.names[f.locs.indexOf(tp)] || tp) : "N/A";
      f.cd = f.cd.map(function (c, i) { c[4] = f.locs[i] === tp ? "★ Tipping Point" : ""; return c; });
      f.tp = tp;

      var fDemTot = f.dv.reduce(function (a, b) { return a + b; }, 0);
      var fRepTot = f.rv.reduce(function (a, b) { return a + b; }, 0);
      var fPvTot = fDemTot + fRepTot || 1;

      var fDemM = (fDemTot / 1e6).toFixed(2);
      var fGopM = (fRepTot / 1e6).toFixed(2);
      var fDemPct = (fDemTot / fPvTot * 100).toFixed(2);
      var fGopPct = (fRepTot / fPvTot * 100).toFixed(2);
      var fPvM = (Math.abs(fDemTot - fRepTot) / fPvTot * 100).toFixed(2);

      f.title =
        key + " US Election Results — Shift: " + s +
        " | Dem " + f.dEV + " EV · " + fDemM + "M (" + fDemPct + "%)  vs  " +
        "GOP " + f.rEV + " EV · " + fGopM + "M (" + fGopPct + "%) | " +
        "Tossup " + f.tEV + " | PV: " + f.pvP + " +" + fPvM + "% | TP: " + tpName;

      return f;
    });

    var z0 = allFrames[zeroIdx];
    PER_STATE_BASELINE[key] = {
      locations: z0.locs,
      state_names: z0.names,
      signed_margins: z0.sm,
      dem_votes: z0.dv,
      rep_votes: z0.rv,
      other_votes: z0.ov,
      evs: z0.evs,
      district_baselines: [] // imports are statewide only
    };

    var newSteps = allFrames.map(function (f, i) {
      var tp = f.tp ? [f.tp] : [];
      return {
        label: String(shifts[i]),
        method: "update",
        args: [
          { locations: [f.locs, tp], z: [f.z, tp.length ? [0] : []], customdata: [f.cd, [[]]] },
          { "title.text": f.title }
        ]
      };
    });

    var tp0 = z0.tp ? [z0.tp] : [];
    var newBtn = {
      label: key,
      method: "update",
      args: [
        { locations: [z0.locs, tp0], z: [z0.z, tp0.length ? [0] : []], customdata: [z0.cd, [[]]] },
        { "title.text": z0.title, "sliders[0].steps": newSteps, "sliders[0].active": zeroIdx }
      ]
    };

    var mi = plotDiv.layout.updatemenus.length - 1;
    var btns = plotDiv.layout.updatemenus[mi].buttons.slice();
    btns.push(newBtn);

    var u = {};
    u["updatemenus[" + mi + "].buttons"] = btns;
    Plotly.relayout(plotDiv, u);
  }

  // ---------------------------------------------------------------------------
  // UI controls: buttons + mode toggle
  // ---------------------------------------------------------------------------
  function addButtons() {
    var style = document.createElement("style");
    style.textContent = ".modebar-container { display:none !important; }";
    document.head.appendChild(style);

    plotDiv.style.position = "relative";
    var base = "padding:4px 12px;font-size:12px;font-weight:600;cursor:pointer;background:#f5f5f5;border:1px solid #ccc;border-radius:3px;color:#444;";

    var fi = document.createElement("input");
    fi.type = "file"; fi.accept = ".csv"; fi.style.display = "none";
    fi.addEventListener("change", function () { if (fi.files.length) importCSV(fi.files[0]); fi.value = ""; });
    plotDiv.appendChild(fi);

    var ib = document.createElement("button");
    ib.textContent = "Import CSV";
    ib.title = "Import a CSV election to add it to the map";
    ib.style.cssText = "position:absolute;top:6px;right:120px;z-index:1000;" + base;
    ib.onclick = function () { fi.click(); };
    plotDiv.appendChild(ib);

    var eb = document.createElement("button");
    eb.textContent = "Export CSV";
    eb.title = "Export current election state as CSV";
    eb.style.cssText = "position:absolute;top:6px;right:6px;z-index:1000;" + base;
    eb.onclick = exportCurrentState;
    plotDiv.appendChild(eb);
  }

  function createModeToggle() {
    sliderLockOverlay = document.createElement("div");
    sliderLockOverlay.style.cssText = [
      "position:absolute;left:0;right:0;bottom:0;height:72px;",
      "z-index:900;cursor:not-allowed;display:none;",
      "background:rgba(220,220,220,0.70);",
      "align-items:center;justify-content:center;",
      "font-family:sans-serif;font-size:12px;color:#555;",
      "border-top:2px dashed #aaa;pointer-events:all;"
    ].join("");
    sliderLockOverlay.innerHTML =
      "<span style='background:rgba(255,255,255,0.85);padding:4px 12px;border-radius:4px;border:1px solid #bbb;'>" +
      "🔒 Map slider locked — switch to <b>Map Swing</b> to use</span>";
    plotDiv.appendChild(sliderLockOverlay);

    var wrap = document.createElement("div");
    wrap.style.cssText = [
      "display:flex;align-items:center;gap:8px;",
      "padding:6px 12px;font-family:sans-serif;font-size:12px;",
      "background:#f4f4f4;border-bottom:1px solid #ddd;",
      "position:sticky;top:0;z-index:500;"
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

      function doSwitch() {
        mode = "map";
        stateOverrides = {};
        closePanel();
        sliderLockOverlay.style.display = "none";
        setYearButtonsLocked(false);
        computeAndRestyle();
        styleToggle();
      }

      if (Object.keys(stateOverrides).length > 0) {
        showModal(
          "Switching to Map Swing will clear all per-state overrides. Export your scenario as CSV first if you want to keep it.",
          doSwitch,
          doSwitch,
          "Unsaved State Overrides"
        );
      } else {
        doSwitch();
      }
    };

    modeStateBtn.onclick = function () {
      if (mode === "state") return;

      var liveShift = getLiveShift();
      function doEnterState() {
        // Reset slider to 0 when entering state mode (your existing UX)
        try {
          var sl = plotDiv.layout.sliders[0];
          var zIdx = -1;
          for (var i = 0; i < sl.steps.length; i++) {
            if (parseInt(sl.steps[i].label, 10) === 0) { zIdx = i; break; }
          }
          if (zIdx >= 0 && liveShift !== 0) {
            var stepArgs = sl.steps[zIdx].args;
            _suppress(500);
            Plotly.update(plotDiv, stepArgs[0], stepArgs[1]).then(function () {
              Plotly.relayout(plotDiv, { "sliders[0].active": zIdx });
            });
            currentShift = 0;
          }
        } catch (e) {}

        mode = "state";
        sliderLockOverlay.style.display = "flex";
        setYearButtonsLocked(true);
        styleToggle();
      }

      if (liveShift === 0) {
        doEnterState();
        return;
      }

      var shiftLabel = liveShift > 0 ? "D+" + liveShift : "R+" + Math.abs(liveShift);
      showModal(
        "The map is currently shifted <b>" + shiftLabel + "</b>. Switching to State Swing will reset the global slider to 0. Export the scenario first if you want to keep it.",
        doEnterState,
        doEnterState,
        "Unsaved Map Shift"
      );
    };

    wrap.appendChild(lbl);
    wrap.appendChild(modeMapBtn);
    wrap.appendChild(modeStateBtn);
    wrap.appendChild(modeHint);

    if (plotDiv.parentNode) plotDiv.parentNode.insertBefore(wrap, plotDiv);
    styleToggle();
  }

  // ---------------------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------------------
  createPanel();
  addButtons();
  createModeToggle();

  document.addEventListener("click", function (e) {
    if (!panel || panel.style.display === "none") return;
    if (!plotDiv.contains(e.target) && !panel.contains(e.target)) closePanel();
  });

  // Optional: keep year+shift consistent at start
  currentShift = getLiveShift();
})();