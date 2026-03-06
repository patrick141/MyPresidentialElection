(function () {
  var plotDiv = document.getElementById("myDiv") || document.querySelector(".plotly-graph-div");
  if (!plotDiv) return;

  // ---------------------------------------------------------------------------
  // Read current key and shift directly from the live Plotly figure title
  // ---------------------------------------------------------------------------
  function getCurrentElectionState() {
    var title = (plotDiv.layout && plotDiv.layout.title && plotDiv.layout.title.text) || "";
    var key = PER_STATE_DEFAULT_KEY;
    var shift = 0;
    var keyMatch = title.match(/^(.+?) US Election Results/);
    if (keyMatch) key = keyMatch[1];
    var shiftMatch = title.match(/Margin Shift:\s*(-?\d+)/);
    if (shiftMatch) shift = parseInt(shiftMatch[1], 10);
    return { key: key, shift: shift };
  }

  // ---------------------------------------------------------------------------
  // Export current map state as CSV
  // ---------------------------------------------------------------------------
  function exportCurrentState() {
    var state = getCurrentElectionState();
    var currentKey = state.key;
    var nationalShift = state.shift;
    var data = PER_STATE_BASELINE[currentKey];
    if (!data) return;

    var rows = ["State,EV,Democratic,Republican,Other"];
    data.locations.forEach(function (abbr, i) {
      var dem = data.dem_votes[i];
      var rep = data.rep_votes[i];
      var other = data.other_votes[i];
      var total = dem + rep + other;
      if (total <= 0) {
        rows.push([data.state_names[i], data.evs[i], dem, rep, other].join(","));
        return;
      }
      var half = nationalShift / 2;
      var demAdj = Math.round(((dem / total) * 100 + half) / 100 * total);
      var repAdj = Math.round(((rep / total) * 100 - half) / 100 * total);
      rows.push([data.state_names[i], data.evs[i], demAdj, repAdj, other].join(","));
    });

    var csv = rows.join("\n");
    var shiftLabel = nationalShift === 0 ? "baseline"
      : nationalShift > 0 ? "D+" + nationalShift
      : "R+" + Math.abs(nationalShift);
    var filename = currentKey + "_" + shiftLabel + ".csv";

    var blob = new Blob([csv], { type: "text/csv" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  // ---------------------------------------------------------------------------
  // Import CSV — helpers
  // ---------------------------------------------------------------------------

  function isPresidentialYear(year) {
    return year % 4 === 0 && year >= 1788 && year <= 2100;
  }

  // Mirrors Election._VALID_YEAR_RE: (?:19|20)\d{2} not surrounded by digits
  function extractYearFromFilename(filename) {
    var match = filename.match(/(?<!\d)((?:19|20)\d{2})(?!\d)/);
    if (!match) return null;
    var year = parseInt(match[1], 10);
    return isPresidentialYear(year) ? year : null;
  }

  function parseCSV(text) {
    var lines = text.trim().split(/\r?\n/);
    if (lines.length < 2) return null;
    var header = lines[0].split(",").map(function (s) { return s.trim().toLowerCase(); });
    var stateIdx = header.indexOf("state");
    var evIdx    = header.indexOf("ev");
    var demIdx   = header.indexOf("democratic");
    var repIdx   = header.indexOf("republican");
    var otherIdx = header.indexOf("other");
    if (stateIdx < 0 || evIdx < 0 || demIdx < 0 || repIdx < 0) return null;
    var rows = [];
    for (var i = 1; i < lines.length; i++) {
      var line = lines[i].trim();
      if (!line) continue;
      var cols = line.split(",");
      rows.push({
        state: cols[stateIdx].trim(),
        ev:    parseInt(cols[evIdx], 10)   || 0,
        dem:   parseInt(cols[demIdx], 10)  || 0,
        rep:   parseInt(cols[repIdx], 10)  || 0,
        other: otherIdx >= 0 ? (parseInt(cols[otherIdx], 10) || 0) : 0,
      });
    }
    return rows.length > 0 ? rows : null;
  }

  // Build state-name → abbreviation map from existing baseline data
  function buildNameToAbbr() {
    var map = {};
    var keys = Object.keys(PER_STATE_BASELINE);
    if (keys.length === 0) return map;
    var data = PER_STATE_BASELINE[keys[0]];
    data.state_names.forEach(function (name, i) { map[name] = data.locations[i]; });
    return map;
  }

  // Compute one shift frame from raw rows
  function computeFrame(rows, shift, nameToAbbr) {
    var demEV = 0, repEV = 0, tossupEV = 0;
    var totalDem = 0, totalRep = 0, totalOther = 0;
    var locations = [], z = [], customdata = [];
    var signedMargins = [], demVotes = [], repVotes = [], otherVotes = [], evs = [], stateNames = [];

    rows.forEach(function (row) {
      var abbr = nameToAbbr[row.state];
      if (!abbr) return;

      var total = row.dem + row.rep + row.other;
      if (total <= 0) return;

      var half = shift / 2;
      var demPct = (row.dem / total) * 100 + half;
      var repPct = (row.rep / total) * 100 - half;
      var demAdj = Math.round(demPct / 100 * total);
      var repAdj = Math.round(repPct / 100 * total);

      totalDem += demAdj;
      totalRep += repAdj;
      totalOther += row.other;

      var signedMargin = demPct - repPct;
      var winner, zCode, winnerVotes;
      if (demAdj > repAdj) {
        winner = "Democratic"; zCode = -1; winnerVotes = demAdj; demEV += row.ev;
      } else if (repAdj > demAdj) {
        winner = "Republican"; zCode = 1;  winnerVotes = repAdj; repEV += row.ev;
      } else {
        winner = "Tossup"; zCode = 0; winnerVotes = 0; tossupEV += row.ev;
      }

      locations.push(abbr);
      z.push(zCode);
      customdata.push([winner, row.ev, Math.abs(signedMargin).toFixed(2), winnerVotes]);
      signedMargins.push(signedMargin);
      demVotes.push(demAdj);
      repVotes.push(repAdj);
      otherVotes.push(row.other);
      evs.push(row.ev);
      stateNames.push(row.state);
    });

    var totalVotes = totalDem + totalRep + totalOther || 1;
    var pvParty, pvMarginVal;
    if (totalDem >= totalRep) {
      pvParty = "Dem"; pvMarginVal = ((totalDem - totalRep) / totalVotes * 100).toFixed(1);
    } else {
      pvParty = "GOP"; pvMarginVal = ((totalRep - totalDem) / totalVotes * 100).toFixed(1);
    }

    return {
      locations: locations, z: z, customdata: customdata,
      demEV: demEV, repEV: repEV, tossupEV: tossupEV,
      pvParty: pvParty, pvMarginVal: pvMarginVal,
      signedMargins: signedMargins, demVotes: demVotes,
      repVotes: repVotes, otherVotes: otherVotes,
      evs: evs, stateNames: stateNames,
    };
  }

  function importCSV(file) {
    var year = extractYearFromFilename(file.name);
    if (!year) {
      alert(
        "Invalid file: \"" + file.name + "\"\n\n" +
        "Filename must contain a presidential election year (e.g. 1996, 2004, 2020).\n" +
        "Years must be divisible by 4 and between 1788–2100."
      );
      return;
    }

    var reader = new FileReader();
    reader.onload = function (e) {
      var rows = parseCSV(e.target.result);
      if (!rows) {
        alert(
          "Invalid CSV format.\n\n" +
          "File must have columns: State, EV, Democratic, Republican, Other"
        );
        return;
      }

      // Derive key from filename stem (strip .csv)
      var key = file.name.replace(/\.csv$/i, "");

      if (PER_STATE_BASELINE[key]) {
        if (!confirm("\"" + key + "\" is already loaded. Replace it?")) return;
      }

      // Read current slider range from the active slider steps
      var sliderSteps = plotDiv.layout.sliders[0].steps;
      var shifts = sliderSteps.map(function (s) { return parseInt(s.label, 10); });
      var zeroIdx = shifts.indexOf(0);

      var nameToAbbr = buildNameToAbbr();

      // Compute all frames
      var allFrames = shifts.map(function (s) {
        var frame = computeFrame(rows, s, nameToAbbr);
        frame.title = (
          key + " US Election Results \u2014 Margin Shift: " + s + " | " +
          "Dem " + frame.demEV + " - GOP " + frame.repEV +
          " - Tossup " + frame.tossupEV +
          " | PV: " + frame.pvParty + " +" + frame.pvMarginVal + "%"
        );
        return frame;
      });

      // Register in baseline for export
      var zeroFrame = allFrames[zeroIdx];
      PER_STATE_BASELINE[key] = {
        locations:      zeroFrame.locations,
        state_names:    zeroFrame.stateNames,
        signed_margins: zeroFrame.signedMargins,
        dem_votes:      zeroFrame.demVotes,
        rep_votes:      zeroFrame.repVotes,
        other_votes:    zeroFrame.otherVotes,
        evs:            zeroFrame.evs,
      };

      // Build slider steps for this election
      var newSliderSteps = allFrames.map(function (frame, i) {
        return {
          label: String(shifts[i]),
          method: "update",
          args: [
            { locations: [frame.locations], z: [frame.z], customdata: [frame.customdata] },
            { "title.text": frame.title },
          ],
        };
      });

      // Build year toggle button
      var newYearButton = {
        label: key,
        method: "update",
        args: [
          {
            locations:  [zeroFrame.locations],
            z:          [zeroFrame.z],
            customdata: [zeroFrame.customdata],
          },
          {
            "title.text":        zeroFrame.title,
            "sliders[0].steps":  newSliderSteps,
            "sliders[0].active": zeroIdx,
          },
        ],
      };

      // Add button to the year toggle updatemenu (always the last one)
      var menuIdx = plotDiv.layout.updatemenus.length - 1;
      var currentButtons = plotDiv.layout.updatemenus[menuIdx].buttons.slice();
      currentButtons.push(newYearButton);
      var relayoutUpdate = {};
      relayoutUpdate["updatemenus[" + menuIdx + "].buttons"] = currentButtons;
      Plotly.relayout(plotDiv, relayoutUpdate);
    };

    reader.readAsText(file);
  }

  // ---------------------------------------------------------------------------
  // Inject Import CSV + Export CSV buttons (top-right, side by side)
  // ---------------------------------------------------------------------------
  function addButtons() {
    // Hide default Plotly modebar to free up top-right space
    var style = document.createElement("style");
    style.textContent = ".modebar-container { display: none !important; }";
    document.head.appendChild(style);

    plotDiv.style.position = "relative";

    var btnStyle = (
      "padding:4px 12px;font-size:12px;font-weight:600;" +
      "cursor:pointer;background:#f5f5f5;border:1px solid #ccc;border-radius:3px;color:#444;"
    );

    // Hidden file input
    var fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.accept = ".csv";
    fileInput.style.display = "none";
    fileInput.addEventListener("change", function () {
      if (fileInput.files.length > 0) importCSV(fileInput.files[0]);
      fileInput.value = "";   // reset so same file can be re-imported
    });
    plotDiv.appendChild(fileInput);

    // Import button
    var importBtn = document.createElement("button");
    importBtn.textContent = "Import CSV";
    importBtn.title = "Import a CSV election file to add it to the map";
    importBtn.style.cssText = "position:absolute;top:6px;right:120px;z-index:1000;" + btnStyle;
    importBtn.onclick = function () { fileInput.click(); };
    plotDiv.appendChild(importBtn);

    // Export button
    var exportBtn = document.createElement("button");
    exportBtn.textContent = "Export CSV";
    exportBtn.title = "Export current election state as CSV";
    exportBtn.style.cssText = "position:absolute;top:6px;right:6px;z-index:1000;" + btnStyle;
    exportBtn.onclick = exportCurrentState;
    plotDiv.appendChild(exportBtn);
  }

  addButtons();
})();
