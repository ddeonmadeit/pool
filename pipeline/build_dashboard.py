"""Render the outreach dashboard and the CSV extracts from leads.json."""
import csv
import html
import json
import os
import sys
from collections import Counter
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
DASH = os.path.join(HERE, "..", "dashboard")

MAX_ROWS = int(os.environ.get("DASH_ROWS", "2500"))

ERA = [
    (1978, "pre-1979", "e78"),
    (1986, "1979-86", "e86"),
    (1991, "1987-91", "e91"),
    (1998, "1992-98", "e98"),
    (2005, "1999-2005", "e05"),
]


def era_of(year):
    for y, label, cls in ERA:
        if year == y:
            return label, cls
    return "unknown", "eun"


def write_csvs(leads):
    cols = ["address", "suburb", "earliest_confirmed_year", "min_age_years",
            "lead_score", "age_confidence", "address_match", "area_m2",
            "lot_m2", "length_m", "width_m", "rect_fill", "category",
            "contact_name", "contact_phone", "contact_email", "contact_website",
            "postcode", "council", "pools_at_address", "lat", "lon", "osm_id"]
    for p in leads:
        c = p.get("contact") or {}
        p["contact_name"] = c.get("name", "")
        p["contact_phone"] = c.get("phone") or c.get("mobile") or ""
        p["contact_email"] = c.get("email", "")
        p["contact_website"] = c.get("website", "")
    full = os.path.join(DATA, "leads_full.csv")
    with open(full, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for p in leads:
            w.writerow(p)
    mail = os.path.join(DATA, "mail_merge.csv")
    with open(mail, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Address", "Suburb", "State", "Postcode",
                    "PoolAgeYearsMin", "PoolBuiltBefore", "LeadScore"])
        for p in leads:
            w.writerow([p.get("address", ""), p.get("suburb", ""), "NSW",
                        p.get("postcode", "") or "",
                        p.get("min_age_years", ""),
                        p.get("earliest_confirmed_year", ""),
                        p.get("lead_score", "")])
    return full, mail


def row_html(p, i):
    year = p.get("earliest_confirmed_year")
    label, cls = era_of(year)
    addr = html.escape(p.get("address") or "")
    sub = html.escape(p.get("suburb") or "")
    age = p.get("min_age_years") or 0
    score = p.get("lead_score") or 0
    lot = p.get("lot_m2") or 0
    area = p.get("area_m2") or 0
    conf = p.get("age_confidence") or 0
    lat, lon = p.get("lat"), p.get("lon")
    maps = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"

    c = p.get("contact") or {}
    bits = []
    if c.get("name"):
        bits.append(f'<b>{html.escape(str(c["name"]))}</b>')
    tel = c.get("phone") or c.get("mobile")
    if tel:
        t = html.escape(str(tel))
        bits.append(f'<a href="tel:{t.replace(" ", "")}">{t}</a>')
    if c.get("email"):
        em = html.escape(str(c["email"]))
        bits.append(f'<a href="mailto:{em}">{em}</a>')
    if c.get("website"):
        ws = html.escape(str(c["website"]))
        bits.append(f'<a href="{ws}" target="_blank" rel="noopener">site</a>')
    contact = (" &middot; " + " &middot; ".join(bits)) if bits else ""
    has_contact = "1" if bits else "0"
    npools = p.get("pools_at_address") or 1
    multi = (f'<span class="multi" title="{npools} pools mapped on this '
             f'property">x{npools}</span>') if npools > 1 else ""
    pcode = f' &middot; {p["postcode"]}' if p.get("postcode") else ""
    approx = ('<span class="approx" title="Matched to the closest parcel, '
              'not one containing the pool - check the map link">~</span>'
              if p.get("address_match") == "nearby" else "")

    return f"""<tr class="row {cls}" data-status="new" data-key="{html.escape(p['osm_id'])}" data-suburb="{sub}" data-era="{cls}" data-score="{score}" data-contact="{has_contact}">
<td class="c-addr"><span class="addr">{addr}{approx}{multi}</span><span class="sub">{sub}{pcode}{contact}</span></td>
<td class="c-era"><span class="chip {cls}">{label}</span> <span class="age">{age}+</span></td>
<td class="c-num">{area:.0f}</td>
<td class="c-num">{lot:.0f}</td>
<td class="c-num sc">{score:.0f}</td>
<td class="c-conf">{conf:.2f}</td>
<td class="c-status"><button type="button" class="cyc">Not contacted</button></td>
<td class="c-note"><input class="note" type="text" placeholder="note" aria-label="Note for {addr}" value=""></td>
<td class="c-link"><a href="{maps}" target="_blank" rel="noopener">map</a></td>
</tr>"""


