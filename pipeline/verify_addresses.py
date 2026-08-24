"""Check each lead's address against NSW's authoritative address points.

`geocode.py` assigns an address by testing the pool centroid against Property
polygons, and falls back to the *nearest* parcel within 30 m when no polygon
contains it. That fallback recovered a lot of leads, but it is a guess: about a
quarter of the prime set is a "nearby" match, with offsets running out to 28 m.
A guess that lands on the neighbour's title is a letter to the wrong house.

This validates the assigned address independently, against a layer not used
for assignment: NSW_Geocoded_Addressing_Theme AddressPoint, which holds the
state's principal address points. For each lead, find the official point whose
address string matches the one we assigned, and measure how far the pool is
from it. A pool a few tens of metres from its address point is normal - the
point sits at the dwelling, the pool is in the yard. A pool hundreds of metres
away means the address belongs to a different property.

Points are pulled per grid cell and matched locally, the same batching
`geocode.py` uses, so the whole set costs a few hundred requests.
"""
import json
import math
import os
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from common import http_get_json

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
CACHE = os.path.join(DATA, "cache", "addrpoints")

ADDR_QUERY = ("https://portal.spatial.nsw.gov.au/server/rest/services"
              "/NSW_Geocoded_Addressing_Theme/MapServer/1/query")
CELL = 0.02  # degrees; ~2.2 km

# A pool sits in the yard behind or beside the dwelling the address point marks,
# so tens of metres is expected. Past this the address point belongs to some
# other property and the assignment is not trustworthy.
PLAUSIBLE_M = 90.0


def norm(a):
    """Normalise an address string for comparison."""
    return " ".join((a or "").upper().replace(",", " ").split())


def cell_key(lat, lon):
    return (math.floor(lat / CELL), math.floor(lon / CELL))


def fetch_cell(key):
    path = os.path.join(CACHE, "%d_%d.json" % key)
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:  # noqa: BLE001 - corrupt cache entry, refetch
            pass
    s = key[0] * CELL - 0.002
    w = key[1] * CELL - 0.002
    n = (key[0] + 1) * CELL + 0.002
    e = (key[1] + 1) * CELL + 0.002
    feats = []
    offset = 0
    while True:
        d = http_get_json(ADDR_QUERY, {
            "f": "json",
            "geometry": json.dumps({"xmin": w, "ymin": s, "xmax": e, "ymax": n,
                                    "spatialReference": {"wkid": 4326}}),
            "geometryType": "esriGeometryEnvelope", "inSR": 4326, "outSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "address", "returnGeometry": "true",
            "geometryPrecision": "6",
            "resultRecordCount": "2000", "resultOffset": str(offset),
        }, timeout=120, retries=3)
        batch = d.get("features", [])
        feats.extend(batch)
        if not d.get("exceededTransferLimit") or not batch:
            break
        offset += len(batch)
        if offset > 12000:
            break
    slim = []
    for f in feats:
        g = f.get("geometry") or {}
        a = (f.get("attributes") or {}).get("address")
        if a and g.get("x") is not None:
            slim.append([norm(a), round(g["y"], 6), round(g["x"], 6)])
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "w") as f:
        json.dump(slim, f)
    return slim


def metres(lat1, lon1, lat2, lon2):
    mlat = 111320.0
    mlon = 111320.0 * math.cos(math.radians(lat1))
    return math.hypot((lon2 - lon1) * mlon, (lat2 - lat1) * mlat)


def verify(leads, workers=6):
    """Annotate each lead with address_verify and address_point_m."""
    buckets = defaultdict(list)
    for p in leads:
        if p.get("lat") is not None:
            buckets[cell_key(p["lat"], p["lon"])].append(p)
    keys = list(buckets)
    print("address-point cells to fetch: %d" % len(keys), flush=True)

    done = [0]

    def work(k):
        try:
            return k, fetch_cell(k), None
        except Exception as e:  # noqa: BLE001 - one cell must not sink the run
            return k, None, e

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(work, k) for k in keys]
        for fut in as_completed(futs):
            key, pts, err = fut.result()
            done[0] += 1
            if err is not None:
                print("  cell %s failed: %s" % (key, err), flush=True)
                continue
            # Several points can share an address string (units, dual
            # frontages); keep them all and take the closest to the pool.
            idx = defaultdict(list)
            for a, la, lo in pts:
                idx[a].append((la, lo))
            for p in buckets[key]:
                cands = idx.get(norm(p.get("address")))
                if not cands:
                    p["address_verify"] = "unverifiable"
                    continue
                d = min(metres(p["lat"], p["lon"], la, lo) for la, lo in cands)
                p["address_point_m"] = round(d, 1)
                p["address_verify"] = ("verified" if d <= PLAUSIBLE_M
                                       else "suspect")
            if done[0] % 25 == 0:
                print("  [%d/%d cells]" % (done[0], len(keys)), flush=True)
    return leads


def main():
    src = os.path.join(DATA, "leads.json")
    with open(src) as f:
        doc = json.load(f)
    leads = doc["leads"]
    for p in leads:
        p.setdefault("address_verify", "unverifiable")
    verify(leads)

    from collections import Counter
    c = Counter(p.get("address_verify") for p in leads)
    print("\naddress verification over %d leads:" % len(leads))
    for k, v in c.most_common():
        print("   %-14s %5d  (%.1f%%)" % (k, v, 100 * v / len(leads)))

    nearby = [p for p in leads if p.get("address_match") == "nearby"]
    if nearby:
        cn = Counter(p.get("address_verify") for p in nearby)
        print("\nof the %d 'nearby' (nearest-parcel) matches:" % len(nearby))
        for k, v in cn.most_common():
            print("   %-14s %5d  (%.1f%%)" % (k, v, 100 * v / len(nearby)))

    with open(src, "w") as f:
        json.dump(doc, f)
    print("\nUPDATED", src)


if __name__ == "__main__":
    sys.exit(main())
