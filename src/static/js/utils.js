// ---------------------------------------------------------------------------
// utils.js — pure utility functions shared by per_state_control.js
// No DOM access or Plotly calls here.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Presidential year validation
// Mirrors Election._validate_presidential_year in election.py
// ---------------------------------------------------------------------------
function isPresidentialYear(year) {
  // Returns true if the year falls on a valid U.S. presidential election cycle
  return year % 4 === 0 && year >= 1788 && year <= 2100;
}

// Mirrors Election._VALID_YEAR_RE: extracts a 19xx/20xx year not surrounded by digits
function yearFromFilename(filename) {
  // Returns the presidential year embedded in the filename, or null if none found
  var m = filename.match(/(?<!\d)((?:19|20)\d{2})(?!\d)/);
  if (!m) return null;
  var y = parseInt(m[1], 10);
  return isPresidentialYear(y) ? y : null;
}

// ---------------------------------------------------------------------------
// CSV parsing
// Expected columns: State, EV, Democratic, Republican, Other
// ---------------------------------------------------------------------------
function parseElectionCSV(text) {
  // Parses a CSV string into an array of row objects; returns null if headers are invalid
  var lines = text.trim().split(/\r?\n/);
  if (lines.length < 2) return null;
  var hdr = lines[0].split(",").map(function (s) { return s.trim().toLowerCase(); });
  var si = hdr.indexOf("state"), ei = hdr.indexOf("ev"),
      di = hdr.indexOf("democratic"), ri = hdr.indexOf("republican"),
      oi = hdr.indexOf("other");
  if (si < 0 || ei < 0 || di < 0 || ri < 0) return null;
  var rows = [];
  for (var i = 1; i < lines.length; i++) {
    var c = lines[i].trim().split(",");
    if (c.length < 4) continue;
    // Coerce vote columns to numbers; fall back to 0 for empty or missing values
    rows.push({ state: c[si].trim(), ev: +c[ei]||0, dem: +c[di]||0,
                rep: +c[ri]||0, other: oi >= 0 ? (+c[oi]||0) : 0 });
  }
  return rows.length ? rows : null;
}

// ---------------------------------------------------------------------------
// Build a state-name → abbreviation map from PER_STATE_BASELINE
// Used by importCSV to match CSV "State" column values to choropleth location codes
// ---------------------------------------------------------------------------
function buildNameToAbbrMap() {
  // Reads state_names and locations from the first baseline entry to build the lookup
  var map = {}, keys = Object.keys(PER_STATE_BASELINE);
  if (!keys.length) return map;
  var d = PER_STATE_BASELINE[keys[0]];
  d.state_names.forEach(function (n, i) { map[n] = d.locations[i]; });
  return map;
}

// ---------------------------------------------------------------------------
// Build all data for one shift frame from raw CSV rows
// Called by importCSV for each slider step of a newly imported election
// ---------------------------------------------------------------------------
function buildImportFrame(rows, shift, nameToAbbr) {
  // Computes EV totals, z-codes, margins, and customdata for a given national shift
  var dEV=0, rEV=0, tEV=0, dTot=0, rTot=0, oTot=0;
  var locs=[],z=[],cd=[],sm=[],dv=[],rv=[],ov=[],evs=[],names=[];

  rows.forEach(function (row) {
    var abbr = nameToAbbr[row.state]; if (!abbr) return;
    var tot = row.dem + row.rep + row.other; if (tot <= 0) return;
    // Apply the national shift as ±half to each party's percentage share
    var half = shift / 2;
    var dp = (row.dem/tot)*100 + half, rp = (row.rep/tot)*100 - half;
    var da = Math.round(dp/100*tot), ra = Math.round(rp/100*tot);
    dTot += da; rTot += ra; oTot += row.other;
    var sig = dp - rp, w, zc, wv;
    // Determine winner and assign z-code and EV for this state
    if (da > ra)      { w="Democratic"; zc=-1; wv=da; dEV+=row.ev; }
    else if (ra > da) { w="Republican"; zc=1;  wv=ra; rEV+=row.ev; }
    else              { w="Tossup";     zc=0;  wv=0;  tEV+=row.ev; }
    locs.push(abbr); z.push(zc); sm.push(sig);
    dv.push(da); rv.push(ra); ov.push(row.other); evs.push(row.ev); names.push(row.state);
    cd.push([w, row.ev, Math.abs(sig).toFixed(2), wv, ""]);
  });

  // Compute popular vote party and margin from accumulated totals
  var tot = dTot+rTot+oTot||1;
  var pvP = dTot>=rTot ? "Dem" : "GOP";
  var pvM = (Math.abs(dTot-rTot)/tot*100).toFixed(1);
  return { locs, z, cd, dEV, rEV, tEV, pvP, pvM, sm, dv, rv, ov, evs, names };
}

// ---------------------------------------------------------------------------
// EC-based tipping point calculation
// Mirrors Python get_tipping_point_state — sorts winner states safest-first,
// accumulates EVs until 270 is reached, and returns that state's abbreviation.
// ---------------------------------------------------------------------------

// Called during live computeAndRestyle; requires the outer nationalShift + stateOverrides.
// extraDemEV / extraRepEV fold in district EVs that are not in data.locations.
function computeTPAbbr(data, z, nationalShift, stateOverrides, extraDemEV, extraRepEV) {
  // Seed EV accumulators with district EVs so the 270-check is complete
  var demEV = (extraDemEV || 0), repEV = (extraRepEV || 0);
  data.locations.forEach(function (loc, i) {
    if (z[i] === -1) demEV += data.evs[i];
    else if (z[i] === 1) repEV += data.evs[i];
  });
  // Determine which party (if any) has an EC majority
  var ecCode = demEV >= 270 ? -1 : repEV >= 270 ? 1 : 0;
  if (ecCode === 0) return "";

  // Collect winner's states with their effective margin (baseline + national + per-state override)
  var cands = [];
  data.locations.forEach(function (loc, i) {
    if (z[i] === ecCode) {
      var absMarg = Math.abs(data.signed_margins[i] + nationalShift + (stateOverrides[loc]||0));
      cands.push({ loc: loc, ev: data.evs[i], margin: absMarg });
    }
  });
  // Sort safest-first (largest margin first), then walk until 270 is reached
  cands.sort(function (a, b) { return b.margin - a.margin; });
  var ev = 0;
  for (var i = 0; i < cands.length; i++) {
    ev += cands[i].ev;
    if (ev >= 270) return cands[i].loc;
  }
  return "";
}

// Called when building import frames; all data is self-contained in the frame object
function tpFromImportFrame(frame) {
  // Determines the tipping point abbreviation from a fully pre-computed import frame
  var ec = frame.dEV>=270 ? -1 : frame.rEV>=270 ? 1 : 0;
  if (!ec) return "";
  var cands = [];
  frame.locs.forEach(function (loc, i) {
    if (frame.z[i] === ec)
      cands.push({ loc: loc, ev: frame.evs[i], margin: Math.abs(frame.sm[i]) });
  });
  cands.sort(function (a, b) { return b.margin - a.margin; });
  var ev = 0;
  for (var i = 0; i < cands.length; i++) {
    ev += cands[i].ev;
    if (ev >= 270) return cands[i].loc;
  }
  return "";
}
