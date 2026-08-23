"""Turn dated, addressed pools into a ranked outreach list.

Scoring is built around what actually makes a pool-surround renovation likely to
convert for a landscaping business:

* **Age** - the whole premise. Confirmed 1978/1986 pools outrank 2005 ones.
* **Shape era** - free-form and kidney shapes with low rectangular fill are
  hallmarks of 1970s-80s construction; crisp narrow rectangles read as modern
  lap pools that were probably done recently.
* **Parcel size** - a bigger block means more surround, coping and paving, so a
  bigger job.
* **Confidence** - how clean the imagery evidence was.
"""
import json
import os
import sys
from collections import Counter
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
THIS_YEAR = date.today().year


def load_ages():
    ages = {}
    path = os.path.join(DATA, "pool_ages.jsonl")
    if not os.path.exists(path):
        return ages
    with open(path) as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            ages[r["osm_id"]] = r
    return ages


def evidence_confidence(obs):
    """How trustworthy the imagery read was, 0-1."""
    hits = [o for o in obs if o.get("status") == "present"]
    if not hits:
        return 0.0
    best = max(hits, key=lambda o: (o.get("water_frac", 0), o.get("cyan_contrast", 0)))
    frac = best.get("water_frac", 0) or 0
    con = best.get("cyan_contrast", 0) or 0
    c = 0.45 * min(frac / 0.9, 1.0) + 0.4 * min(con / 45.0, 1.0)
    if len(hits) > 1:
        c += 0.15  # corroborated across more than one capture
    # A match found well away from the pool's mapped position may actually be a
    # neighbour's pool, so discount it.
    off = best.get("offset_m") or 0
    if off > 6:
        c -= 0.25
    elif off > 4:
        c -= 0.1
    return round(max(0.0, min(c, 1.0)), 2)


def shape_era_score(p):
    """0-1: how much the geometry looks like a pre-2000 Sydney pool."""
    fill = p.get("rect_fill")
    aspect = p.get("aspect")
    area = p.get("area_m2") or 0
    if fill is None:
        return 0.5
    s = 0.0
    # Free-form / kidney shapes fill their bounding rectangle poorly.
    if fill < 0.72:
        s += 0.55
    elif fill < 0.84:
        s += 0.35
    elif fill < 0.92:
        s += 0.15
    # Narrow high-aspect lap pools are a modern signature.
    if aspect and aspect >= 3.2:
        s -= 0.2
    elif aspect and aspect <= 2.2:
        s += 0.2
    # Classic 8x4-ish family pool footprint.
    if 28 <= area <= 90:
        s += 0.25
    return round(max(0.0, min(s, 1.0)), 2)


def score_pool(p, age_rec):
    earliest = (age_rec or {}).get("earliest_year")
    obs = (age_rec or {}).get("observations", [])
    conf = evidence_confidence(obs)

    if earliest:
        min_age = THIS_YEAR - earliest
    else:
        min_age = None

    age_pts = 0.0
    if earliest == 1978:
        age_pts = 1.0
    elif earliest == 1986:
        age_pts = 0.92
    elif earliest == 1991:
        age_pts = 0.82
    elif earliest == 1998:
        age_pts = 0.7
    elif earliest == 2005:
        age_pts = 0.5

    lot = p.get("lot_m2") or 0
    if lot >= 1200:
        lot_pts = 1.0
    elif lot >= 800:
        lot_pts = 0.8
    elif lot >= 550:
        lot_pts = 0.6
    elif lot >= 350:
        lot_pts = 0.4
    else:
        lot_pts = 0.2

    shape_pts = shape_era_score(p)

    score = 100 * (0.50 * age_pts + 0.18 * shape_pts + 0.14 * lot_pts
                   + 0.18 * conf)
    p["earliest_confirmed_year"] = earliest
    p["min_age_years"] = min_age
    p["age_confidence"] = conf
    p["shape_era_score"] = shape_pts
    p["lead_score"] = round(score, 1)
    p["age_evidence"] = [
        {k: o.get(k) for k in ("year", "status", "water_frac", "cyan_contrast",
                               "offset_m")}
        for o in obs
    ]
    return p


def suburb_of(address):
    """NSW address strings end with the suburb, e.g. '29 HOPETOUN AVENUE VAUCLUSE'."""
    if not address:
        return None
    parts = address.strip().split()
    if len(parts) < 2:
        return None
    street_types = {
        "AVENUE", "STREET", "ROAD", "PLACE", "DRIVE", "CLOSE", "COURT",
        "CRESCENT", "PARADE", "LANE", "WAY", "TERRACE", "GROVE", "CIRCUIT",
        "BOULEVARD", "ESPLANADE", "HIGHWAY", "RISE", "WALK", "GARDENS",
        "SQUARE", "PARKWAY", "CIRCLE", "GLEN", "VIEW", "TRACK", "ROW",
    }
    for i in range(len(parts) - 1, 0, -1):
        if parts[i] in street_types:
            return " ".join(parts[i + 1:]) or None
    return parts[-1]


def main():
    src = os.path.join(DATA, "pools_addressed.json")
    with open(src) as f:
        pools = json.load(f)["pools"]
    ages = load_ages()

    for p in pools:
        score_pool(p, ages.get(p["osm_id"]))
        p["suburb"] = suburb_of(p.get("address"))

    qualified = [
        p for p in pools
        if p.get("earliest_confirmed_year")
        and (THIS_YEAR - p["earliest_confirmed_year"]) >= 20
        and p.get("address")
    ]
    qualified.sort(key=lambda p: -p["lead_score"])

    out = os.path.join(DATA, "leads.json")
    with open(out, "w") as f:
        json.dump({"generated": str(date.today()), "count": len(qualified),
                   "leads": qualified}, f)
    print(f"total pools: {len(pools)}")
    print(f"dated: {sum(1 for p in pools if p.get('earliest_confirmed_year'))}")
    print(f"qualified 20+ yrs WITH address: {len(qualified)}")
    print("by earliest year:",
          Counter(p["earliest_confirmed_year"] for p in qualified).most_common())
    print("top suburbs:", Counter(p["suburb"] for p in qualified).most_common(15))
    print("WROTE", out)


if __name__ == "__main__":
    sys.exit(main())
