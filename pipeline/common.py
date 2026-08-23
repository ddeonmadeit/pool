"""Small shared helpers: HTTP with retries, tile maths, geometry."""
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request

from config import USER_AGENT


def http_post(url, data, timeout=180, retries=3):
    body = urllib.parse.urlencode(data).encode()
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, data=body, headers={"User-Agent": USER_AGENT}
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 - network layer, retry everything
            last = e
            time.sleep(2 ** attempt)
    raise last


def http_get_json(url, params=None, timeout=90, retries=3):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last


# --- Web Mercator tile maths -------------------------------------------------

def deg2tile_f(lat, lon, z):
    """Fractional slippy-map tile coordinates."""
    n = 2.0 ** z
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
    return x, y


def tile_resolution_m(lat, z):
    """Ground resolution in metres per pixel for a 256px tile."""
    return 156543.03392 * math.cos(math.radians(lat)) / (2 ** z)


# --- Planar geometry on a local metric projection ---------------------------

def ring_to_metres(ring, lat0, lon0):
    """Project a lat/lon ring to local metres about (lat0, lon0)."""
    mlat = 111320.0
    mlon = 111320.0 * math.cos(math.radians(lat0))
    return [((lon - lon0) * mlon, (lat - lat0) * mlat) for lat, lon in ring]


def polygon_area_m2(pts):
    """Shoelace area of a projected ring, in square metres."""
    a = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def polygon_perimeter_m(pts):
    p = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        p += math.hypot(x2 - x1, y2 - y1)
    return p


def centroid(ring):
    """Area-weighted centroid of a lat/lon ring; falls back to mean."""
    n = len(ring)
    if n < 3:
        return sum(p[0] for p in ring) / n, sum(p[1] for p in ring) / n
    a = cx = cy = 0.0
    for i in range(n):
        y1, x1 = ring[i]
        y2, x2 = ring[(i + 1) % n]
        cross = x1 * y2 - x2 * y1
        a += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if abs(a) < 1e-12:
        return sum(p[0] for p in ring) / n, sum(p[1] for p in ring) / n
    a *= 0.5
    return cy / (6 * a), cx / (6 * a)


def min_area_rect_ratio(pts):
    """Return (fill_ratio, long_side, short_side) of the minimum-area
    bounding rectangle via rotating calipers over edge directions.

    fill_ratio near 1.0 means a crisp rectangle (typical of modern lap
    pools); lower values indicate free-form/kidney shapes typical of
    1970s-90s Sydney pools.
    """
    if len(pts) < 3:
        return 1.0, 0.0, 0.0
    best = None
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        ang = math.atan2(y2 - y1, x2 - x1)
        ca, sa = math.cos(-ang), math.sin(-ang)
        xs = [x * ca - y * sa for x, y in pts]
        ys = [x * sa + y * ca for x, y in pts]
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
        area = w * h
        if best is None or area < best[0]:
            best = (area, max(w, h), min(w, h))
    rect_area, long_s, short_s = best
    poly_area = polygon_area_m2(pts)
    fill = poly_area / rect_area if rect_area > 0 else 1.0
    return fill, long_s, short_s
