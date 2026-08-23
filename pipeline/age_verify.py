"""Date each pool by checking whether it is visible in historical aerial imagery.

We already know exactly where each pool is (from its OSM polygon), so we never
have to *find* pools in old imagery - we only answer "was there water at these
coordinates in year Y?".

Two things make this robust:

1. **Offset tolerance.** NSW's historical mosaics are orthorectified per-capture
   and do not land perfectly on modern cadastre - observed offsets of 5-8 m are
   common on sloping ground. We therefore slide the pool's footprint mask over a
   small search window and keep the best response, instead of masking strictly.

2. **Local contrast.** Pool water reads strongly cyan (blue and green both above
   red). We require the footprint to be markedly more cyan than the surrounding
   background rather than passing an absolute colour threshold, which keeps the
   detector stable across captures with different exposure and colour balance.
"""
import io
import math
import os
import urllib.request

import numpy as np
from PIL import Image

from common import deg2tile_f, tile_resolution_m
from config import HISTORICAL_IMAGERY, IMAGERY_ZOOM, USER_AGENT

HERE = os.path.dirname(os.path.abspath(__file__))
TILE_CACHE = os.path.join(HERE, "..", "data", "cache", "tiles")

WATER_FRACTION_MIN = 0.35   # of footprint pixels, at the best offset
CYAN_CONTRAST_MIN = 10.0    # footprint cyanness minus background cyanness
SEARCH_RADIUS_M = 10.0      # georeferencing slack between imagery and cadastre


def _tile_path(year, z, x, y):
    d = os.path.join(TILE_CACHE, str(year), str(z), str(x))
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{y}.png")


def fetch_tile(year, z, x, y):
    """256x256 RGB array, or None where that year has no coverage."""
    path = _tile_path(year, z, x, y)
    if os.path.exists(path):
        if os.path.getsize(path) == 0:
            return None
        try:
            return np.asarray(Image.open(path).convert("RGB"))
        except Exception:  # noqa: BLE001 - corrupt cache entry
            os.remove(path)
    url = f"{HISTORICAL_IMAGERY[year]}/tile/{z}/{y}/{x}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
        im = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:  # noqa: BLE001 - 404 means no imagery here that year
        open(path, "wb").close()
        return None
    with open(path, "wb") as f:
        f.write(raw)
    return np.asarray(im)


def cyanness(arr):
    """Per-pixel blue/green dominance over red. Water scores high."""
    a = arr.astype(np.int16)
    return np.minimum(a[..., 2] - a[..., 0], a[..., 1] - a[..., 0])


def water_mask(arr):
    a = arr.astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx = a.max(axis=-1)
    return (b > r + 12) & (g >= r) & (mx > 45) & (mx < 252)


def _points_in_poly(gx, gy, pxs, pys):
    """Vectorised even-odd ray casting over a pixel grid."""
    inside = np.zeros(gx.shape, dtype=bool)
    n = len(pxs)
    j = n - 1
    for i in range(n):
        xi, yi = pxs[i], pys[i]
        xj, yj = pxs[j], pys[j]
        cond = (yi > gy) != (yj > gy)
        with np.errstate(divide="ignore", invalid="ignore"):
            xint = (xj - xi) * (gy - yi) / (yj - yi + 1e-12) + xi
        inside ^= cond & (gx < xint)
        j = i
    return inside


def _mosaic(year, ring, z, margin_px):
    """Assemble the tiles covering a footprint plus margin."""
    fx = [deg2tile_f(la, lo, z) for la, lo in ring]
    xs = [p[0] for p in fx]
    ys = [p[1] for p in fx]
    pad_t = margin_px / 256.0 + 0.02
    x0 = int(math.floor(min(xs) - pad_t))
    x1 = int(math.floor(max(xs) + pad_t))
    y0 = int(math.floor(min(ys) - pad_t))
    y1 = int(math.floor(max(ys) + pad_t))
    if (x1 - x0) > 5 or (y1 - y0) > 5:
        return None
    w = (x1 - x0 + 1) * 256
    h = (y1 - y0 + 1) * 256
    canvas = np.zeros((h, w, 3), dtype=np.uint8)
    have = np.zeros((h, w), dtype=bool)
    got = False
    for tx in range(x0, x1 + 1):
        for ty in range(y0, y1 + 1):
            t = fetch_tile(year, z, tx, ty)
            if t is None:
                continue
            got = True
            canvas[(ty - y0) * 256:(ty - y0) * 256 + 256,
                   (tx - x0) * 256:(tx - x0) * 256 + 256] = t
            have[(ty - y0) * 256:(ty - y0) * 256 + 256,
                 (tx - x0) * 256:(tx - x0) * 256 + 256] = True
    if not got:
        return None
    poly = [(((p[0] - x0) * 256), ((p[1] - y0) * 256)) for p in fx]
    return canvas, have, poly


