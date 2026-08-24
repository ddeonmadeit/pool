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
import re
import sys
from collections import Counter
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
THIS_YEAR = date.today().year


def load_reno():
    """Latest renovation-state record per pool, keyed by osm_id."""
    recs = {}
    path = os.path.join(DATA, "pool_reno.jsonl")
    if not os.path.exists(path):
        return recs
    with open(path) as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            recs[r["osm_id"]] = r
    return recs


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
        return 0.4
    # Roughly half of Sydney's mapped pools are traced as plain rectangles, and
    # a rectangle is not evidence of a *new* pool - it is often just a simplified
    # trace. So the baseline is neutral and only genuine curvature adds to it.
    s = 0.30
    # Free-form / kidney shapes fill their bounding rectangle poorly.
    if fill < 0.72:
        s += 0.35
    elif fill < 0.84:
        s += 0.22
    elif fill < 0.92:
        s += 0.10
    # Narrow high-aspect lap pools are a modern signature.
    if aspect and aspect >= 3.2:
        s -= 0.20
    elif aspect and aspect <= 2.2:
        s += 0.12
    # Classic 8x4-ish family pool footprint.
    if 28 <= area <= 90:
        s += 0.15
    return round(max(0.0, min(s, 1.0)), 2)


def score_pool(p, age_rec, reno_rec=None):
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

    # Block size maps to how much surround, coping and paving a job involves.
    # It peaks in the range of a generous suburban block: parcels in the tens of
    # thousands of square metres are schools, clubs and estates, not a back yard,
    # so they score down rather than topping the list.
    lot = p.get("lot_m2") or 0
    if lot >= 20000:
        lot_pts = 0.25
    elif lot >= 5000:
        lot_pts = 0.5
    elif lot >= 1200:
        lot_pts = 1.0
    elif lot >= 800:
        lot_pts = 0.85
    elif lot >= 550:
        lot_pts = 0.65
    elif lot >= 350:
        lot_pts = 0.45
    else:
        lot_pts = 0.25

    shape_pts = shape_era_score(p)

    # Whether the pool still looks original is the difference between a lead and
    # a wasted letter, so it carries as much weight as age itself. Age says the
    # pool is old enough to be due; this says nobody has already done the work.
    from renovation import STATE_SCORE  # noqa: PLC0415 - avoids a cycle at import
    state = (reno_rec or {}).get("state", "unknown")
    reno_pts = STATE_SCORE.get(state, 0.3)
    p["reno_state"] = state
    p["reno_score"] = reno_pts
    for k in ("ti_now", "ti_2005", "ti_1998", "water_frac_now",
              "surround_delta_late"):
        if reno_rec and reno_rec.get(k) is not None:
            p[k] = round(reno_rec[k], 3) if isinstance(reno_rec[k], float) else reno_rec[k]

    score = 100 * (0.34 * age_pts + 0.34 * reno_pts + 0.11 * shape_pts
                   + 0.09 * lot_pts + 0.12 * conf)
    if p.get("address_match") == "nearby":
        score -= 3  # matched to the closest parcel, not one containing the pool
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


def is_mailable(p):
    """Can Australia Post actually deliver a letter here?

    Three things disqualify an address. Without a leading street number it is a
    road, not a letterbox - the cadastre returns these for parcels that have no
    principal address point.

    A parcel over 4,000 sq m is almost never a single house, however generous a
    block the address suggests - this also catches landholding-scale outliers
    like Holsworthy army base (a single 230 sq km title with thirteen pools
    inside it) as a limiting case. Above 4,000 sqm the data is dominated by
    apartment blocks, retirement villages and strata complexes on one shared
    title - lots over that size turned out to carry a second pool on the same
    address four times more often than lots in the normal house range (23% vs
    5.8%), which is exactly the fingerprint of one title, many dwellings.

    And "26/569 Smith St" is a strata unit number: the pool sits on land owned
    by an owners corporation, not one titleholder to address a renovation
    offer to.

    A hyphenated house-number range ("203-225 Victoria St") was tried as a
    fourth check and dropped - it also fires on genuine prestige-suburb
    mansions with an old dual-lot title (several $20-70M Point Piper and
    Bellevue Hill addresses use exactly this format), so it would have thrown
    out real high-value leads to catch a handful of CBD towers. Land value per
    square metre does not separate them either: a harbourfront lot in Point
    Piper prices similarly to CBD commercial land. A few very high "Est.
    value" outliers in dense inner-city postcodes may be commercial rather
    than residential; this is disclosed rather than guessed at further.
    """
    addr = p.get("address") or ""
    if not re.match(r"^\s*\d", addr):
        return False
    if (p.get("lot_m2") or 0) > 4000:
        return False
    if re.match(r"^\s*\d+[A-Za-z]?\s*/\s*\d", addr):
        return False
    return True


