"""Estimate each property's current market value from official land values.

NSW does not publish a full automated valuation model, but the Valuer General
publishes two things that combine into a defensible estimate:

1. **Current land value** for almost every property, updated 1 July each year -
   the freehold value of the land alone, excluding the house.
2. **Actual sale prices**, which are recent for only a small slice of any given
   suburb - and a stale slice at that. For this lead set specifically, a
   property whose pool has never been renovated is exactly the kind of
   property that also has not changed hands recently: the one sale on file for
   the very first property this module was tested against was from 2003.

So sale price is not used per-property - it is too often decades old to mean
anything today. Instead it calibrates a **land-to-value ratio**: for properties
with a reasonably recent sale, price / current-land-value gives how much of a
typical property's worth sits in the land right now. Taking the median of that
ratio per suburb, then applying it to every lead's own current land value,
gives every property an estimate on the same current footing - the 2003 sale
above is never used directly, but the suburb it sits in still gets an estimate
from properties nearby that did sell recently.
"""
import json
import math
import os
import statistics
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from common import http_get_json
from config import SYDNEY_BBOX

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
CACHE = os.path.join(DATA, "cache", "valuation")

VAL_BASE = "https://maps.six.nsw.gov.au/arcgis/rest/services/public/Valuation/MapServer"
LAND_VALUE_LAYER = f"{VAL_BASE}/5"   # Urban Property Valuations
SALES_LAYER = f"{VAL_BASE}/1"        # Urban Property Sales

# A ratio needs at least this many recent sales in a suburb before it is
# trusted; below that the citywide median is used instead.
MIN_SAMPLES_FOR_SUBURB_RATIO = 8
BATCH = 180  # propid IN (...) batch size; comfortably under URL/row limits


def _parse_money(s):
    if not s:
        return None
    try:
        return int(str(s).replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


def fetch_land_values(propids, workers=8):
    """propid -> (land_value:int, valuation_date:str), batched and cached."""
    os.makedirs(CACHE, exist_ok=True)
    propids = sorted(set(p for p in propids if p))
    out = {}
    todo = []
    for i in range(0, len(propids), BATCH):
        batch = propids[i:i + BATCH]
        key = "lv_%d_%d.json" % (batch[0], len(batch))
        path = os.path.join(CACHE, key)
        if os.path.exists(path):
            with open(path) as f:
                out.update(json.load(f))
        else:
            todo.append((batch, path))

    def work(item):
        batch, path = item
        where = "propid IN (%s)" % ",".join(str(b) for b in batch)
        d = http_get_json(LAND_VALUE_LAYER + "/query", {
            "f": "json", "where": where,
            "outFields": "propid,val1_lv,val1_bd", "returnGeometry": "false",
        }, timeout=60, retries=3)
        got = {}
        for feat in d.get("features", []):
            a = feat["attributes"]
            lv = _parse_money(a.get("val1_lv"))
            if lv:
                got[str(a["propid"])] = [lv, a.get("val1_bd")]
        with open(path, "w") as f:
            json.dump(got, f)
        return got

    if todo:
        print("fetching land values: %d batches" % len(todo), flush=True)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(work, it) for it in todo]
            for i, fut in enumerate(as_completed(futs), 1):
                out.update(fut.result())
                if i % 10 == 0:
                    print("  land values %d/%d batches" % (i, len(todo)), flush=True)
    return {int(k): tuple(v) for k, v in out.items()}


def _envelope(bbox):
    s, w, n, e = bbox
    return json.dumps({"xmin": w, "ymin": s, "xmax": e, "ymax": n,
                       "spatialReference": {"wkid": 4326}})