def build(leads, stats):
    rows = "\n".join(row_html(p, i) for i, p in enumerate(leads[:MAX_ROWS]))
    subs = sorted({p.get("suburb") for p in leads[:MAX_ROWS] if p.get("suburb")})
    subopts = "\n".join(
        f'<option value="{html.escape(s)}">{html.escape(s)}</option>' for s in subs)
    total_all = stats["qualified_total"]
    shown = min(len(leads), MAX_ROWS)
    gen = stats["generated"]
    era_counts = stats["era_counts"]
    ec = " ".join(
        f'<span class="lg {cls}"><i></i>{label} <b>{era_counts.get(y,0):,}</b></span>'
        for y, label, cls in ERA)

    return f"""<title>Poolside Ledger</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" media="print" onload="this.media='all'" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=Public+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<noscript><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=Public+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap"></noscript>
<style>
:root {{
  --ground:#EDF1F2; --surface:#FFFFFF; --surface-2:#F5F8F8; --line:#D2DDDE;
  --ink:#12262B; --ink-2:#41595E; --ink-3:#6F878B;
  --accent:#0E7C8E; --accent-soft:#D5EAEE;
  --e78:#9C3A22; --e86:#B4633A; --e91:#A8842E; --e98:#4E8A5E; --e05:#3F7E93;
  --st-mailed:#B07C1E; --st-replied:#2F7BA6; --st-quoted:#6B4FA8;
  --st-won:#2E7D52; --st-dead:#8A9599;
  --shadow:0 1px 2px rgba(18,38,43,.06),0 4px 14px rgba(18,38,43,.05);
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --ground:#0B1618; --surface:#111F22; --surface-2:#16282C; --line:#24393D;
    --ink:#DDE8E9; --ink-2:#9DB2B5; --ink-3:#7A9094;
    --accent:#41B6C9; --accent-soft:#123239;
    --e78:#E0714C; --e86:#DE8F5C; --e91:#D4AE52; --e98:#6DBE83; --e05:#63AEC6;
    --st-mailed:#D9A63F; --st-replied:#5CA8D4; --st-quoted:#9B84D6;
    --st-won:#54B37F; --st-dead:#6E8085;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 6px 18px rgba(0,0,0,.3);
  }}
}}
:root[data-theme="dark"] {{
  --ground:#0B1618; --surface:#111F22; --surface-2:#16282C; --line:#24393D;
  --ink:#DDE8E9; --ink-2:#9DB2B5; --ink-3:#7A9094;
  --accent:#41B6C9; --accent-soft:#123239;
  --e78:#E0714C; --e86:#DE8F5C; --e91:#D4AE52; --e98:#6DBE83; --e05:#63AEC6;
  --st-mailed:#D9A63F; --st-replied:#5CA8D4; --st-quoted:#9B84D6;
  --st-won:#54B37F; --st-dead:#6E8085;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 6px 18px rgba(0,0,0,.3);
}}
* {{ box-sizing:border-box; }}
body {{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:"Public Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  font-size:14px; line-height:1.5;
}}
.wrap {{ max-width:1500px; margin:0 auto; padding:26px 20px 70px; }}
header.top {{ display:flex; flex-wrap:wrap; gap:18px; align-items:flex-end;
  justify-content:space-between; margin-bottom:20px; }}
h1 {{ font-family:"Archivo",sans-serif; font-weight:700; font-size:27px;
  letter-spacing:-.015em; margin:0 0 4px; text-wrap:balance; }}
.sub1 {{ color:var(--ink-2); font-size:13.5px; max-width:62ch; margin:0; }}
.meta {{ font-family:"IBM Plex Mono",monospace; font-size:11.5px;
  color:var(--ink-3); text-align:right; line-height:1.7; }}

.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(132px,1fr));
  gap:10px; margin-bottom:16px; }}
.stat {{ background:var(--surface); border:1px solid var(--line); border-radius:7px;
  padding:11px 13px; box-shadow:var(--shadow); }}
.stat .k {{ font-size:10.5px; text-transform:uppercase; letter-spacing:.09em;
  color:var(--ink-3); font-weight:600; }}
.stat .v {{ font-family:"IBM Plex Mono",monospace; font-variant-numeric:tabular-nums;
  font-size:25px; font-weight:600; line-height:1.25; margin-top:3px; }}
.stat.s-mailed .v {{ color:var(--st-mailed); }}
.stat.s-replied .v {{ color:var(--st-replied); }}
.stat.s-won .v {{ color:var(--st-won); }}
.stat.s-left .v {{ color:var(--accent); }}

.legend {{ display:flex; flex-wrap:wrap; gap:14px; margin:0 0 16px;
  font-size:11.5px; color:var(--ink-2); font-family:"IBM Plex Mono",monospace; }}
.lg {{ display:inline-flex; align-items:center; gap:6px; }}
.lg i {{ width:9px; height:9px; border-radius:2px; display:inline-block; }}
.lg b {{ color:var(--ink); font-weight:600; }}
.lg.e78 i {{ background:var(--e78); }} .lg.e86 i {{ background:var(--e86); }}
.lg.e91 i {{ background:var(--e91); }} .lg.e98 i {{ background:var(--e98); }}
.lg.e05 i {{ background:var(--e05); }}

.controls {{ display:flex; flex-wrap:wrap; gap:9px; align-items:center;
  background:var(--surface); border:1px solid var(--line); border-radius:8px;
  padding:11px 12px; margin-bottom:14px; box-shadow:var(--shadow);
  position:sticky; top:0; z-index:20; }}
.controls input[type=search], .controls select {{
  font-family:"Public Sans",sans-serif; font-size:13px; color:var(--ink);
  background:var(--surface-2); border:1px solid var(--line); border-radius:6px;
  padding:7px 10px; }}
.controls input[type=search] {{ min-width:230px; flex:1 1 230px; }}
.controls label {{ font-size:11px; text-transform:uppercase; letter-spacing:.08em;
  color:var(--ink-3); font-weight:600; }}
.pill {{ font-family:"IBM Plex Mono",monospace; font-size:11.5px; color:var(--ink-2);
  background:var(--surface-2); border:1px solid var(--line);
  border-radius:20px; padding:5px 11px; }}
button.act {{ font-family:"Public Sans",sans-serif; font-size:12.5px; font-weight:600;
  color:var(--ink); background:var(--surface-2); border:1px solid var(--line);
  border-radius:6px; padding:7px 12px; cursor:pointer; }}
button.act:hover {{ border-color:var(--accent); color:var(--accent); }}

.tablewrap {{ overflow-x:auto; background:var(--surface); border:1px solid var(--line);
  border-radius:8px; box-shadow:var(--shadow); }}
/* A 2,500-row auto-layout table forces the browser to measure every cell in
   every column before it can paint. Fixing the layout and declaring the column
   widths removes that pass entirely, and content-visibility lets it skip the
   rows that are scrolled out of view. Together these take first paint from
   ~14s to well under a second. */
table {{ border-collapse:collapse; width:100%; min-width:1120px;
  table-layout:fixed; }}
tbody tr {{ content-visibility:auto; contain-intrinsic-size:auto 41px; }}
.c-addr {{ overflow:hidden; text-overflow:ellipsis; }}
thead th {{ position:sticky; top:0; background:var(--surface-2); z-index:5;
  font-size:10.5px; text-transform:uppercase; letter-spacing:.08em;
  color:var(--ink-3); font-weight:600; text-align:left;
  padding:9px 10px; border-bottom:1px solid var(--line); white-space:nowrap; }}
tbody td {{ padding:7px 10px; border-bottom:1px solid var(--line);
  vertical-align:middle; }}
tbody tr:hover {{ background:var(--surface-2); }}
tbody tr.row {{ border-left:4px solid transparent; }}
tbody tr.e78 {{ border-left-color:var(--e78); }}
tbody tr.e86 {{ border-left-color:var(--e86); }}
tbody tr.e91 {{ border-left-color:var(--e91); }}
tbody tr.e98 {{ border-left-color:var(--e98); }}
tbody tr.e05 {{ border-left-color:var(--e05); }}
.addr {{ display:block; font-weight:600; font-size:13.5px; letter-spacing:-.005em; }}
.sub {{ display:block; font-size:11px; color:var(--ink-3); letter-spacing:.04em; }}
.sub a {{ color:var(--accent); text-decoration:none; }}
.sub a:hover {{ text-decoration:underline; }}
.approx {{ color:var(--ink-3); font-weight:400; margin-left:4px; cursor:help; }}
.multi {{ font-family:"IBM Plex Mono",monospace; font-size:10px; font-weight:600;
  color:var(--accent); background:var(--accent-soft); border-radius:3px;
  padding:1px 4px; margin-left:6px; cursor:help; }}
.chip {{ display:inline-block; font-family:"IBM Plex Mono",monospace; font-size:11px;
  font-weight:600; padding:2px 7px; border-radius:4px; color:#fff; }}
.chip.e78 {{ background:var(--e78); }} .chip.e86 {{ background:var(--e86); }}
.chip.e91 {{ background:var(--e91); }} .chip.e98 {{ background:var(--e98); }}
.chip.e05 {{ background:var(--e05); }}
.age {{ font-size:10.5px; color:var(--ink-3);
  font-family:"IBM Plex Mono",monospace; }}
.c-num {{ font-family:"IBM Plex Mono",monospace; font-variant-numeric:tabular-nums;
  font-size:12.5px; color:var(--ink-2); text-align:right; white-space:nowrap; }}
.c-conf {{ font-family:"IBM Plex Mono",monospace; font-size:12px; color:var(--ink-3);
  text-align:right; }}
.sc {{ font-weight:700; color:var(--accent); font-size:13.5px; }}
.cyc {{ font-family:"Public Sans",sans-serif; font-size:11.5px; font-weight:600;
  padding:5px 10px; border-radius:5px; cursor:pointer; min-width:106px;
  border:1px solid var(--line); background:var(--surface-2); color:var(--ink-3);
  white-space:nowrap; text-align:center; }}
.cyc:hover {{ border-color:var(--accent); color:var(--accent); }}
.cyc:focus-visible, .note:focus-visible, a:focus-visible, button:focus-visible,
input:focus-visible, select:focus-visible {{
  outline:2px solid var(--accent); outline-offset:1px; }}
tr[data-status="mailed"] .cyc {{ background:var(--st-mailed); color:#fff; border-color:var(--st-mailed); }}
tr[data-status="replied"] .cyc {{ background:var(--st-replied); color:#fff; border-color:var(--st-replied); }}
tr[data-status="quoted"] .cyc {{ background:var(--st-quoted); color:#fff; border-color:var(--st-quoted); }}
tr[data-status="won"] .cyc {{ background:var(--st-won); color:#fff; border-color:var(--st-won); }}
tr[data-status="dead"] .cyc {{ background:var(--st-dead); color:#fff; border-color:var(--st-dead); }}
tr[data-status="dead"] {{ opacity:.5; }}
tr[data-status="won"] .addr {{ color:var(--st-won); }}
.note {{ font-family:"Public Sans",sans-serif; font-size:12px; color:var(--ink);
  background:transparent; border:1px solid transparent; border-radius:4px;
  padding:4px 6px; width:150px; }}
.note:hover {{ border-color:var(--line); }}
.note:focus {{ background:var(--surface-2); border-color:var(--accent); }}
.c-link a {{ font-family:"IBM Plex Mono",monospace; font-size:11.5px;
  color:var(--accent); text-decoration:none; border-bottom:1px solid transparent; }}
.c-link a:hover {{ border-bottom-color:var(--accent); }}
tr.hide {{ display:none; }}
.empty {{ padding:30px; text-align:center; color:var(--ink-3); font-size:13.5px; }}
footer {{ margin-top:22px; font-size:11.5px; color:var(--ink-3);
  font-family:"IBM Plex Mono",monospace; line-height:1.8; }}
footer b {{ color:var(--ink-2); font-weight:600; }}
.savechip {{ font-family:"IBM Plex Mono",monospace; font-size:11px;
  color:var(--ink-3); }}
@media (max-width:720px) {{ .wrap {{ padding:16px 10px 60px; }} h1 {{ font-size:22px; }} }}
@media (prefers-reduced-motion:reduce) {{ * {{ transition:none !important; }} }}
</style>

<div class="wrap">
<header class="top">
  <div>
    <h1>Poolside Ledger</h1>
    <p class="sub1">Sydney properties whose pool is confirmed present in NSW government aerial imagery from 2005 or earlier &mdash; every one at least 20 years old. Mark each address as you mail it.</p>
  </div>
  <div class="meta">
    Built {gen}<br>
    {total_all:,} qualified leads &middot; showing top {shown:,}<br>
    Age evidence: NSW Historical Imagery 1978&ndash;2005
  </div>
</header>

<div class="stats">
  <div class="stat s-left"><div class="k">Not contacted</div><div class="v" id="k-new">0</div></div>
  <div class="stat s-mailed"><div class="k">Mailed</div><div class="v" id="k-mailed">0</div></div>
  <div class="stat s-replied"><div class="k">Replied</div><div class="v" id="k-replied">0</div></div>
  <div class="stat"><div class="k">Quoted</div><div class="v" id="k-quoted">0</div></div>
  <div class="stat s-won"><div class="k">Won</div><div class="v" id="k-won">0</div></div>
  <div class="stat"><div class="k">Visible now</div><div class="v" id="k-shown">0</div></div>
</div>

<div class="legend">{ec}</div>

<artifact-local>
<div class="controls">
  <input type="search" id="q" placeholder="Search address or suburb&hellip;" aria-label="Search address or suburb">
  <label for="f-sub">Suburb</label>
  <select id="f-sub"><option value="">All</option>{subopts}</select>
  <label for="f-era">Built</label>
  <select id="f-era">
    <option value="">Any</option>
    <option value="e78">pre-1979</option><option value="e86">1979-86</option>
    <option value="e91">1987-91</option><option value="e98">1992-98</option>
    <option value="e05">1999-2005</option>
  </select>
  <label for="f-st">Status</label>
  <select id="f-st">
    <option value="">All</option><option value="new">Not contacted</option>
    <option value="mailed">Mailed</option><option value="replied">Replied</option>
    <option value="quoted">Quoted</option><option value="won">Won</option>
    <option value="dead">Not interested</option>
  </select>
  <label for="f-con">Contact</label>
  <select id="f-con"><option value="">Any</option><option value="1">Has phone/email</option></select>
  <button type="button" class="act" id="reset">Clear filters</button>
  <span class="pill" id="count">&mdash;</span>
  <span class="savechip" id="save">&nbsp;</span>
</div>
</artifact-local>

<div class="tablewrap">
<table>
<colgroup>
  <col style="width:34%"><col style="width:11%"><col style="width:7%">
  <col style="width:8%"><col style="width:6%"><col style="width:6%">
  <col style="width:12%"><col style="width:12%"><col style="width:4%">
</colgroup>
<thead><tr>
  <th>Address</th><th>Pool built</th><th class="c-num">Pool m&sup2;</th>
  <th class="c-num">Block m&sup2;</th><th class="c-num">Score</th>
  <th class="c-conf">Conf</th><th>Status</th><th>Note</th><th></th>
</tr></thead>
<tbody id="tb" artifact-sync>
{rows}
</tbody>
</table>
<div class="empty" id="empty" hidden>No leads match these filters.</div>
</div>

<footer>
  <b>How age is proven:</b> each pool polygon is sampled against NSW Spatial Services historical aerial imagery. A pool counted here showed open water at its mapped position in 1998 or 2005 imagery, so it pre-dates 2006.<br>
  <b>Score</b> blends confirmed age (50%), pre-2000 shape signature (18%), block size (14%) and imagery confidence (18%).<br>
  <b>Conf</b> is how clean the imagery evidence was, 0&ndash;1. Anything below 0.45 is worth eyeballing on the map link before you post.
</footer>
</div>

<script>
(function () {{
  var KEY = "poolside-ledger-v1";
  var tb = document.getElementById("tb");
  var rows = Array.prototype.slice.call(tb.querySelectorAll("tr.row"));
  var ORDER0 = ["new", "mailed", "replied", "quoted", "won", "dead"];
  var LABEL = {{
    new: "Not contacted", mailed: "Mailed", replied: "Replied",
    quoted: "Quoted", won: "Won", dead: "Not interested"
  }};
  var local = {{}};
  try {{ local = JSON.parse(localStorage.getItem(KEY) || "{{}}"); }} catch (e) {{ local = {{}}; }}

  // Restore this device's tracking onto rows the shared document still shows
  // as untouched. Rows already carrying a status keep it - that is shared truth.
  rows.forEach(function (tr) {{
    var rec = local[tr.dataset.key];
    if (!rec) return;
    if (tr.dataset.status === "new" && rec.s && rec.s !== "new") {{
      tr.dataset.status = rec.s;
      var cb = tr.querySelector(".cyc");
      if (cb) cb.textContent = LABEL[rec.s] || rec.s;
    }}
    var n = tr.querySelector(".note");
    if (n && !n.value && rec.n) n.value = rec.n;
  }});

  function save() {{
    var out = {{}};
    rows.forEach(function (tr) {{
      var st = tr.dataset.status || "new";
      var n = tr.querySelector(".note");
      var nv = n ? n.value.trim() : "";
      if (st !== "new" || nv) out[tr.dataset.key] = {{ s: st, n: nv }};
    }});
    try {{
      localStorage.setItem(KEY, JSON.stringify(out));
      flash("saved");
    }} catch (e) {{ flash("not saved on this device"); }}
  }}

  var flashT;
  function flash(msg) {{
    var el = document.getElementById("save");
    el.textContent = msg;
    clearTimeout(flashT);
    flashT = setTimeout(function () {{ el.innerHTML = "&nbsp;"; }}, 1600);
  }}

  function counts() {{
    var c = {{ new: 0, mailed: 0, replied: 0, quoted: 0, won: 0, dead: 0 }}, shown = 0;
    rows.forEach(function (tr) {{
      c[tr.dataset.status || "new"] = (c[tr.dataset.status || "new"] || 0) + 1;
      if (!tr.classList.contains("hide")) shown++;
    }});
    ["new", "mailed", "replied", "quoted", "won"].forEach(function (k) {{
      document.getElementById("k-" + k).textContent = (c[k] || 0).toLocaleString();
    }});
    document.getElementById("k-shown").textContent = shown.toLocaleString();
    document.getElementById("count").textContent = shown.toLocaleString() + " shown";
    document.getElementById("empty").hidden = shown !== 0;
  }}

  var ORDER = ORDER0;

  function setStatus(tr, st) {{
    tr.dataset.status = st;                       // gesture-driven change
    tr.querySelector(".cyc").textContent = LABEL[st];
  }}

  tb.addEventListener("click", function (ev) {{
    var b = ev.target.closest(".cyc");
    if (!b) return;
    var tr = b.closest("tr.row");
    var i = ORDER.indexOf(tr.dataset.status || "new");
    // Shift-click steps back, for when you overshoot.
    i = (i + (ev.shiftKey ? ORDER.length - 1 : 1)) % ORDER.length;
    setStatus(tr, ORDER[i]);
    save();
    counts();
    applyFilters();
  }});

  var noteT;
  tb.addEventListener("input", function (ev) {{
    if (!ev.target.classList.contains("note")) return;
    clearTimeout(noteT);
    noteT = setTimeout(save, 500);
  }});

  var q = document.getElementById("q"), fs = document.getElementById("f-sub"),
      fe = document.getElementById("f-era"), ft = document.getElementById("f-st"),
      fc = document.getElementById("f-con");

  function applyFilters() {{
    var s = q.value.trim().toLowerCase(), sub = fs.value, era = fe.value,
        st = ft.value, con = fc.value;
    rows.forEach(function (tr) {{
      var ok = true;
      if (sub && tr.dataset.suburb !== sub) ok = false;
      if (ok && era && tr.dataset.era !== era) ok = false;
      if (ok && st && (tr.dataset.status || "new") !== st) ok = false;
      if (ok && con && tr.dataset.contact !== con) ok = false;
      if (ok && s) {{
        var t = (tr.querySelector(".addr").textContent + " " + tr.dataset.suburb).toLowerCase();
        if (t.indexOf(s) === -1) ok = false;
      }}
      tr.classList.toggle("hide", !ok);
    }});
    counts();
  }}

  [q, fs, fe, ft, fc].forEach(function (el) {{
    el.addEventListener("input", applyFilters);
    el.addEventListener("change", applyFilters);
  }});
  document.getElementById("reset").addEventListener("click", function () {{
    q.value = ""; fs.value = ""; fe.value = ""; ft.value = ""; fc.value = "";
    applyFilters();
  }});

  // Another writer's edit landing in the shared document.
  document.addEventListener("claude:edit", function () {{ counts(); applyFilters(); }});

  counts();
  applyFilters();
}})();
</script>
"""


def main():
    with open(os.path.join(DATA, "leads.json")) as f:
        doc = json.load(f)
    leads = doc["leads"]
    era_counts = Counter(p["earliest_confirmed_year"] for p in leads)
    stats = {"qualified_total": len(leads), "generated": str(date.today()),
             "era_counts": era_counts}
    os.makedirs(DASH, exist_ok=True)
    out = os.path.join(DASH, "index.html")
    with open(out, "w") as f:
        f.write(build(leads, stats))
    full, mail = write_csvs(leads)
    print("WROTE", out, f"({os.path.getsize(out)/1024:.0f} KB)")
    print("WROTE", full, "|", mail)
    print("leads:", len(leads), "| rows in dashboard:", min(len(leads), MAX_ROWS))


if __name__ == "__main__":
    sys.exit(main())
