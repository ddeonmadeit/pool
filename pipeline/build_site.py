"""Build the SDL Finder site: one self-contained page carrying every lead.

The whole lead set is packed into the page as an array-of-arrays and the table
is virtualised, so nothing is truncated - all 11,000+ leads are searchable and
sortable while only the rows on screen exist in the DOM.

The same file is published as an Artifact and served from GitHub Pages, so it
must stay dependency-free apart from Google Fonts.
"""
import csv
import html
import json
import os
import shutil
import sys
from collections import Counter
from datetime import date

from site_css import CSS
from site_js import JS

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
SITE = os.path.join(HERE, "..", "site")
DOCS = os.path.join(HERE, "..", "docs")
ROOT = os.path.join(HERE, "..")

ERA = [(1978, "pre-1979"), (1986, "1979-86"), (1991, "1987-91"),
       (1998, "1992-98"), (2005, "1999-2005")]

# Pool condition, from comparing current imagery against the old captures.
CONDITION_CODE = {"neglected": 0, "untouched": 1, "renovated_pre2005": 2,
                  "dark_throughout": 3, "unknown": 4, "not_visible": 5}
CONDITION = [
    (0, "Green water", "c0", "Water reads green in current imagery - nobody "
        "maintaining a pool lets it go green. Strongest sign of deferred work."),
    (1, "Original finish", "c1", "Still the pale turquoise of a marbelite or "
        "painted interior, with no tone change across captures. Never resurfaced."),
    (2, "Redone pre-2005", "c2", "Went dark between 1998 and 2005. Pool interiors "
        "last 15-25 years, so this one is due again."),
    (3, "Always dark", "c3", "Dark in every capture. Could be an early dark "
        "finish or deep shade - cannot be told apart."),
    (4, "Unconfirmed", "c4", "Not enough imagery to judge the interior."),
]
THIS_YEAR = date.today().year


def contact_str(p):
    """One compact, already-escaped contact line, or empty."""
    c = p.get("contact") or {}
    bits = []
    if c.get("name"):
        bits.append(html.escape(str(c["name"])))
    tel = c.get("phone") or c.get("mobile")
    if tel:
        t = html.escape(str(tel))
        bits.append('<a href="tel:%s">%s</a>' % (t.replace(" ", ""), t))
    if c.get("email"):
        e = html.escape(str(c["email"]))
        bits.append('<a href="mailto:%s">%s</a>' % (e, e))
    if c.get("website"):
        w = html.escape(str(c["website"]))
        bits.append('<a href="%s" target="_blank" rel="noopener">site</a>' % w)
    return " · ".join(bits)


def pack(leads):
    """Compact record layout, mirrored by the column constants in site_js."""
    out = []
    for p in leads:
        out.append([
            p.get("address") or "",
            p.get("suburb") or "",
            p.get("postcode") or "",
            p.get("earliest_confirmed_year") or 0,
            round(p.get("lead_score") or 0),
            round((p.get("age_confidence") or 0) * 100),
            round(p.get("area_m2") or 0),
            round(p.get("lot_m2") or 0),
            p.get("pools_at_address") or 1,
            1 if p.get("address_match") == "nearby" else 0,
            round(p.get("lat"), 5),
            round(p.get("lon"), 5),
            contact_str(p),
            CONDITION_CODE.get(p.get("reno_state"), 5),
        ])
    return out


def suburb_centroids(leads):
    """Mean lat/lon per suburb, for the radius-search center picker.

    A plain arithmetic mean is fine at Sydney's scale and latitude - the error
    against a proper spherical centroid is a few metres, far under the width
    of a suburb.
    """
    sums = {}
    for p in leads:
        s = p.get("suburb")
        lat, lon = p.get("lat"), p.get("lon")
        if not s or lat is None or lon is None:
            continue
        acc = sums.setdefault(s, [0.0, 0.0, 0])
        acc[0] += lat
        acc[1] += lon
        acc[2] += 1
    return {s: [round(x / n, 5), round(y / n, 5)] for s, (x, y, n) in sums.items()}

