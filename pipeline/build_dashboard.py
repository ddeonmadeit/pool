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

MAX_ROWS = int(os.environ.get("DASH_ROWS", "2000"))

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
            "lead_score", "age_confidence", "area_m2", "lot_m2", "length_m",
            "width_m", "rect_fill", "category", "lat", "lon", "osm_id"]
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
            w.writerow([p.get("address", ""), p.get("suburb", ""), "NSW", "",
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
    return f"""<tr class="row" data-status="new" data-key="{html.escape(p['osm_id'])}" data-suburb="{sub}" data-era="{cls}" data-age="{age}" data-score="{score}">
<td class="c-stripe"><span class="stripe {cls}"></span></td>
<td class="c-addr"><span class="addr">{addr}</span><span class="sub">{sub}</span></td>
<td class="c-era"><span class="chip {cls}">{label}</span><span class="age">{age}+ yrs</span></td>
<td class="c-num">{area:.0f}</td>
<td class="c-num">{lot:.0f}</td>
<td class="c-score"><span class="sc">{score:.0f}</span><span class="bar"><i style="width:{min(score,100):.0f}%"></i></span></td>
<td class="c-conf" title="Imagery evidence confidence">{conf:.2f}</td>
<td class="c-status">
<div class="statusbtns" role="group" aria-label="Outreach status for {addr}">
<button type="button" class="sbtn" data-set="new" title="Not contacted">·</button>
<button type="button" class="sbtn" data-set="mailed" title="Mail sent">Mailed</button>
<button type="button" class="sbtn" data-set="replied" title="They replied">Replied</button>
<button type="button" class="sbtn" data-set="quoted" title="Quote given">Quoted</button>
<button type="button" class="sbtn" data-set="won" title="Job won">Won</button>
<button type="button" class="sbtn" data-set="dead" title="Not interested">Dead</button>
</div></td>
<td class="c-note"><input class="note" type="text" placeholder="note" aria-label="Note for {addr}" value=""></td>
<td class="c-link"><a href="{maps}" target="_blank" rel="noopener" title="Open in Google Maps">map</a></td>
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
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=Public+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
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
table {{ border-collapse:collapse; width:100%; min-width:1080px; }}
thead th {{ position:sticky; top:0; background:var(--surface-2); z-index:5;
  font-size:10.5px; text-transform:uppercase; letter-spacing:.08em;
  color:var(--ink-3); font-weight:600; text-align:left;
  padding:9px 10px; border-bottom:1px solid var(--line); white-space:nowrap; }}
tbody td {{ padding:7px 10px; border-bottom:1px solid var(--line);
  vertical-align:middle; }}
tbody tr:hover {{ background:var(--surface-2); }}
.c-stripe {{ width:5px; padding:0 !important; }}
.stripe {{ display:block; width:4px; height:34px; border-radius:2px; }}
.stripe.e78 {{ background:var(--e78); }} .stripe.e86 {{ background:var(--e86); }}
.stripe.e91 {{ background:var(--e91); }} .stripe.e98 {{ background:var(--e98); }}
.stripe.e05 {{ background:var(--e05); }}
.addr {{ display:block; font-weight:600; font-size:13.5px; letter-spacing:-.005em; }}
.sub {{ display:block; font-size:11px; color:var(--ink-3);
  text-transform:uppercase; letter-spacing:.07em; }}
.chip {{ display:inline-block; font-family:"IBM Plex Mono",monospace; font-size:11px;
  font-weight:600; padding:2px 7px; border-radius:4px; color:#fff; }}
.chip.e78 {{ background:var(--e78); }} .chip.e86 {{ background:var(--e86); }}
.chip.e91 {{ background:var(--e91); }} .chip.e98 {{ background:var(--e98); }}
.chip.e05 {{ background:var(--e05); }}
.age {{ display:block; font-size:10.5px; color:var(--ink-3);
  font-family:"IBM Plex Mono",monospace; }}
.c-num {{ font-family:"IBM Plex Mono",monospace; font-variant-numeric:tabular-nums;
  font-size:12.5px; color:var(--ink-2); text-align:right; white-space:nowrap; }}
.c-conf {{ font-family:"IBM Plex Mono",monospace; font-size:12px; color:var(--ink-3);
  text-align:right; }}
.c-score {{ white-space:nowrap; }}
.sc {{ font-family:"IBM Plex Mono",monospace; font-weight:600; font-size:13px;
  font-variant-numeric:tabular-nums; }}
.bar {{ display:block; width:62px; height:3px; background:var(--line);
  border-radius:2px; overflow:hidden; margin-top:3px; }}
.bar i {{ display:block; height:100%; background:var(--accent); }}
.statusbtns {{ display:flex; gap:3px; }}
.sbtn {{ font-family:"Public Sans",sans-serif; font-size:10.5px; font-weight:600;
  padding:4px 7px; border-radius:4px; cursor:pointer;
  border:1px solid var(--line); background:transparent; color:var(--ink-3);
  white-space:nowrap; }}
.sbtn:hover {{ border-color:var(--accent); color:var(--accent); }}
.sbtn:focus-visible, .note:focus-visible, a:focus-visible, button:focus-visible,
input:focus-visible, select:focus-visible {{
  outline:2px solid var(--accent); outline-offset:1px; }}
tr[data-status="mailed"] .sbtn[data-set="mailed"] {{ background:var(--st-mailed); color:#fff; border-color:var(--st-mailed); }}
tr[data-status="replied"] .sbtn[data-set="replied"] {{ background:var(--st-replied); color:#fff; border-color:var(--st-replied); }}
tr[data-status="quoted"] .sbtn[data-set="quoted"] {{ background:var(--st-quoted); color:#fff; border-color:var(--st-quoted); }}
tr[data-status="won"] .sbtn[data-set="won"] {{ background:var(--st-won); color:#fff; border-color:var(--st-won); }}
tr[data-status="dead"] .sbtn[data-set="dead"] {{ background:var(--st-dead); color:#fff; border-color:var(--st-dead); }}
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
  <button type="button" class="act" id="reset">Clear filters</button>
  <span class="pill" id="count">&mdash;</span>
  <span class="savechip" id="save">&nbsp;</span>
</div>
</artifact-local>

<div class="tablewrap">
<table>
<thead><tr>
  <th></th><th>Address</th><th>Pool built</th><th class="c-num">Pool m&sup2;</th>
  <th class="c-num">Block m&sup2;</th><th>Score</th><th class="c-conf">Conf</th>
  <th>Outreach status</th><th>Note</th><th></th>
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
  var local = {{}};
  try {{ local = JSON.parse(localStorage.getItem(KEY) || "{{}}"); }} catch (e) {{ local = {{}}; }}

  // Restore this device's tracking onto rows the shared document still shows
  // as untouched. Rows already carrying a status keep it - that is shared truth.
  rows.forEach(function (tr) {{
    var rec = local[tr.dataset.key];
    if (!rec) return;
    if (tr.dataset.status === "new" && rec.s && rec.s !== "new") tr.dataset.status = rec.s;
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

  tb.addEventListener("click", function (ev) {{
    var b = ev.target.closest(".sbtn");
    if (!b) return;
    var tr = b.closest("tr.row");
    tr.dataset.status = b.dataset.set;   // gesture-driven attribute change
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
      fe = document.getElementById("f-era"), ft = document.getElementById("f-st");

  function applyFilters() {{
    var s = q.value.trim().toLowerCase(), sub = fs.value, era = fe.value, st = ft.value;
    rows.forEach(function (tr) {{
      var ok = true;
      if (sub && tr.dataset.suburb !== sub) ok = false;
      if (ok && era && tr.dataset.era !== era) ok = false;
      if (ok && st && (tr.dataset.status || "new") !== st) ok = false;
      if (ok && s) {{
        var t = (tr.querySelector(".addr").textContent + " " + tr.dataset.suburb).toLowerCase();
        if (t.indexOf(s) === -1) ok = false;
      }}
      tr.classList.toggle("hide", !ok);
    }});
    counts();
  }}

  [q, fs, fe, ft].forEach(function (el) {{
    el.addEventListener("input", applyFilters);
    el.addEventListener("change", applyFilters);
  }});
  document.getElementById("reset").addEventListener("click", function () {{
    q.value = ""; fs.value = ""; fe.value = ""; ft.value = ""; applyFilters();
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
