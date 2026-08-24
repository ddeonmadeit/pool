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
of ground immediately around the pool, so comparing that annulus between the old
and current capture ought to catch renovations that kept the original interior.
It does not, and the measurement is kept only as a reported number rather than
used to classify anything. Across the 8,411-lead set the annulus delta is
distributed almost identically whatever the pool's current state - median 45 for
an original-looking finish against 61 for one already redone before 2005, with
both spreading from single digits past 200. Comparing a half-metre 2005 scan
against a 7 cm current capture measures the difference in resolution and season
far more than it measures new paving, and no threshold separates the two
populations. Judging renovation on it would be guessing with extra steps.

Tone is compared against the pool's own local background in the same frame, so
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
# Two services publish the current mosaic. The SIX one is the obvious choice
# but its tile cache is patchy - sampled across Sydney it answered for only
# 57% of leads at z20 and 75% even at z18, which was sending nearly a third of
# the list to "unknown". The portal.spatial cache answered 60/60 at every zoom
# tested, at equivalent quality, so it is the primary and SIX is the fallback.
CUR_SERVICE = ("https://portal.spatial.nsw.gov.au/tileservices"
               "/Hosted/NSW_Imagery/MapServer")
CUR_FALLBACK = ("https://maps.six.nsw.gov.au/arcgis/rest/services"
                "/public/NSW_Imagery/MapServer")

