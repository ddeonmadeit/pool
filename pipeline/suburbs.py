"""Suburb -> postcode and council lookup, from the NSW administrative boundaries.

Australia Post needs a postcode, and knowing the council is useful because pool
rules and renovation approval paths are set locally.
"""
import json
import os
import sys

from common import http_get_json
from config import SYDNEY_BBOX

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(DATA, "suburb_lookup.json")

SUBURB_Q = ("https://portal.spatial.nsw.gov.au/server/rest/services"
            "/NSW_Administrative_Boundaries_Theme/MapServer/2/query")
LGA_Q = ("https://portal.spatial.nsw.gov.au/server/rest/services"
         "/NSW_Administrative_Boundaries_Theme/MapServer/8/query")


def envelope():
    s, w, n, e = SYDNEY_BBOX
    return json.dumps({"xmin": w, "ymin": s, "xmax": e, "ymax": n,
                       "spatialReference": {"wkid": 4326}})


def fetch(url, fields, geom=False):
    feats = []
    offset = 0
    while True:
        d = http_get_json(url, {
            "f": "json", "geometry": envelope(),
            "geometryType": "esriGeometryEnvelope", "inSR": 4326, "outSR": 4326,
            "spatialRel": "esriSpatialRelIntersects", "outFields": fields,
            "returnGeometry": "true" if geom else "false",
            "geometryPrecision": "5", "maxAllowableOffset": "0.0004",
            "resultRecordCount": "2000", "resultOffset": str(offset),
        }, timeout=180)
        batch = d.get("features", [])
        feats.extend(batch)
        if not d.get("exceededTransferLimit") or not batch:
            break
        offset += len(batch)
        if offset > 20000:
            break
    return feats


def main():
    subs = fetch(SUBURB_Q, "suburbname,postcode", geom=True)
    print("suburb polygons:", len(subs))
    lgas = fetch(LGA_Q, "lganame", geom=True)
    print("lga polygons:", len(lgas))

    lookup = {}
    for f in subs:
        a = f["attributes"]
        name = (a.get("suburbname") or "").strip().upper()
        pc = a.get("postcode")
        if not name:
            continue
        rings = (f.get("geometry") or {}).get("rings") or []
        rec = lookup.setdefault(name, {"postcode": pc, "rings": []})
        if pc and not rec.get("postcode"):
            rec["postcode"] = pc
        if rings:
            rec["rings"].append(rings[0])

    # Attach a council to each suburb by testing the suburb's first vertex.
    def in_ring(x, y, ring):
        inside = False
        n = len(ring)
        j = n - 1
        for i in range(n):
            xi, yi = ring[i][0], ring[i][1]
            xj, yj = ring[j][0], ring[j][1]
            if (yi > y) != (yj > y):
                if x < (xj - xi) * (y - yi) / (yj - yi + 1e-18) + xi:
                    inside = not inside
            j = i
        return inside

    lga_idx = []
    for f in lgas:
        rings = (f.get("geometry") or {}).get("rings") or []
        nm = (f["attributes"].get("lganame") or "").strip()
        for r in rings:
            xs = [c[0] for c in r]
            ys = [c[1] for c in r]
            lga_idx.append((min(xs), min(ys), max(xs), max(ys), r, nm))

    out = {}
    for name, rec in lookup.items():
        council = None
        if rec["rings"]:
            pts = rec["rings"][0]
            cx = sum(c[0] for c in pts) / len(pts)
            cy = sum(c[1] for c in pts) / len(pts)
            for minx, miny, maxx, maxy, r, nm in lga_idx:
                if minx <= cx <= maxx and miny <= cy <= maxy and in_ring(cx, cy, r):
                    council = nm
                    break
        out[name] = {"postcode": rec.get("postcode"), "council": council}

    with open(OUT, "w") as f:
        json.dump(out, f)
    have_pc = sum(1 for v in out.values() if v.get("postcode"))
    have_lga = sum(1 for v in out.values() if v.get("council"))
    print(f"WROTE {OUT}: {len(out)} suburbs, {have_pc} with postcode, "
          f"{have_lga} with council")
    for k in list(out)[:5]:
        print("  ", k, out[k])


if __name__ == "__main__":
    sys.exit(main())
