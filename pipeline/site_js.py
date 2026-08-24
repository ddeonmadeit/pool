"""Client logic for the SDL Finder site.

The whole lead set ships inline as a compact array-of-arrays and the table is
virtualised, so all 11,000+ rows are searchable and scrollable while only the
~40 rows actually on screen ever exist in the DOM. That is what keeps the page
instant at full size rather than capping the list.

Outreach state lives in localStorage keyed by pool id, with JSON export/import
so it can be backed up or moved between machines.
"""

JS = r"""
(function () {
  var DATA = JSON.parse(document.getElementById("lead-data").textContent);
  // Why a lead is held back, indexed by bit position in qualify.BLOCK_ORDER.
  var BLOCK_TEXT = JSON.parse(document.getElementById("block-reasons").textContent);
  var ROW_H = 48, OVER = 8, KEY = "sdlfinder-tracking-v1";
  var ORDER = ["new", "mailed", "replied", "quoted", "won", "dead"];
  var LABEL = { new: "Not contacted", mailed: "Mailed", replied: "Replied",
                quoted: "Quoted", won: "Won", dead: "Not interested" };
  // Column order in each packed record.
  var A = 0, S = 1, PC = 2, YR = 3, SC = 4, CF = 5, AR = 6, LOT = 7,
      NP = 8, MQ = 9, LAT = 10, LON = 11, CON = 12, CD = 13, EV = 14,
      MR = 15, MB = 16;
  // Pool condition codes, mirroring CONDITION_CODE in build_site.py.
  var COND = [["Green water", "c0"], ["Original look", "c1"],
              ["Redone pre-2005", "c2"], ["Mid tone", "c3"],
              ["Modern dark", "c4"], ["Unconfirmed", "c5"],
              ["Not visible", "c6"]];
  // The two states worth posting to: never resurfaced, or visibly neglected.
  // "Prime" is that judgement alone; "mail-ready" (MR) additionally requires
  // every evidence check in qualify.py to have come back clean.
  var PRIME = [0, 1];
  var ERA = { 1978: ["pre-1979", "e78"], 1986: ["1979-86", "e86"],
              1991: ["1987-91", "e91"], 1998: ["1992-98", "e98"],
              2005: ["1999-2005", "e05"] };
  var NOW = new Date().getFullYear();

  // Unpack a lead's block bitmask into the reasons it carries.
  function blockText(mask) {
    if (!mask) return "";
    var out = [];
    for (var i = 0; i < BLOCK_TEXT.length; i++) {
      if (mask & (1 << i)) out.push(BLOCK_TEXT[i]);
    }
    return out.join("; ");
  }

  var track = {};
  try { track = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { track = {}; }

  var view = [];                       // indices into DATA, after filter+sort
  var sortKey = "score", sortDir = -1;

  var scroller = document.getElementById("scroller");
  var tbody = document.getElementById("tb");
  var padTop = document.getElementById("pad-top");
  var padBot = document.getElementById("pad-bot");
  var empty = document.getElementById("empty");

  function statusOf(i) { var t = track[i]; return (t && t.s) || "new"; }
  function noteOf(i) { var t = track[i]; return (t && t.n) || ""; }

  function persist() {
    try { localStorage.setItem(KEY, JSON.stringify(track)); }
    catch (e) { flash("Could not save on this device"); }
  }

  var flashT;
  function flash(msg) {
    var el = document.getElementById("saved");
    el.textContent = msg;
    clearTimeout(flashT);
    flashT = setTimeout(function () { el.textContent = ""; }, 1800);
  }

  function fmtMoney(n) {
    if (n >= 1000000) return "$" + (n / 1000000).toFixed(n % 1000000 === 0 ? 0 : 1) + "M";
    return "$" + Math.round(n / 1000) + "K";
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  // ── filtering ──────────────────────────────────────────────────
  var CENTROIDS = JSON.parse(document.getElementById("centroid-data").textContent);
  var q = document.getElementById("q"), fSub = document.getElementById("f-sub"),
      fEra = document.getElementById("f-era"), fSt = document.getElementById("f-st"),
      fCon = document.getElementById("f-con"),
      fAgeMin = document.getElementById("f-age-min"), fAgeMax = document.getElementById("f-age-max"),
      fCond = document.getElementById("f-cond"), fValue = document.getElementById("f-value"),
      fCenter = document.getElementById("f-center"), fRadius = document.getElementById("f-radius"),
      geoBtn = document.getElementById("geo");

  // Radius search state. centerPos is null until a suburb or "Use my location"
  // gives us somewhere to measure from; distances are only meaningful then.
  var centerPos = null, centerLabel = "";

  function haversineKm(lat1, lon1, lat2, lon2) {
    var R = 6371, toRad = Math.PI / 180;
    var dLat = (lat2 - lat1) * toRad, dLon = (lon2 - lon1) * toRad;
    var a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(lat1 * toRad) * Math.cos(lat2 * toRad) *
      Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }

  function distKm(i) {
    if (!centerPos) return null;
    var d = DATA[i];
    return haversineKm(centerPos[0], centerPos[1], d[LAT], d[LON]);
  }

  function setCenter(pos, label) {
    centerPos = pos;
    centerLabel = label;
    document.getElementById("near-label").textContent = pos ? "Near " + label : "";
  }

  fCenter.addEventListener("change", function () {
    var name = fCenter.value;
    if (!name) { setCenter(null, ""); rebuild(); return; }
    var c = CENTROIDS[name];
    if (c) setCenter(c, name);
    rebuild();
  });

  geoBtn.addEventListener("click", function () {
    if (!navigator.geolocation) { flash("Location not available in this browser"); return; }
    geoBtn.textContent = "Locating…";
    navigator.geolocation.getCurrentPosition(function (pos) {
      geoBtn.textContent = "Use my location";
      fCenter.value = "";
      setCenter([pos.coords.latitude, pos.coords.longitude], "your location");
      rebuild();
    }, function () {
      geoBtn.textContent = "Use my location";
      flash("Location request denied or unavailable");
    }, { timeout: 8000 });
  });

  function rebuild() {
    var term = q.value.trim().toLowerCase();
    var sub = fSub.value, era = fEra.value, st = fSt.value, con = fCon.value;
    var cond = fCond.value;
    var minValue = fValue.value ? parseInt(fValue.value, 10) : null;
    var ageMin = fAgeMin.value ? parseInt(fAgeMin.value, 10) : null;
    var ageMax = fAgeMax.value ? parseInt(fAgeMax.value, 10) : null;
    var radius = (centerPos && fRadius.value) ? parseFloat(fRadius.value) : null;
    var out = [];
    for (var i = 0; i < DATA.length; i++) {
      var d = DATA[i];
      if (cond === "mail") { if (!d[MR]) continue; }
      else if (cond === "prime") { if (PRIME.indexOf(d[CD]) === -1) continue; }
      else if (cond !== "" && String(d[CD]) !== cond) continue;
      if (minValue != null && d[EV] < minValue) continue;
      if (sub && d[S] !== sub) continue;
      if (era && String(d[YR]) !== era) continue;
      if (st && statusOf(i) !== st) continue;
      if (con && !d[CON]) continue;
      if (ageMin != null && (NOW - d[YR]) < ageMin) continue;
      if (ageMax != null && (NOW - d[YR]) > ageMax) continue;
      if (radius != null && distKm(i) > radius) continue;
      if (term) {
        var hay = (d[A] + " " + d[S] + " " + (d[PC] || "")).toLowerCase();
        if (hay.indexOf(term) === -1) continue;
      }
      out.push(i);
    }
    var dir = sortDir;
    if (sortKey === "score") out.sort(function (a, b) { return (DATA[a][SC] - DATA[b][SC]) * dir; });
    else if (sortKey === "age") out.sort(function (a, b) { return (DATA[a][YR] - DATA[b][YR]) * dir; });
    else if (sortKey === "lot") out.sort(function (a, b) { return (DATA[a][LOT] - DATA[b][LOT]) * dir; });
    else if (sortKey === "area") out.sort(function (a, b) { return (DATA[a][AR] - DATA[b][AR]) * dir; });
    else if (sortKey === "distance") out.sort(function (a, b) {
      var da = distKm(a), db = distKm(b);
      if (da == null && db == null) return 0;
      if (da == null) return 1; if (db == null) return -1;
      return (da - db) * dir; });
    else if (sortKey === "cond") out.sort(function (a, b) {
      return (DATA[a][CD] - DATA[b][CD]) * dir; });
    else if (sortKey === "value") out.sort(function (a, b) {
      return (DATA[a][EV] - DATA[b][EV]) * dir; });
    else if (sortKey === "suburb") out.sort(function (a, b) {
      return DATA[a][S] < DATA[b][S] ? -dir : DATA[a][S] > DATA[b][S] ? dir : 0; });
    view = out;
    scroller.scrollTop = 0;
    render();
    counts();
  }

  // ── virtual rendering ──────────────────────────────────────────
  function render() {
    var total = view.length;
    var top = scroller.scrollTop;
    var vis = Math.ceil(scroller.clientHeight / ROW_H) + OVER * 2;
    var start = Math.max(0, Math.floor(top / ROW_H) - OVER);
    var end = Math.min(total, start + vis);

    padTop.style.height = (start * ROW_H) + "px";
    padBot.style.height = Math.max(0, (total - end) * ROW_H) + "px";
    empty.hidden = total !== 0;

    var html = "";
    for (var k = start; k < end; k++) {
      var i = view[k], d = DATA[i];
      var era = ERA[d[YR]] || ["unknown", "e05"];
      var age = NOW - d[YR];
      var stt = statusOf(i);
      var multi = d[NP] > 1 ? '<span class="tag" title="' + d[NP] +
          ' pools mapped on this property">x' + d[NP] + '</span>' : "";
      var approx = d[MQ] === 1 ? '<span class="approx" title="Matched to the nearest parcel, not one containing the pool — check the map link">~</span>' : "";
      // Only the held-back leads are marked. In the default mail-ready view every
      // row would otherwise carry an identical "post" tag, which says nothing and
      // pushes itself off the end of a long address.
      var hold = d[MR] ? "" :
        '<span class="tag hold" title="' + esc(blockText(d[MB])) + '">hold</span>';
      var meta = esc(d[S]) + (d[PC] ? " · " + d[PC] : "");
      if (d[CON]) meta += " · " + d[CON];
      var cd = COND[d[CD]] || COND[4];
      var valStr = d[EV] > 0 ? fmtMoney(d[EV]) : "&mdash;";
      var dk = distKm(i);
      var distStr = dk == null ? "—" : (dk < 10 ? dk.toFixed(1) : Math.round(dk)) + " km";
      html += '<tr class="lead" data-i="' + i + '" data-s="' + stt + '">' +
        '<td><span class="addr">' + esc(d[A]) + approx + multi + hold + '</span>' +
        '<span class="meta">' + meta + '</span></td>' +
        '<td><span class="pill ' + era[1] + '">' + era[0] + '</span>' +
        '<span class="ago">' + age + '+ yr</span></td>' +
        '<td><span class="pill ' + cd[1] + '">' + cd[0] + '</span></td>' +
        '<td class="num val">' + valStr + '</td>' +
        '<td class="num">' + d[AR] + '</td>' +
        '<td class="num">' + d[LOT] + '</td>' +
        '<td class="num dist">' + distStr + '</td>' +
        '<td class="score">' + d[SC] + '</td>' +
        '<td class="num">' + (d[CF] / 100).toFixed(2) + '</td>' +
        '<td><button type="button" class="st">' + LABEL[stt] + '</button></td>' +
        '<td><input class="note" type="text" placeholder="note" value="' +
        esc(noteOf(i)) + '" aria-label="Note for ' + esc(d[A]) + '"></td>' +
        '<td><a class="maplink" target="_blank" rel="noopener" href="https://www.google.com/maps/search/?api=1&query=' +
        d[LAT] + ',' + d[LON] + '">map</a></td></tr>';
    }
    tbody.innerHTML = html;
  }

  var raf = null;
  scroller.addEventListener("scroll", function () {
    if (raf) return;
    raf = requestAnimationFrame(function () { raf = null; render(); });
  });
  window.addEventListener("resize", render);

  // ── stats ──────────────────────────────────────────────────────
  function counts() {
    var c = { new: 0, mailed: 0, replied: 0, quoted: 0, won: 0, dead: 0 };
    for (var i = 0; i < DATA.length; i++) c[statusOf(i)]++;
    ["mailed", "replied", "quoted", "won"].forEach(function (k) {
      document.getElementById("k-" + k).textContent = c[k].toLocaleString();
    });
    document.getElementById("k-new").textContent = c.new.toLocaleString();
    document.getElementById("k-shown").textContent = view.length.toLocaleString();
    document.getElementById("tally").textContent = view.length.toLocaleString() +
      " of " + DATA.length.toLocaleString() + " shown";
  }

  // ── interaction ────────────────────────────────────────────────
  tbody.addEventListener("click", function (ev) {
    var b = ev.target.closest(".st");
    if (!b) return;
    var tr = b.closest("tr.lead"), i = +tr.dataset.i;
    var n = ORDER.indexOf(statusOf(i));
    n = (n + (ev.shiftKey ? ORDER.length - 1 : 1)) % ORDER.length;
    var st = ORDER[n];
    var rec = track[i] || (track[i] = {});
    rec.s = st;
    if (st === "new" && !rec.n) delete track[i];
    tr.dataset.s = st;
    b.textContent = LABEL[st];
    persist();
    counts();
    if (fSt.value) rebuild();
  });

  var noteT;
  tbody.addEventListener("input", function (ev) {
    if (!ev.target.classList.contains("note")) return;
    var tr = ev.target.closest("tr.lead"), i = +tr.dataset.i;
    var v = ev.target.value;
    var rec = track[i] || (track[i] = {});
    rec.n = v;
    if (!v && (!rec.s || rec.s === "new")) delete track[i];
    clearTimeout(noteT);
    noteT = setTimeout(function () { persist(); flash("Saved"); }, 450);
  });

  [q, fSub, fEra, fSt, fCon, fCond, fValue, fAgeMin, fAgeMax, fRadius].forEach(function (el) {
    el.addEventListener("input", rebuild);
    el.addEventListener("change", rebuild);
  });
  document.getElementById("reset").addEventListener("click", function () {
    q.value = ""; fSub.value = ""; fEra.value = ""; fSt.value = ""; fCon.value = "";
    fCond.value = "mail"; fValue.value = "2000000";
    fAgeMin.value = ""; fAgeMax.value = ""; fRadius.value = ""; fCenter.value = "";
    setCenter(null, "");
    rebuild();
  });

  document.querySelectorAll("th.sortable").forEach(function (th) {
    th.addEventListener("click", function () {
      var k = th.dataset.sort;
      if (sortKey === k) sortDir = -sortDir;
      else { sortKey = k; sortDir = (k === "suburb" || k === "distance") ? 1 : -1; }
      document.querySelectorAll("th .ind").forEach(function (s) { s.textContent = ""; });
      var ind = th.querySelector(".ind");
      if (ind) ind.textContent = sortDir < 0 ? "▼" : "▲";
      rebuild();
    });
  });

  // ── backup ─────────────────────────────────────────────────────
  document.getElementById("export").addEventListener("click", function () {
    var rows = [["address", "suburb", "postcode", "pool_built_by", "min_age_years",
                 "condition", "est_value", "score", "mail_ready", "held_back_because",
                 "status", "note"]];
    for (var i = 0; i < DATA.length; i++) {
      var t = track[i];
      if (!t) continue;
      var d = DATA[i];
      rows.push([d[A], d[S], d[PC] || "", d[YR], NOW - d[YR],
                 (COND[d[CD]] || COND[4])[0], d[EV] || "", d[SC],
                 d[MR] ? "yes" : "no", blockText(d[MB]),
                 t.s || "new", (t.n || "").replace(/"/g, "'")]);
    }
    if (rows.length === 1) { flash("Nothing tracked yet"); return; }
    var csv = rows.map(function (r) {
      return r.map(function (c) { return '"' + String(c) + '"'; }).join(",");
    }).join("\n");
    navigator.clipboard.writeText(csv).then(
      function () { flash("Tracking CSV copied to clipboard — " + (rows.length - 1) + " rows"); },
      function () { flash("Clipboard blocked by browser"); }
    );
  });

  document.getElementById("backup").addEventListener("click", function () {
    navigator.clipboard.writeText(JSON.stringify(track)).then(
      function () { flash("Backup JSON copied — paste somewhere safe"); },
      function () { flash("Clipboard blocked by browser"); }
    );
  });

  document.getElementById("restore").addEventListener("click", function () {
    var raw = window.prompt("Paste a backup JSON to restore your tracking:");
    if (!raw) return;
    try {
      var incoming = JSON.parse(raw);
      if (typeof incoming !== "object" || incoming === null) throw new Error("bad");
      Object.keys(incoming).forEach(function (k) { track[k] = incoming[k]; });
      persist(); rebuild();
      flash("Restored " + Object.keys(incoming).length + " tracked leads");
    } catch (e) { flash("That did not look like a backup"); }
  });

  rebuild();
})();
"""