def write_csvs(leads, outdir):
    cols = ["address", "suburb", "postcode", "council", "earliest_confirmed_year",
            "min_age_years", "lead_score", "age_confidence", "address_match",
            "area_m2", "lot_m2", "length_m", "width_m", "rect_fill", "category",
            "pools_at_address", "reno_state", "ti_now", "contact_name",
            "contact_phone", "contact_email",
            "contact_website", "lat", "lon", "osm_id"]
    for p in leads:
        c = p.get("contact") or {}
        p["contact_name"] = c.get("name", "")
        p["contact_phone"] = c.get("phone") or c.get("mobile") or ""
        p["contact_email"] = c.get("email", "")
        p["contact_website"] = c.get("website", "")
    with open(os.path.join(outdir, "leads_full.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(leads)
    with open(os.path.join(outdir, "mail_merge.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Address", "Suburb", "State", "Postcode", "PoolAgeYearsMin",
                    "PoolBuiltBefore", "LeadScore"])
        for p in leads:
            w.writerow([p.get("address", ""), p.get("suburb", ""), "NSW",
                        p.get("postcode") or "", p.get("min_age_years", ""),
                        p.get("earliest_confirmed_year", ""), p.get("lead_score", "")])


def build(leads, with_downloads=False):
    packed = pack(leads)
    payload = json.dumps(packed, separators=(",", ":"), ensure_ascii=False)
    subs = sorted({p.get("suburb") for p in leads if p.get("suburb")})
    subopts = "".join('<option value="%s">%s</option>' % (html.escape(s), html.escape(s))
                      for s in subs)
    centroid_payload = json.dumps(suburb_centroids(leads), separators=(",", ":"))
    cond_counts = Counter(p.get("reno_state") for p in leads)
    condlegend = "".join(
        '<span title="%s"><span class="pill %s">%s</span> <b>%s</b></span>'
        % (html.escape(desc), cls, lbl,
           format(cond_counts.get(k, 0), ","))
        for code, lbl, cls, desc in CONDITION
        for k in [next((kk for kk, vv in CONDITION_CODE.items() if vv == code), None)]
        if cond_counts.get(k))
    condopts = "".join('<option value="%d">%s</option>' % (code, lbl)
                       for code, lbl, cls, desc in CONDITION
                       for k in [next((kk for kk, vv in CONDITION_CODE.items()
                                       if vv == code), None)]
                       if cond_counts.get(k))
    prime = sum(cond_counts.get(k, 0) for k in ("neglected", "untouched"))
    era_counts = Counter(p.get("earliest_confirmed_year") for p in leads)
    legend = "".join(
        '<span><span class="pill e%s">%s</span> <b>%s</b></span>'
        % (str(y)[-2:], lbl, format(era_counts.get(y, 0), ","))
        for y, lbl in ERA if era_counts.get(y))
    eraopts = "".join('<option value="%d">%s</option>' % (y, lbl)
                      for y, lbl in ERA if era_counts.get(y))
    n = len(leads)
    oldest = min((p["earliest_confirmed_year"] for p in leads
                  if p.get("earliest_confirmed_year")), default=None)
    councils = Counter(p.get("council") for p in leads if p.get("council"))
    top_councils = ", ".join(c.title() for c, _ in councils.most_common(4))

    return """<title>SDL Finder</title>
<meta name="description" content="Sydney properties with a pool confirmed 20+ years old from NSW government aerial imagery. Addresses, scoring and direct-mail outreach tracking.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" media="print" onload="this.media='all'" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<noscript><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&family=IBM+Plex+Mono:wght@400;500;600&display=swap"></noscript>
<style>__CSS__</style>

<div class="shell">

<div class="chassis">
  <span class="brand">SDL<i>FINDER</i></span>
  <span class="spacer"></span>
  <span class="readout">
    __N__ verified leads &middot; aged by NSW aerial imagery<br>
    <b>__OLDEST__</b> oldest confirmed capture &middot; built __DATE__
  </span>
</div>

<div class="eyebrow"><span class="dash"></span>Sydney &middot; pool renovation prospects</div>
<h1>Sydney pools over 20 years old that <em>nobody has renovated</em>.</h1>
<p class="lede">__N__ properties whose pool shows open water in NSW government aerial
imagery from 2005 or earlier, cross-checked against current imagery to weed out the
ones already redone. __PRIME__ are prime prospects &mdash; still on an original pale
interior, or sitting green. Heaviest in __COUNCILS__. Click a status key as you work
the list; it saves in this browser.</p>

<div class="stats">
  <div class="stat n"><div class="v" id="k-new">0</div><div class="k">Not contacted</div></div>
  <div class="stat"><div class="v" id="k-mailed">0</div><div class="k">Mailed</div></div>
  <div class="stat"><div class="v" id="k-replied">0</div><div class="k">Replied</div></div>
  <div class="stat"><div class="v" id="k-quoted">0</div><div class="k">Quoted</div></div>
  <div class="stat g"><div class="v" id="k-won">0</div><div class="k">Won</div></div>
  <div class="stat n"><div class="v" id="k-shown">0</div><div class="k">Matching filter</div></div>
</div>

<div class="legend">__LEGEND__</div>
<div class="legend">__CONDLEGEND__</div>

<div class="controls">
  <input type="search" id="q" placeholder="Search address, suburb or postcode&hellip;" aria-label="Search">
  <span class="ctl-label">Condition</span>
  <select id="f-cond" aria-label="Pool condition">
    <option value="prime">Prime &mdash; original or green</option>
    <option value="">Any condition</option>__CONDOPTS__
  </select>
  <span class="ctl-label">Suburb</span>
  <select id="f-sub" aria-label="Suburb"><option value="">All</option>__SUBOPTS__</select>
  <span class="ctl-label">Built</span>
  <select id="f-era" aria-label="Era"><option value="">Any</option>__ERAOPTS__</select>
  <div class="ctl-group">
    <span class="ctl-label">Age yrs</span>
    <input type="number" id="f-age-min" min="0" max="120" placeholder="min" aria-label="Minimum pool age in years">
    <span aria-hidden="true">&ndash;</span>
    <input type="number" id="f-age-max" min="0" max="120" placeholder="max" aria-label="Maximum pool age in years">
  </div>
  <div class="ctl-group">
    <span class="ctl-label">Near</span>
    <select id="f-center" aria-label="Center suburb for radius search"><option value="">Choose&hellip;</option>__SUBOPTS__</select>
    <span class="ctl-label">Within</span>
    <input type="number" id="f-radius" min="1" max="100" placeholder="km" aria-label="Radius in kilometres">
    <button type="button" class="key" id="geo">Use my location</button>
    <span id="near-label"></span>
  </div>
  <span class="ctl-label">Status</span>
  <select id="f-st" aria-label="Status">
    <option value="">All</option><option value="new">Not contacted</option>
    <option value="mailed">Mailed</option><option value="replied">Replied</option>
    <option value="quoted">Quoted</option><option value="won">Won</option>
    <option value="dead">Not interested</option>
  </select>
  <span class="ctl-label">Contact</span>
  <select id="f-con" aria-label="Contact"><option value="">Any</option><option value="1">Has phone/email</option></select>
  <button type="button" class="key" id="reset">Clear</button>
  <button type="button" class="key" id="export">Copy tracked CSV</button>
  <button type="button" class="key" id="backup">Back up</button>
  <button type="button" class="key" id="restore">Restore</button>
  <span class="tally" id="tally">&mdash;</span>
</div>

<div class="well">
  <div class="well-head">
    <span class="well-title">Outreach ledger &middot; NSW historical imagery 1978&ndash;2005</span>
    <span class="well-count" id="saved"></span>
  </div>
  <div class="scroller" id="scroller">
    <table>
      <colgroup>
        <col style="width:24%"><col style="width:11%"><col style="width:11%">
        <col style="width:5%"><col style="width:6%"><col style="width:6%">
        <col style="width:5%"><col style="width:5%"><col style="width:11%">
        <col style="width:12%"><col style="width:4%">
      </colgroup>
      <thead><tr>
        <th class="sortable" data-sort="suburb">Address<span class="ind"></span></th>
        <th class="sortable" data-sort="age">Pool built<span class="ind"></span></th>
        <th class="sortable" data-sort="cond">Condition<span class="ind"></span></th>
        <th class="sortable num" data-sort="area">Pool m&sup2;<span class="ind"></span></th>
        <th class="sortable num" data-sort="lot">Block m&sup2;<span class="ind"></span></th>
        <th class="sortable num" data-sort="distance">Dist<span class="ind"></span></th>
        <th class="sortable num" data-sort="score">Score<span class="ind">&#9660;</span></th>
        <th class="num">Conf</th>
        <th>Status</th><th>Note</th><th></th>
      </tr></thead>
      <tbody id="pads-top"><tr id="pad-top" style="height:0"><td colspan="11"></td></tr></tbody>
      <tbody id="tb"></tbody>
      <tbody id="pads-bot"><tr id="pad-bot" style="height:0"><td colspan="11"></td></tr></tbody>
    </table>
    <div class="empty" id="empty" hidden>No leads match these filters.</div>
  </div>
</div>

<footer>
  <b>How the age is proven</b> &mdash; every pool footprint is sampled against NSW Spatial
  Services historical aerial imagery. A lead appears here only if open water showed at its
  mapped position in 1998 or 2005 imagery, so the pool pre-dates 2006.<br>
  <b>Condition</b> compares the pool in current NSW imagery (2020&ndash;2023, 7&nbsp;cm)
  against the 1998 and 2005 captures. Interiors built in the 1970s&ndash;90s were marbelite
  or painted render and read pale turquoise from above; modern pebblecrete, dark quartz
  and glass mosaic read deep navy. A pool that moved into the navy band has been
  resurfaced &mdash; recently if it happened after 2005, and those are dropped down the
  list. Properties where no open water is visible today are removed altogether. Surround
  paving was tested as a second signal and rejected: two captures of an untouched yard
  differ more from season and sun angle than from actual work. A resurfacing that went
  back to a pale finish will read as original, so this under-detects renovation rather
  than inventing it.<br>
  <b>Score</b> blends confirmed age (34%), pool condition (34%), pre-2000 shape
  signature (11%), block size (9%) and imagery confidence (12%). <b>Conf</b> is how clean the imagery read was, 0&ndash;1;
  below 0.45, check the map link before posting. <b>~</b> means the address came from the
  nearest parcel rather than one containing the pool.<br>
  <b>Age yrs</b> filters on exact years since the pool's earliest confirmed capture, finer
  than the Built buckets. <b>Near / Within</b> centres a radius search on a suburb or your
  current location and filters (and can sort) by distance; the Dist column reads
  &mdash; until a centre is set.<br>
  __DOWNLOADS__<b>Tracking</b> saves in this browser only. Use <b>Back up</b> now and then, and
  <b>Restore</b> to move it to another machine.<br>
  Data: OpenStreetMap contributors (ODbL) &middot; NSW Spatial Services, Department of
  Customer Service (CC BY 4.0).
</footer>
</div>

<script type="application/json" id="lead-data">__PAYLOAD__</script>
<script type="application/json" id="centroid-data">__CENTROIDS__</script>
<script>__JS__</script>
""".replace("__CSS__", CSS).replace("__JS__", JS) \
   .replace("__PAYLOAD__", payload) \
   .replace("__CENTROIDS__", centroid_payload) \
   .replace("__SUBOPTS__", subopts).replace("__ERAOPTS__", eraopts) \
   .replace("__LEGEND__", legend) \
   .replace("__CONDLEGEND__", condlegend) \
   .replace("__CONDOPTS__", condopts) \
   .replace("__PRIME__", format(prime, ",")) \
   .replace("__COUNCILS__", top_councils) \
   .replace("__OLDEST__", str(oldest) if oldest else "n/a") \
   .replace("__DATE__", str(date.today())) \
   .replace("__DOWNLOADS__", (
       '<b>Download</b> the full list: <a href="mail_merge.csv" download>mail_merge.csv</a> '
       '(addresses only, ready for a mail house) or '
       '<a href="leads_full.csv" download>leads_full.csv</a> (every field).<br>'
   ) if with_downloads else "") \
   .replace("__N__", format(n, ","))


def main():
    with open(os.path.join(DATA, "leads.json")) as f:
        leads = json.load(f)["leads"]
    leads.sort(key=lambda p: -(p.get("lead_score") or 0))

    write_csvs(leads, DATA)

    # The Artifact sandbox blocks page-initiated downloads, so only the
    # GitHub Pages build advertises the CSV files.
    os.makedirs(SITE, exist_ok=True)
    with open(os.path.join(SITE, "index.html"), "w") as f:
        f.write(build(leads, with_downloads=False))

    docs_page = build(leads, with_downloads=True)

    # GitHub Pages can be pointed at either the repo root or /docs, and which
    # one is actually selected has proven unreliable to confirm from outside
    # the Settings UI. Writing the real site to BOTH makes the hosted page
    # correct no matter which is chosen, rather than depending on that click
    # having landed. /docs keeps the .nojekyll + CSVs; root gets the page and
    # its own .nojekyll so it never falls back to rendering this README.
    for target, with_extras in ((DOCS, True), (ROOT, True)):
        os.makedirs(target, exist_ok=True)
        with open(os.path.join(target, "index.html"), "w") as f:
            f.write(docs_page)
        open(os.path.join(target, ".nojekyll"), "w").close()
        if with_extras:
            for name in ("mail_merge.csv", "leads_full.csv"):
                shutil.copyfile(os.path.join(DATA, name), os.path.join(target, name))

    print("WROTE site/index.html, docs/index.html and index.html (root) (%.0f KB)"
          % (len(docs_page.encode()) / 1024))
    print("leads embedded:", len(leads))


if __name__ == "__main__":
    sys.exit(main())
