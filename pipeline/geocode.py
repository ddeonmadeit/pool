"""Attach a legal street address to every pool.

Rather than nearest-neighbour guessing (which hops fences), each pool centroid
is tested for containment inside NSW Spatial Services' Property polygons. That
returns the address of the parcel the pool physically sits on, plus the parcel
area, which is a useful signal for job size.

Parcels are fetched in 0.01-degree envelopes and matched locally, so the whole
of Sydney costs a few hundred requests rather than one per pool.
"""
import json
import math
import os
import sys
import urllib.parse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from common import http_get_json

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
CACHE = os.path.join(DATA, "cache", "parcels")

PROPERTY_QUERY = (
    "https://portal.spatial.nsw.gov.au/server/rest/services"
    "/NSW_Land_Parcel_Property_Theme/MapServer/12/query"
)
CELL = 0.01  # degrees; ~1.1 km, comfortably under the 2000-feature page limit
NEAR_LIMIT_M = 30.0  # fallback radius when a pool falls outside every parcel


def cell_key(lat, lon):
    return (math.floor(lat / CELL), math.floor(lon / CELL))


def fetch_cell_parcels(key):
    """All property polygons intersecting one cell, with a small overlap."""
    path = os.path.join(CACHE, f"{key[0]}_{key[1]}.json")
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:  # noqa: BLE001
            pass
    s = key[0] * CELL - 0.0012
    w = key[1] * CELL - 0.0012
    n = (key[0] + 1) * CELL + 0.0012
    e = (key[1] + 1) * CELL + 0.0012
    feats = []
    offset = 0
    while True:
        params = {
            "f": "json",
            "geometry": json.dumps({
                "xmin": w, "ymin": s, "xmax": e, "ymax": n,
                "spatialReference": {"wkid": 4326},
            }),
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326, "outSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "address,propid,shape_Area,propertytype",
            "returnGeometry": "true",
            "geometryPrecision": "6",
            "maxAllowableOffset": "0.000015",
            "resultRecordCount": "2000",
            "resultOffset": str(offset),
        }
        d = http_get_json(PROPERTY_QUERY, params, timeout=120, retries=3)
        batch = d.get("features", [])
        feats.extend(batch)
        if not d.get("exceededTransferLimit") or not batch:
            break
        offset += len(batch)
        if offset > 12000:
            break
    slim = []
    for f in feats:
        rings = (f.get("geometry") or {}).get("rings") or []
        if not rings:
            continue
        a = f["attributes"]
        slim.append({
            "address": a.get("address"),
            "propid": a.get("propid"),
            "lot_m2": round(a.get("shape_Area") or 0, 1),
            "ptype": a.get("propertytype"),
            "ring": rings[0],
        })
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "w") as f:
        json.dump(slim, f)
    return slim


def point_in_ring(x, y, ring):
    """Ray-casting containment test. ring is [[x, y], ...]."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y):
            xint = (xj - xi) * (y - yi) / (yj - yi + 1e-18) + xi
            if x < xint:
                inside = not inside
        j = i
    return inside


def ring_distance_m(x, y, ring, lat0):
    """Approximate metres from a point to a ring's nearest vertex or edge."""
    mlon = 111320.0 * math.cos(math.radians(lat0))
    mlat = 111320.0
    best = float("inf")
    n = len(ring)
    for i in range(n):
        ax, ay = ring[i][0], ring[i][1]
        bx, by = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        ax, ay = (ax - x) * mlon, (ay - y) * mlat
        bx, by = (bx - x) * mlon, (by - y) * mlat
        dx, dy = bx - ax, by - ay
        seg = dx * dx + dy * dy
        if seg <= 0:
            d = math.hypot(ax, ay)
        else:
            t = max(0.0, min(1.0, -(ax * dx + ay * dy) / seg))
            d = math.hypot(ax + t * dx, ay + t * dy)
        if d < best:
            best = d
    return best


def index_parcels(parcels):
    """Precompute bounding boxes so containment tests stay cheap."""
    out = []
    for p in parcels:
        r = p["ring"]
        xs = [c[0] for c in r]
        ys = [c[1] for c in r]
        out.append((min(xs), min(ys), max(xs), max(ys), p))
    return out


def match(pools, workers=6):
    buckets = defaultdict(list)
    for p in pools:
        buckets[cell_key(p["lat"], p["lon"])].append(p)
    keys = list(buckets)
    print(f"parcel cells to fetch: {len(keys)}", flush=True)

    done = [0]
    hits = [0]

    def work(key):
        try:
            return key, fetch_cell_parcels(key), None
        except Exception as e:  # noqa: BLE001
            return key, None, e

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(work, k) for k in keys]
        for fut in as_completed(futs):
            key, parcels, err = fut.result()
            done[0] += 1
            if err is not None:
                print(f"  [{done[0]}/{len(keys)}] parcel fetch failed {key}: {err}",
                      flush=True)
                continue
            idx = index_parcels(parcels)
            for pool in buckets[key]:
                x, y = pool["lon"], pool["lat"]
                best = None
                quality = None
                for minx, miny, maxx, maxy, p in idx:
                    if minx <= x <= maxx and miny <= y <= maxy:
                        if point_in_ring(x, y, p["ring"]):
                            best, quality = p, "exact"
                            break
                if best is None:
                    # The cadastre and OSM do not always agree to the metre, and
                    # a pool mapped a little over a boundary would otherwise be
                    # dropped. Fall back to the closest parcel within 30 m.
                    near = None
                    nd = NEAR_LIMIT_M
                    pad = 0.0006
                    for minx, miny, maxx, maxy, p in idx:
                        if not (minx - pad <= x <= maxx + pad
                                and miny - pad <= y <= maxy + pad):
                            continue
                        d = ring_distance_m(x, y, p["ring"], y)
                        if d < nd:
                            nd, near = d, p
                    if near is not None:
                        best, quality = near, "nearby"
                        pool["address_offset_m"] = round(nd, 1)
                if best:
                    pool["address"] = best["address"]
                    pool["propid"] = best["propid"]
                    pool["lot_m2"] = best["lot_m2"]
                    pool["property_type"] = best["ptype"]
                    pool["address_match"] = quality
                    hits[0] += 1
            if done[0] % 25 == 0:
                print(f"  [{done[0]}/{len(keys)}] matched {hits[0]}", flush=True)
    print(f"address matched: {hits[0]}/{len(pools)}")
    return pools


def main():
    src = os.path.join(DATA, "pools_raw.json")
    with open(src) as f:
        doc = json.load(f)
    pools = doc["pools"]
    match(pools)
    out = os.path.join(DATA, "pools_addressed.json")
    with open(out, "w") as f:
        json.dump({"count": len(pools), "pools": pools}, f)
    print("WROTE", out)


if __name__ == "__main__":
    sys.exit(main())