# Current imagery is 7 cm at source. Served at z18 it is dithered badly enough
# to corrupt a colour average (mean adjacent-pixel difference 22, against 7.9 at
# z20), so tone is read at z20 where a typical pool is ~65x32 px.
CUR_ZOOM = 20
# OSM pool outlines are traced from recent imagery, so they should already sit
# on the current capture. A tight window stops the search wandering onto a
# neighbour's pool; historical captures still get the wide one.
CUR_SEARCH_M = 2.5


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
    raw = None
    for base in (CUR_SERVICE, CUR_FALLBACK):
        try:
            req = urllib.request.Request("%s/tile/%d/%d/%d" % (base, z, y, x),
                                         headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            break
        except Exception:  # noqa: BLE001 - try the other cache before giving up
            raw = None
    if raw is None:
        open(p, "wb").close()
        return None
    with open(p, "wb") as f:
        f.write(raw)
    return np.asarray(im)


def sample_water_mask(arr):
    """Stricter than the dating detector's mask, for tone sampling.

    Dating only had to answer "was there water here", so a permissive mask was
    right. Here the mask decides which pixels get averaged, and it also drives
    the alignment search - so dark bluish shadow passing as water lets the
    search settle on vegetation beside the pool and then average it. Requiring
    real brightness, and a blue lift proportional to it, keeps shadow out.
    """
    a = arr.astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx = a.max(axis=-1)
    return (b > r + 12) & (g >= r) & (mx > 70) & (mx < 252) & ((b - r) * 10 > mx)


def _erode(mask, k):
    """Shrink a mask by k pixels: dilate its complement and invert."""
    return ~_dilate(~mask, k)


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


def probe(getter, ring, z=IMAGERY_ZOOM, search_m=10.0, min_frac=0.30):
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

    # Alignment uses the permissive mask from the dating detector, which
    # accepts dark blue as water. Using the strict tone mask here meant a navy
    # resurfaced pool matched nothing, drifted to the edge of the search window
    # and was written off as unmeasurable - biasing exactly the renovated pools
    # out of the result. Tone is still read separately, from the eroded median.
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

    # Read tone from the middle of the footprint rather than from whatever a
    # water mask accepts. Masking by "looks like water" quietly excluded exactly
    # the pools that matter: a dark navy resurfaced pool fails a water test
    # built around pale turquoise, so the renovated pools came back unmeasurable
    # instead of renovated. Eroding away the outer ~0.8 m drops coping and edge
    # pixels, and a median over what is left ignores ladders, cleaners and
    # sun glint without assuming the water's colour in advance.
    erode_px = max(1, int(round(0.8 / res)))
    wet = _erode(sel, erode_px)
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
    # A match pinned to the edge of the search window means the search never
    # settled - it ran out of room while still improving, so the footprint is
    # probably sitting on something that is not this pool.
    at_edge = (abs(dy) >= search_px) or (abs(dx) >= search_px)
    # Alignment quality only. Whether it is a pool at all is judged from the
    # colour that comes back, so a dark pool is not written off as unmeasurable.
    reliable = not at_edge

    wr = float(np.median(r[wet]))
    wg = float(np.median(g[wet]))
    wb = float(np.median(b[wet]))

    out = {
        "_debug": {"win": win, "sel": sel, "wet": wet, "annulus": annulus,
                   "wx0": wx0, "wy0": wy0},
        "reliable": bool(reliable),
        "at_edge": bool(at_edge),
        "is_water": bool(looks_like_water(wr, wg, wb)),
        "water_frac": round(frac, 3),
        "offset_m": round(math.hypot(dy, dx) * res, 1),
        "n_wet": int(wet.sum()),
        "wr": wr, "wg": wg, "wb": wb,
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


def looks_like_water(rr, gg, bb):
    """Is this median colour a pool surface, pale or dark?

    Pool water always carries blue above red, whatever the finish. Vegetation
    leads with green over blue, and paving, decking and roofs sit neutral or
    red-led. That separates a dark navy pool from a shaded lawn without
    presuming the interior is pale.
    """
    return (bb - rr) >= 8 and bb >= gg - 4


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
# Calibrated by rendering 30 pools spread across the whole index range at z20
# and reading off where the visual break actually falls, rather than guessing.
# Below ~0.55 the water is unmistakably deep navy and usually sits in modern
# hard landscaping; above ~0.80 it is the pale turquoise of an original
# marbelite or painted interior. The band between is genuinely ambiguous and is
# not claimed either way - the first cut of this used 0.60 as "original", which
# swept the entire mid-blue band into the prime list and was the main reason
# that list came out implausibly large.
NAVY_MAX = 0.55      # below this the water reads deep blue: a modern finish
ORIGINAL_MIN = 0.80  # above this it reads pale turquoise: an original finish
GREEN_MIN = 1.10     # above this green outweighs blue: algal, neglected water
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


def classify(p98, p05, pnow):
    """Judge the pool's finish today, and date the change where history allows.

    Current tone decides the finish, because the current capture is 7 cm and
    read at native zoom, while the historical captures are half-metre scans that
    are noisier and need aligning. History is then used only to say *when* a
    modern finish went in - which matters, because interiors last 15-25 years,
    so a pool resurfaced before 2005 is due again and stays a lead, while one
    done since 2005 does not.

    Known limitation: a resurfacing that went back to a pale finish still reads
    as original. This under-detects renovation rather than inventing it.

    Second known limitation, and the reason the dating of a modern finish below
    is reported rather than relied on: the two historical captures agree on a
    pool's tone band only 35% of the time where both could be read (n=5,540),
    and they disagree in a fixed direction - 1,173 pools read pale in 1998 and
    navy in 2005 against 185 the other way. That is per-capture colour balance
    on half-metre scans. So "renovated_recent" and "renovated_pre2005" separate
    a currently-dark pool by weak evidence; both are already outside the prime
    set, and qualify.py declines to use historical tone as corroboration for
    anything it puts a stamp on.
    """
    out = {}
    def ti(p):
        if not p:
            return None
        return turquoise_index(p["wr"], p["wg"], p["wb"])

    ti98, ti05, tinow = ti(p98), ti(p05), ti(pnow)
    out["ti_1998"], out["ti_2005"], out["ti_now"] = ti98, ti05, tinow
    out["surround_delta_late"] = _surround_delta(p05, pnow)

    if pnow is None or not pnow.get("reliable"):
        out["state"] = "unknown"
        return out

    out["water_frac_now"] = pnow["water_frac"]
    out["is_water_now"] = pnow["is_water"]

    if not pnow["is_water"]:
        # The footprint no longer reads as a water surface: filled in, decked
        # over, drained, or replaced by something else. No pool to renovate.
        out["state"] = "not_visible"
        return out

    if tinow is None:
        out["state"] = "unknown"
        return out

    if tinow >= GREEN_MIN:
        out["state"] = "neglected"          # green water: deferred maintenance
        return out

    if tinow >= ORIGINAL_MIN:
        out["state"] = "original_finish"    # pale turquoise: original interior
        return out

    if tinow >= NAVY_MAX:
        out["state"] = "mid_tone"           # between the two; cannot call it
        return out

    # Modern dark finish today. Date it against whichever history is available:
    # a pale reading in an old capture brackets when the work was done.
    was_pale_2005 = ti05 is not None and ti05 >= ORIGINAL_MIN and p05 and p05.get("reliable")
    was_pale_1998 = ti98 is not None and ti98 >= ORIGINAL_MIN and p98 and p98.get("reliable")
    if was_pale_2005:
        out["state"] = "renovated_recent"   # still pale in 2005, dark now
    elif was_pale_1998:
        out["state"] = "renovated_pre2005"  # pale in 1998, already dark by 2005
    else:
        out["state"] = "dark_throughout"    # dark as far back as we can see
    return out


# How much each state is worth as a renovation prospect, 0-1.
STATE_SCORE = {
    "neglected": 1.00,
    "original_finish": 0.90,
    "renovated_pre2005": 0.55,
    "mid_tone": 0.40,
    "dark_throughout": 0.30,
    "unknown": 0.25,
    "renovated_recent": 0.05,
    "not_visible": 0.0,
}
