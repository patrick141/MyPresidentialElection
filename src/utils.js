// ---------------------------------------------------------------------------
// utils.js — pure utility functions shared by per_state_control.js
// No DOM access or Plotly calls here.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Presidential year validation (mirrors Election._validate_presidential_year)
// ---------------------------------------------------------------------------
function isPresidentialYear(year) {
  return year % 4 === 0 && year >= 1788 && year <= 2100;
}

// Mirrors Election._VALID_YEAR_RE: ((?:19|20)\d{2}) not surrounded by digits
function yearFromFilename(filename) {
  var m = filename.match(/(?<!\d)((?:19|20)\d{2})(?!\d)/);
  if (!m) return null;
  var y = parseInt(m[1], 10);
  return isPresidentialYear(y) ? y : null;
}

// ---------------------------------------------------------------------------
// CSV parsing (State, EV, Democratic, Republican, Other)
// ---------------------------------------------------------------------------
function parseElectionCSV(text) {
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
    rows.push({ state: c[si].trim(), ev: +c[ei]||0, dem: +c[di]||0,
                rep: +c[ri]||0, other: oi >= 0 ? (+c[oi]||0) : 0 });
  }
  return rows.length ? rows : null;
}

// ---------------------------------------------------------------------------
// Build a state-name → abbreviation map from PER_STATE_BASELINE
// ---------------------------------------------------------------------------
function buildNameToAbbrMap() {
  var map = {}, keys = Object.keys(PER_STATE_BASELINE);
  if (!keys.length) return map;
  var d = PER_STATE_BASELINE[keys[0]];
  d.state_names.forEach(function (n, i) { map[n] = d.locations[i]; });
  return map;
}

// ---------------------------------------------------------------------------
// Build all data for one shift frame from raw CSV rows (used by importCSV)
// ---------------------------------------------------------------------------
function buildImportFrame(rows, shift, nameToAbbr) {
  var dEV=0, rEV=0, tEV=0, dTot=0, rTot=0, oTot=0;
  var locs=[],z=[],cd=[],sm=[],dv=[],rv=[],ov=[],evs=[],names=[];

  rows.forEach(function (row) {
    var abbr = nameToAbbr[row.state]; if (!abbr) return;
    var tot = row.dem + row.rep + row.other; if (tot <= 0) return;
    var half = shift / 2;
    var dp = (row.dem/tot)*100 + half, rp = (row.rep/tot)*100 - half;
    var da = Math.round(dp/100*tot), ra = Math.round(rp/100*tot);
    dTot += da; rTot += ra; oTot += row.other;
    var sig = dp - rp, w, zc, wv;
    if (da > ra)      { w="Democratic"; zc=-1; wv=da; dEV+=row.ev; }
    else if (ra > da) { w="Republican"; zc=1;  wv=ra; rEV+=row.ev; }
    else              { w="Tossup";     zc=0;  wv=0;  tEV+=row.ev; }
    locs.push(abbr); z.push(zc); sm.push(sig);
    dv.push(da); rv.push(ra); ov.push(row.other); evs.push(row.ev); names.push(row.state);
    cd.push([w, row.ev, Math.abs(sig).toFixed(2), wv, ""]);
  });

  var tot = dTot+rTot+oTot||1;
  var pvP = dTot>=rTot ? "Dem" : "GOP";
  var pvM = (Math.abs(dTot-rTot)/tot*100).toFixed(1);
  return { locs, z, cd, dEV, rEV, tEV, pvP, pvM, sm, dv, rv, ov, evs, names };
}

// ---------------------------------------------------------------------------
// EC-based tipping point (mirrors Python get_tipping_point_state)
//
// computeTPAbbr — live map (uses stateOverrides + nationalShift from closure)
// tpFromImportFrame — imported election frame (self-contained data)
// ---------------------------------------------------------------------------

// Called during live computeAndRestyle; requires outer nationalShift + stateOverrides.
// extraDemEV / extraRepEV add district EVs that are not in data.locations.
function computeTPAbbr(data, z, nationalShift, stateOverrides, extraDemEV, extraRepEV) {
  var demEV = (extraDemEV || 0), repEV = (extraRepEV || 0);
  data.locations.forEach(function (loc, i) {
    if (z[i] === -1) demEV += data.evs[i];
    else if (z[i] === 1) repEV += data.evs[i];
  });
  var ecCode = demEV >= 270 ? -1 : repEV >= 270 ? 1 : 0;
  if (ecCode === 0) return "";

  var cands = [];
  data.locations.forEach(function (loc, i) {
    if (z[i] === ecCode) {
      var absMarg = Math.abs(data.signed_margins[i] + nationalShift + (stateOverrides[loc]||0));
      cands.push({ loc: loc, ev: data.evs[i], margin: absMarg });
    }
  });
  cands.sort(function (a, b) { return b.margin - a.margin; });
  var ev = 0;
  for (var i = 0; i < cands.length; i++) {
    ev += cands[i].ev;
    if (ev >= 270) return cands[i].loc;
  }
  return "";
}

// Called when building import frames; data is fully contained in the frame.
function tpFromImportFrame(frame) {
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
