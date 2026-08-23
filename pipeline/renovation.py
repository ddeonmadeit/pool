"""Tell an untouched pool from one that has already been renovated.

Age alone does not qualify a renovation lead. A 1985 pool resurfaced in 2019 is
a wasted letter; a 1985 pool still on its original interior is the whole target
market. NSW publishes current aerial imagery (2020-2023 depending on block,
7 cm) alongside the historical captures, so the two can be compared directly.

Two independent signals, both read off the imagery:

**Water tone.** Sydney pools built in the 1970s-90s were finished in marbelite
or painted render and read pale turquoise from the air - green and blue both
well above red. Modern resurfacing (pebblecrete, dark quartz, glass mosaic)
reads deep navy: blue far above red, green much closer to red. The ratio
between those two gaps separates an original finish from a modern one without
depending on absolute brightness, which varies with sun angle and capture.

**Surround change.** Re-paving, new coping or a rebuilt deck changes the ring
of ground immediately around the pool. Comparing that annulus between the old
and current capture catches renovations that kept the original interior.

Both are compared against the pool's own local background in the same frame, so
differences in exposure and colour balance between captures cancel out.
"""
import io
import math
import os
import urllib.request

import numpy as np
from PIL import Image

import age_verify as av
from common import deg2tile_f, tile_resolution_m
from config import IMAGERY_ZOOM, USER_AGENT

HERE = os.path.dirname(os.path.abspath(__file__))
CUR_CACHE = os.path.join(HERE, "..", "data", "cache", "tiles", "current")
CUR_SERVICE = ("https://maps.six.nsw.gov.au/arcgis/rest/services"
               "/public/NSW_Imagery/MapServer")