def load_suburb_lookup():
    path = os.path.join(DATA, "suburb_lookup.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def main():
    src = os.path.join(DATA, "pools_addressed.json")
    with open(src) as f:
        pools = json.load(f)["pools"]
    ages = load_ages()
    reno = load_reno()

    sub_lookup = load_suburb_lookup()
    for p in pools:
        score_pool(p, ages.get(p["osm_id"]), reno.get(p["osm_id"]))
        p["suburb"] = suburb_of(p.get("address"))
        meta = sub_lookup.get((p["suburb"] or "").upper()) or {}
        p["postcode"] = meta.get("postcode")
        p["council"] = meta.get("council")

    for p in pools:
        p["mailable"] = bool(p.get("address")) and is_mailable(p)

    qualified = [
        p for p in pools
        if p.get("earliest_confirmed_year")
        and (THIS_YEAR - p["earliest_confirmed_year"]) >= 20
        and p.get("mailable")
        # No open water visible today means no pool to offer to renovate.
        and p.get("reno_state") != "not_visible"
    ]

    # One letter per letterbox. Estates, schools and strata blocks can carry
    # several pools on a single title, and mailing the same address three times
    # wastes postage and looks careless - so collapse to the best-scoring pool
    # per address and record how many pools sit behind it.
    by_addr = {}
    for p in qualified:
        key = (p["address"] or "").strip().upper()
        cur = by_addr.get(key)
        if cur is None or p["lead_score"] > cur["lead_score"]:
            if cur is not None:
                p["pools_at_address"] = cur.get("pools_at_address", 1) + 1
            by_addr[key] = p
        else:
            cur["pools_at_address"] = cur.get("pools_at_address", 1) + 1
    deduped = list(by_addr.values())
    dropped = len(qualified) - len(deduped)
    qualified = deduped
    qualified.sort(key=lambda p: -p["lead_score"])

    # The polygon ring is pipeline scaffolding, not part of the deliverable, and
    # carrying it makes the lead file an order of magnitude bigger than it needs
    # to be. Anything downstream that needs geometry reads pools_addressed.json.
    slim = [{k: v for k, v in p.items() if k != "ring"} for p in qualified]

    # Ranking says which leads are best. Qualification says which are clean
    # enough to post to - a stricter and separate question, since a letter is
    # spent whether or not the lead behind it was sound.
    import qualify  # noqa: PLC0415 - keeps the scoring import graph flat
    stats = qualify.apply(slim)

    out = os.path.join(DATA, "leads.json")
    with open(out, "w") as f:
        json.dump({"generated": str(date.today()), "count": len(slim),
                   "leads": slim}, f)
    print(f"total pools: {len(pools)}")
    print(f"dated: {sum(1 for p in pools if p.get('earliest_confirmed_year'))}")
    unmailable = sum(1 for p in pools if p.get("address") and not p["mailable"])
    print(f"addressed but not mailable (no street number / >10 ha): {unmailable}")
    print(f"qualified 20+ yrs, mailable: {len(qualified)} "
          f"(collapsed {dropped} extra pools sharing an address)")
    print("by earliest year:",
          Counter(p["earliest_confirmed_year"] for p in qualified).most_common())
    print("with postcode:", sum(1 for p in qualified if p.get("postcode")))
    print("top suburbs:", Counter(p["suburb"] for p in qualified).most_common(15))
    print("top councils:", Counter(p["council"] for p in qualified).most_common(10))
    print("by pool condition:", Counter(p.get("reno_state") for p in qualified).most_common())
    qualify.report(slim, stats)
    print("WROTE", out)


if __name__ == "__main__":
    sys.exit(main())