def sample_footprint(year, ring, z=IMAGERY_ZOOM):
    """Best water response for a footprint, allowing for imagery misalignment.

    Returns (n_px, best_water_fraction, cyan_contrast, offset_m) or None.
    """
    lat0 = sum(p[0] for p in ring) / len(ring)
    res = tile_resolution_m(lat0, z)
    search_px = max(2, int(round(SEARCH_RADIUS_M / res)))
    margin_px = search_px + 12

    m = _mosaic(year, ring, z, margin_px)
    if m is None:
        return None
    canvas, have, poly = m

    pxs = np.array([p[0] for p in poly])
    pys = np.array([p[1] for p in poly])
    minx, maxx = int(math.floor(pxs.min())), int(math.ceil(pxs.max()))
    miny, maxy = int(math.floor(pys.min())), int(math.ceil(pys.max()))

    # Footprint mask in its own local box.
    bw, bh = max(1, maxx - minx), max(1, maxy - miny)
    gy, gx = np.mgrid[miny:miny + bh, minx:minx + bw]
    fmask = _points_in_poly(gx + 0.5, gy + 0.5, pxs, pys)
    if fmask.sum() < 3:
        fmask = np.ones((bh, bw), dtype=bool)  # sub-pixel pool: use its bbox

    # Window covering every candidate offset.
    wy0 = max(0, miny - search_px)
    wy1 = min(canvas.shape[0], maxy + search_px)
    wx0 = max(0, minx - search_px)
    wx1 = min(canvas.shape[1], maxx + search_px)
    if wy1 - wy0 < bh or wx1 - wx0 < bw:
        return None
    win = canvas[wy0:wy1, wx0:wx1]
    winhave = have[wy0:wy1, wx0:wx1]
    if winhave.mean() < 0.5:
        return None

    wm = water_mask(win) & winhave
    cy = cyanness(win)
    npix = int(fmask.sum())

    best = (-1e9, 0, 0, 0.0)
    oy0 = miny - wy0
    ox0 = minx - wx0
    for dy in range(-search_px, search_px + 1):
        ty = oy0 + dy
        if ty < 0 or ty + bh > win.shape[0]:
            continue
        for dx in range(-search_px, search_px + 1):
            tx = ox0 + dx
            if tx < 0 or tx + bw > win.shape[1]:
                continue
            frac = float(wm[ty:ty + bh, tx:tx + bw][fmask].mean())
            # Prefer a match at the pool's mapped position: without this bias a
            # neighbour's pool a few metres away can win on a marginal margin.
            adj = frac - 0.012 * math.hypot(dy, dx)
            if adj > best[0]:
                best = (adj, dy, dx, frac)
    _, dy, dx, frac = best

    # Cyan contrast of the winning placement against the rest of the window.
    sel = np.zeros(win.shape[:2], dtype=bool)
    sel[oy0 + dy:oy0 + dy + bh, ox0 + dx:ox0 + dx + bw] = fmask
    bg = winhave & ~sel
    in_cy = float(cy[sel].mean()) if sel.sum() else 0.0
    bg_cy = float(cy[bg].mean()) if bg.sum() > 20 else 0.0
    return npix, frac, in_cy - bg_cy, round(math.hypot(dy, dx) * res, 1)


def detect_year(year, ring):
    s = sample_footprint(year, ring)
    if s is None:
        return {"year": year, "status": "no_imagery"}
    npix, frac, contrast, off = s
    present = frac >= WATER_FRACTION_MIN and contrast >= CYAN_CONTRAST_MIN
    if frac >= 0.65 and contrast >= 5.0:
        present = True   # unmistakably a body of water
    if frac >= 0.25 and contrast >= 20.0:
        present = True   # smaller but strongly cyan against its surroundings
    return {
        "year": year,
        "status": "present" if present else "absent",
        "px": npix,
        "water_frac": round(frac, 3),
        "cyan_contrast": round(contrast, 1),
        "offset_m": off,
    }


def date_pool(ring):
    """Return (earliest_confirmed_year, observations) using a cost-aware ladder.

    1998 is checked first: it is the best-aligned capture and a hit there
    already proves the pool is nearly 30 years old. Only if 1998 is negative do
    we fall back to 2005 to catch pools built in between. When 1998 is positive
    we walk further back to find out *how* old the pool is, which drives lead
    priority - a 1978 pool is a far stronger renovation prospect than a 2004 one.
    """
    obs = []
    earliest = None

    r98 = detect_year(1998, ring)
    obs.append(r98)
    if r98["status"] == "present":
        earliest = 1998
        for y in (1991, 1986, 1978):
            r = detect_year(y, ring)
            obs.append(r)
            if r["status"] == "present":
                earliest = y
            elif r["status"] == "absent":
                break
        return earliest, obs

    r05 = detect_year(2005, ring)
    obs.append(r05)
    if r05["status"] == "present":
        return 2005, obs

    # Nothing in 1998 or 2005. If neither year had imagery we simply do not
    # know; if imagery existed and showed no water, the pool post-dates 2005.
    if r98["status"] == "no_imagery" and r05["status"] == "no_imagery":
        return None, obs
    return None, obs