def fetch_recent_sales(bbox=SYDNEY_BBOX, years=3):
    """House sales (not units) across the metro area, for ratio calibration."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, "recent_sales.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)

    cutoff_year = time.gmtime().tm_year - years
    feats = []
    offset = 0
    print("fetching recent sales for suburb value ratios...", flush=True)
    while True:
        # This service 400s on any explicit outFields list combined with a
        # geometry filter - only "*" works. Harmless; we only need four fields.
        d = http_get_json(SALES_LAYER + "/query", {
            "f": "json", "geometry": _envelope(bbox),
            "geometryType": "esriGeometryEnvelope", "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "where": "strata=0 AND last_sale=\'Y\'",
            "outFields": "*", "returnGeometry": "false",
            "resultRecordCount": "1000", "resultOffset": str(offset),
        }, timeout=35, retries=3)
        batch = d.get("features", [])
        feats.extend(batch)
        print("  ...%d sale records so far" % len(feats), flush=True)
        if not d.get("exceededTransferLimit") or not batch:
            break
        offset += len(batch)
        if offset > 90000:
            break
    print("  %d sale records" % len(feats), flush=True)

    out = []
    for f in feats:
        a = f["attributes"]
        sd = a.get("sale_date") or ""
        try:
            year = int(sd.split()[-1])
        except (ValueError, IndexError):
            continue
        if year < cutoff_year:
            continue
        if not a.get("propid") or not a.get("price"):
            continue
        out.append({"propid": a["propid"], "suburb": a.get("suburb"),
                    "price": a["price"], "year": year})
    with open(path, "w") as f:
        json.dump(out, f)
    return out


def build_ratio_table():
    """suburb (upper-case) -> median(recent sale price / current land value).

    Falls back to the citywide median for any suburb without enough recent
    sales to trust its own figure.
    """
    out_path = os.path.join(DATA, "value_ratios.json")
    if os.path.exists(out_path):
        with open(out_path) as f:
            return json.load(f)

    sales = fetch_recent_sales()
    propids = [s["propid"] for s in sales]
    land_values = fetch_land_values(propids)

    by_suburb = defaultdict(list)
    all_ratios = []
    for s in sales:
        lv = land_values.get(s["propid"])
        if not lv or lv[0] <= 0:
            continue
        ratio = s["price"] / lv[0]
        if not (0.3 <= ratio <= 8.0):
            continue  # drop non-arm's-length transfers and data errors
        by_suburb[(s["suburb"] or "").upper()].append(ratio)
        all_ratios.append(ratio)

    citywide = round(statistics.median(all_ratios), 3) if all_ratios else 1.4
    table = {"_citywide": citywide, "_generated": time.strftime("%Y-%m-%d")}
    for suburb, ratios in by_suburb.items():
        if len(ratios) >= MIN_SAMPLES_FOR_SUBURB_RATIO:
            table[suburb] = {"ratio": round(statistics.median(ratios), 3),
                             "n": len(ratios)}
    with open(out_path, "w") as f:
        json.dump(table, f)
    print("value ratio table: %d suburbs with their own ratio, "
          "citywide fallback %.2f (n=%d)"
          % (len(table) - 2, citywide, len(all_ratios)), flush=True)
    return table


def ratio_for_suburb(table, suburb):
    rec = table.get((suburb or "").upper())
    if isinstance(rec, dict):
        return rec["ratio"]
    return table.get("_citywide", 1.4)


def main():
    with open(os.path.join(DATA, "leads.json")) as f:
        doc = json.load(f)
    leads = doc["leads"]

    table = build_ratio_table()
    land_values = fetch_land_values([p.get("propid") for p in leads])
    print("land values matched: %d/%d" % (len(land_values), len(leads)))

    have = 0
    for p in leads:
        lv = land_values.get(p.get("propid"))
        if not lv:
            continue
        land_value, val_date = lv
        ratio = ratio_for_suburb(table, p.get("suburb"))
        p["land_value"] = land_value
        p["land_value_date"] = val_date
        p["value_ratio"] = ratio
        p["estimated_value"] = int(round(land_value * ratio / 10000) * 10000)
        have += 1
    print("leads with an estimated value: %d/%d" % (have, len(leads)))

    with open(os.path.join(DATA, "leads.json"), "w") as f:
        json.dump(doc, f)
    print("UPDATED", os.path.join(DATA, "leads.json"))


if __name__ == "__main__":
    sys.exit(main())