def current_tile(z, x, y):
    d = os.path.join(CUR_CACHE, str(z), str(x))
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "%d.png" % y)
    if os.path.exists(p):
        if os.path.getsize(p) == 0:
            return None
        try:
            return np.asarray(Image.open(p).convert("RGB"))
        except Exception:  # noqa: BLE001 - corrupt cache entry
            os.remove(p)
    try:
        req = urllib.request.Request("%s/tile/%d/%d/%d" % (CUR_SERVICE, z, y, x),
                                     headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
        im = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:  # noqa: BLE001 - no coverage here
        open(p, "wb").close()
        return None
    with open(p, "wb") as f:
        f.write(raw)
    return np.asarray(im)


def _dilate(mask, k):
    """Square-kernel binary dilation by k pixels, via shifted ORs.

    Cheaper than pulling in scipy for the one morphological op this module
    needs, and a square kernel is fine for sampling a surround ring.
    """
    out = mask.copy()
    for _ in range(k):
        nxt = out.copy()
        nxt[1:, :] |= out[:-1, :]
        nxt[:-1, :] |= out[1:, :]
        nxt[:, 1:] |= out[:, :-1]
        nxt[:, :-1] |= out[:, 1:]
        out = nxt
    return out


def _mosaic(getter, ring, z, margin_px):
    fx = [deg2tile_f(la, lo, z) for la, lo in ring]
    xs = [q[0] for q in fx]
    ys = [q[1] for q in fx]
    pad = margin_px / 256.0 + 0.02
    x0 = int(math.floor(min(xs) - pad))
    x1 = int(math.floor(max(xs) + pad))
    y0 = int(math.floor(min(ys) - pad))
    y1 = int(math.floor(max(ys) + pad))
    if (x1 - x0) > 5 or (y1 - y0) > 5:
        return None
    w = (x1 - x0 + 1) * 256
    h = (y1 - y0 + 1) * 256
    canvas = np.zeros((h, w, 3), dtype=np.uint8)
    have = np.zeros((h, w), dtype=bool)
    got = False
    for tx in range(x0, x1 + 1):
        for ty in range(y0, y1 + 1):
            t = getter(z, tx, ty)
            if t is None:
                continue
            got = True
            canvas[(ty - y0) * 256:(ty - y0) * 256 + 256,
                   (tx - x0) * 256:(tx - x0) * 256 + 256] = t
            have[(ty - y0) * 256:(ty - y0) * 256 + 256,
                 (tx - x0) * 256:(tx - x0) * 256 + 256] = True
    if not got:
        return None
    poly = [(((q[0] - x0) * 256), ((q[1] - y0) * 256)) for q in fx]
    return canvas, have, poly


def probe(getter, ring, z=IMAGERY_ZOOM, search_m=10.0):
    """Measure the pool interior and its surround in one imagery source.

    Returns a dict of tone statistics, or None where that source has no
    coverage. The footprint is slid over a small search window exactly as the
    dating detector does, so a capture that does not sit perfectly on the
    modern cadastre still lands on the pool.
    """
    lat0 = sum(p[0] for p in ring) / len(ring)
    res = tile_resolution_m(lat0, z)
    search_px = max(2, int(round(search_m / res)))
    ring_px = max(3, int(round(3.5 / res)))     # ~3.5 m of surround
    margin = search_px + ring_px + 8

    m = _mosaic(getter, ring, z, margin)
    if m is None:
        return None
    canvas, have, poly = m

    pxs = np.array([p[0] for p in poly])
    pys = np.array([p[1] for p in poly])
    minx, maxx = int(math.floor(pxs.min())), int(math.ceil(pxs.max()))
    miny, maxy = int(math.floor(pys.min())), int(math.ceil(pys.max()))
    bw, bh = max(1, maxx - minx), max(1, maxy - miny)
    gy, gx = np.mgrid[miny:miny + bh, minx:minx + bw]
    fmask = av._points_in_poly(gx + 0.5, gy + 0.5, pxs, pys)
    if fmask.sum() < 3:
        fmask = np.ones((bh, bw), dtype=bool)

    wy0 = max(0, miny - search_px - ring_px)
    wy1 = min(canvas.shape[0], maxy + search_px + ring_px)
    wx0 = max(0, minx - search_px - ring_px)
    wx1 = min(canvas.shape[1], maxx + search_px + ring_px)
    if wy1 - wy0 < bh or wx1 - wx0 < bw:
        return None
    win = canvas[wy0:wy1, wx0:wx1]
    winhave = have[wy0:wy1, wx0:wx1]
    if winhave.mean() < 0.5:
        return None

    wm = av.water_mask(win) & winhave
    oy0, ox0 = miny - wy0, minx - wx0

    # Find the placement of the footprint with the most water under it.
    best = (-1e9, 0, 0, 0.0)
    for dy in range(-search_px, search_px + 1):
        ty = oy0 + dy
        if ty < 0 or ty + bh > win.shape[0]:
            continue
        for dx in range(-search_px, search_px + 1):
            tx = ox0 + dx
            if tx < 0 or tx + bw > win.shape[1]:
                continue
            frac = float(wm[ty:ty + bh, tx:tx + bw][fmask].mean())
            adj = frac - 0.012 * math.hypot(dy, dx)
            if adj > best[0]:
                best = (adj, dy, dx, frac)
    _, dy, dx, frac = best

    sel = np.zeros(win.shape[:2], dtype=bool)
    sel[oy0 + dy:oy0 + dy + bh, ox0 + dx:ox0 + dx + bw] = fmask

    # Only average pixels that actually read as water: coping and diving boards
    # inside the traced polygon would otherwise wash out the tone.
    wet = sel & wm
    if wet.sum() < 4:
        wet = sel

    a = win.astype(np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]

    # Surround: a ring just outside the footprint, excluding any water in it
    # (a neighbouring pool or a spa should not count as decking).
    annulus = _dilate(sel, ring_px) & ~sel & winhave & ~wm

    # Median of the whole frame: a per-capture reference for exposure, season
    # and colour balance, so those cancel when comparing two epochs.
    ref = a[winhave]
    out = {
        "water_frac": round(frac, 3),
        "offset_m": round(math.hypot(dy, dx) * res, 1),
        "n_wet": int(wet.sum()),
        "wr": float(r[wet].mean()), "wg": float(g[wet].mean()), "wb": float(b[wet].mean()),
        "mr": float(np.median(ref[..., 0])), "mg": float(np.median(ref[..., 1])),
        "mb": float(np.median(ref[..., 2])),
    }
    if annulus.sum() > 12:
        out.update({
            "n_sur": int(annulus.sum()),
            "sr": float(r[annulus].mean()), "sg": float(g[annulus].mean()),
            "sb": float(b[annulus].mean()),
            "s_std": float(a[annulus].std()),
        })
    return out


def turquoise_index(rr, gg, bb):
    """0 = navy (modern resurfacing), 1 = pale turquoise (original finish).

    Measured as how much the green lift tracks the blue lift above red. Pale
    marbelite and painted finishes push green and blue up together; dark modern
    finishes push blue up alone. Taking the ratio makes it independent of how
    bright the capture is.
    """
    blue_lift = bb - rr
    green_lift = gg - rr
    if blue_lift <= 4:
        return None            # not reading as water at all
    return max(0.0, min(1.5, green_lift / blue_lift))


# Tone bands, calibrated against visual inspection of NSW imagery.
NAVY_MAX = 0.45      # below this the water reads deep blue: a modern finish
ORIGINAL_MIN = 0.60  # above this it reads pale turquoise: an original finish
GREEN_MIN = 1.05     # above this it is green water, i.e. a neglected pool
SURROUND_CHANGE = 34.0   # RGB distance in the surround ring that counts as work
GONE_FRAC = 0.15     # below this there is no longer open water at the footprint


def _surround_delta(a, b):
    """How much the ground around the pool changed between two captures.

    Absolute RGB distance is useless here: two captures of an untouched yard
    differ by ~50 units purely from season, sun angle and sensor. Referencing
    the surround against each frame's own median cancels that global shift, so
    what remains is the surround changing relative to its neighbourhood.
    """
    if not a or not b or "sr" not in a or "sr" not in b:
        return None
    av_ = (a["sr"] - a["mr"], a["sg"] - a["mg"], a["sb"] - a["mb"])
    bv = (b["sr"] - b["mr"], b["sg"] - b["mg"], b["sb"] - b["mb"])
    return round(math.dist(av_, bv), 1)


def _went_dark(old_ti, new_ti):
    """True when the interior moved into the modern dark-finish band."""
    if old_ti is None or new_ti is None:
        return False
    return new_ti < NAVY_MAX and old_ti >= ORIGINAL_MIN


def classify(p98, p05, pnow):
    """Work out when this pool was last visibly worked on.

    Pool interiors last roughly 15-25 years, so a pool resurfaced before 2005 is
    due again and still a lead - what disqualifies a property is work done
    *recently*. Bracketing the tone change across three captures says which case
    applies, rather than lumping every past renovation together.

    The decision rests on interior tone alone. Surround change was tried as a
    second signal and dropped: two captures of an untouched yard differ by ~50
    RGB units from season, sun angle and sensor, and even after referencing each
    frame against its own median the 2005-to-current gap stays systematically
    wider than the 1998-to-2005 gap because current imagery is far sharper. A
    single threshold across both would flag recent work on capture differences.
    The measurement is still recorded for inspection, but it does not classify.

    The known limitation of a tone-only rule: a resurfacing that went back to a
    pale finish looks like an untouched pool. This under-detects renovation, it
    does not invent it, so the list stays honest about what it can prove.
    """
    out = {}
    ti98 = turquoise_index(p98["wr"], p98["wg"], p98["wb"]) if p98 else None
    ti05 = turquoise_index(p05["wr"], p05["wg"], p05["wb"]) if p05 else None
    tinow = turquoise_index(pnow["wr"], pnow["wg"], pnow["wb"]) if pnow else None
    out["ti_1998"], out["ti_2005"], out["ti_now"] = ti98, ti05, tinow
    out["surround_delta_early"] = _surround_delta(p98, p05)
    out["surround_delta_late"] = _surround_delta(p05, pnow)

    if pnow is None:
        out["state"] = "unknown"
        return out

    out["water_frac_now"] = pnow["water_frac"]
    if pnow["water_frac"] < GONE_FRAC:
        # No open water at the footprint now: filled in, decked over, drained,
        # under a solid cover, or buried in tree shadow. The cause cannot be
        # told apart from above, but in every case a pool cannot be confirmed,
        # so the property must not be mailed a pool-renovation offer.
        out["state"] = "not_visible"
        return out

    if tinow is not None and tinow >= GREEN_MIN:
        # Green water. Nobody maintaining a pool lets it go green, so this is
        # the strongest available signal of deferred maintenance.
        out["state"] = "neglected"
        return out

    if _went_dark(ti05, tinow) or (ti05 is None and _went_dark(ti98, tinow)):
        out["state"] = "renovated_recent"     # since 2005; may be very recent
    elif _went_dark(ti98, ti05):
        out["state"] = "renovated_pre2005"    # done long ago, due again
    elif tinow is not None and tinow < NAVY_MAX:
        out["state"] = "dark_throughout"      # always dark; cannot tell
    elif tinow is None:
        out["state"] = "unknown"
    else:
        out["state"] = "untouched"            # pale finish, no tone transition
    return out


# How much each state is worth as a renovation prospect, 0-1.
STATE_SCORE = {
    "neglected": 1.00,
    "untouched": 0.90,
    "renovated_pre2005": 0.55,
    "dark_throughout": 0.35,
    "unknown": 0.30,
    "renovated_recent": 0.05,
    "not_visible": 0.0,
}
