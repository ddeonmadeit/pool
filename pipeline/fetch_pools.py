"""Harvest swimming-pool polygons across Greater Sydney from OpenStreetMap.

Overpass is queried on a grid so that any single dense cell can fail and be
retried without losing the whole run. Raw per-cell responses are cached to
data/cache/osm/ so re-runs are cheap.
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from common import (centroid, http_post, min_area_rect_ratio, polygon_area_m2,
                    polygon_perimeter_m, ring_to_metres)
from config import GRID_STEP, OVERPASS_MIRRORS, SYDNEY_BBOX

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
CACHE = os.path.join(DATA, "cache", "osm")

QUERY = """[out:json][timeout:170];
(
  way["leisure"="swimming_pool"]({s},{w},{n},{e});
  relation["leisure"="swimming_pool"]({s},{w},{n},{e});
);
out geom tags;
"""


def cells(bbox, step):
    s, w, n, e = bbox
    out = []
    lat = s
    while lat < n:
        lon = w
        while lon < e:
            out.append((lat, lon, min(lat + step, n), min(lon + step, e)))
            lon += step
        lat += step
    return out


def fetch_cell(cell, mirror_idx=0):
    s, w, n, e = cell
    key = f"{s:.3f}_{w:.3f}_{n:.3f}_{e:.3f}.json"
    path = os.path.join(CACHE, key)
    if os.path.exists(path) and os.path.getsize(path) > 2:
        with open(path) as f:
            return json.load(f)
    q = QUERY.format(s=s, w=w, n=n, e=e)
    last = None
    for i in range(len(OVERPASS_MIRRORS)):
        mirror = OVERPASS_MIRRORS[(mirror_idx + i) % len(OVERPASS_MIRRORS)]
        try:
            raw = http_post(mirror, {"data": q}, timeout=200, retries=2)
            doc = json.loads(raw.decode("utf-8", "replace"))
            if "elements" not in doc:
                raise ValueError("no elements key")
            with open(path, "w") as f:
                json.dump(doc, f)
            return doc
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(3)
    raise RuntimeError(f"all mirrors failed for {cell}: {last}")


def ring_of(el):
    """Extract an outer ring as [(lat, lon), ...] from a way or relation."""
    if el["type"] == "way" and "geometry" in el:
        return [(p["lat"], p["lon"]) for p in el["geometry"]]
    if el["type"] == "relation":
        for m in el.get("members", []):
            if m.get("role") == "outer" and "geometry" in m:
                return [(p["lat"], p["lon"]) for p in m["geometry"]]
    return None


def classify(tags, area):
    """Split domestic back-yard pools from public/commercial aquatic sites."""
    name = (tags.get("name") or "").lower()
    access = (tags.get("access") or "").lower()
    public_words = ("aquatic", "leisure centre", "leisure center", "swim centre",
                    "swimming centre", "olympic", "baths", "pool complex",
                    "council", "ymca", "school", "college", "university",
                    "club", "resort", "hotel", "motel", "caravan", "park")
    if access in ("yes", "public", "customers", "permissive"):
        return "public_commercial"
    if any(wd in name for wd in public_words):
        return "public_commercial"
    if tags.get("amenity") or tags.get("tourism") or tags.get("sport") == "swimming" and name:
        return "public_commercial"
    if area >= 260:
        return "public_commercial"
    if name:
        return "strata_or_commercial"
    return "residential"


def main():
    os.makedirs(CACHE, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)
    grid = cells(SYDNEY_BBOX, GRID_STEP)
    print(f"grid cells: {len(grid)}", flush=True)

    seen = {}
    failures = []
    done = [0]

    def work(item):
        i, cell = item
        try:
            return cell, fetch_cell(cell, mirror_idx=i), None
        except Exception as e:  # noqa: BLE001
            return cell, None, e

    workers = int(os.environ.get("POOL_WORKERS", "4"))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(work, it) for it in enumerate(grid)]
        for fut in as_completed(futs):
            cell, doc, err = fut.result()
            done[0] += 1
            if err is not None:
                print(f"  [{done[0]}/{len(grid)}] FAIL {cell}: {err}", flush=True)
                failures.append(cell)
                continue
            added = 0
            for el in doc.get("elements", []):
                oid = f"{el['type']}/{el['id']}"
                if oid in seen:
                    continue
                ring = ring_of(el)
                if not ring or len(ring) < 3:
                    continue
                lat, lon = centroid(ring)
                if not (SYDNEY_BBOX[0] <= lat <= SYDNEY_BBOX[2]):
                    continue
                if not (SYDNEY_BBOX[1] <= lon <= SYDNEY_BBOX[3]):
                    continue
                proj = ring_to_metres(ring, lat, lon)
                area = polygon_area_m2(proj)
                if area < 8 or area > 5000:
                    continue  # spas/paddling pools and mapping errors
                perim = polygon_perimeter_m(proj)
                fill, long_s, short_s = min_area_rect_ratio(proj)
                tags = el.get("tags", {})
                seen[oid] = {
                    "osm_id": oid,
                    "lat": round(lat, 7),
                    "lon": round(lon, 7),
                    "area_m2": round(area, 1),
                    "perimeter_m": round(perim, 1),
                    "rect_fill": round(fill, 3),
                    "length_m": round(long_s, 1),
                    "width_m": round(short_s, 1),
                    "aspect": round(long_s / short_s, 2) if short_s > 0 else None,
                    "name": tags.get("name"),
                    "access": tags.get("access"),
                    "location": tags.get("location"),
                    "category": classify(tags, area),
                    "ring": [[round(a, 6), round(b, 6)] for a, b in ring],
                }
                added += 1
            print(f"  [{done[0]}/{len(grid)}] +{added} (total {len(seen)})", flush=True)

    pools = list(seen.values())
    out = os.path.join(DATA, "pools_raw.json")
    with open(out, "w") as f:
        json.dump({"count": len(pools), "failures": failures, "pools": pools}, f)
    print(f"\nWROTE {out}: {len(pools)} pools, {len(failures)} failed cells")
    from collections import Counter
    print(Counter(p["category"] for p in pools).most_common())


if __name__ == "__main__":
    sys.exit(main())
