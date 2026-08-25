"""Decide which leads are good enough to put a stamp on.

Scoring ranks the whole list; this is a different question with a different
answer. A letter costs real money and lands on a real doormat, so a lead only
belongs in the mail run when every piece of evidence behind it is clean - not
merely when it outranks the lead below it. Everything here is therefore a hard
gate, and every gate records *why* it fired so the decision is auditable
address by address.

Each gate below is justified by what the collected evidence actually supports,
measured over the qualified-lead set rather than assumed. Figures in this
docstring were true at the time each gate was designed and are not
re-computed on every run; see README.md for the current numbers, which are
recomputed each time the pipeline ships.

**Where the address came from.** `geocode.py` puts a pool inside a cadastral
parcel when it can, and otherwise falls back to the closest parcel within 30 m.
That offset was originally gated at 3 m on the reasoning that anything further
was the neighbour's title - a fair inference when parcel containment was the
only address evidence there was.

It is no longer the only evidence. `verify_addresses.py` checks each assigned
address against the NSW principal address points, which is the authoritative
answer to "does this address exist where we think it does", and it disagreed
with the parcel rule in both directions: leads the 3 m rule rejected often
verified against an official point tens of metres away - the distance from a
backyard pool to its own house, not a mis-assignment - while some leads the
parcel rule waved through had no plausible official point at all. So the
authoritative check decides, and parcel containment only rules on the leads
it cannot see.

(That same comparison also surfaced a real bug: `centroid()` in `common.py`
was computing each pool's address point 421 m off median on 99.3% of pools,
from floating-point cancellation in the shoelace formula run on raw lat/lon.
Fixed by shifting to the first vertex before the area-weighted sum. Every
address in this dataset was reassigned after that fix.)

**Whether the dated pool is this pool.** The age detector slides the footprint
over a +/-10 m window to absorb georeferencing drift in the historical mosaics
and keeps the best response. A match that had to travel 8 m or more to find
water is more likely to have found the pool next door than this one, and with
it the neighbour's construction date.

**Whether one letter reaches one decision-maker.** Several pools collapsing
onto a single address is the fingerprint of a duplex, dual occupancy or estate:
the addressee may not be the person who can commission the work.

**Whether the pool reads pale against its own neighbourhood.** This is the gate
that costs the most leads, and it is worth being blunt about why. `ti_now`
across the full set is a single smooth distribution peaking around 0.44 with a
long pale tail - there is no trough at 0.80, or anywhere else. The 0.80 line
separating "original finish" from "mid tone" is a visually calibrated slice
through a continuum, not a boundary between two separated populations. So a
reading of 0.81 is not a pale pool; it is a pool that landed just on the pale
side of an arbitrary line.

Worse, an absolute line is not measuring the same thing everywhere. Tone has a
large per-suburb component: suburb medians run 0.42 in Thornleigh to 0.78 in
Ashfield, sd 0.078 across the 59 suburbs with 30+ leads, against a
within-suburb sd of 0.19. The pale end is the treeless inner east and inner
west, the dark end the canopied northern suburbs - which is what capture
conditions and shade look like, not what pool finishes look like. Checked
inside each suburb the effect disappears, which is how you know it is the
frame and not the pools: comparing each suburb's dearer half against its
cheaper half moves the median tone by +0.005, a coin flip across 42 suburbs,
while between suburbs the same measure spans 0.36.

An absolute bar therefore hands whole suburbs a head start, and it compounds
with the value filter, which selects those same eastern suburbs for unrelated
reasons. Drawn at an absolute 0.90 the mail list came out 43% inner-east and
inner-west against 21% of the leads overall - a geography set by tree cover and
flight dates rather than by where Sydney's unrenovated pools are.

So the bar is drawn twice. A lead must clear an absolute floor - no mid-tone
pools, whatever their surroundings - and must also stand out as an outlier
against the median and spread of its own suburb, which is the same
"compare against the local background" principle the tone measurement already
uses within a single frame, applied one level up. That reads the palest pools
in Cherrybrook and Wahroonga, where an absolute bar found nothing at all, and
stops reading half of Strathfield.

Green water is exempt from that bar. It is the one categorical signal in the
set: nobody maintaining a pool lets it go green, so algal water is direct
evidence of deferred maintenance rather than an inference from colour balance.

There is a second reason to sit well out on the tail, found by asking where
else the reading varies. Tone has a strong per-suburb component: suburb medians
run from 0.42 in Thornleigh to 0.78 in Ashfield, a spread (sd 0.078 across the
59 suburbs with 30+ leads) that is a large fraction of the within-suburb spread
(sd 0.19). The pale end is the treeless inner east and inner west, the dark end
the heavily-canopied northern suburbs, which is what capture conditions and
shade look like rather than what pool finishes look like. A bar drawn in
absolute terms therefore hands whole suburbs a head start. The strict bar
mostly closes that hole by itself: 0.90 sits clear of even the palest suburb
baseline (0.808), so additionally requiring 0.20 over a lead's own suburb
median drops only 6 of 306. At the 0.80 classification boundary the same
requirement drops 72 of 679 - the confound bites hard exactly where the bar is
loose. So the suburb correction is measured here and deliberately not applied:
at this bar it would be machinery that changes almost nothing. Lower
MAIL_TONE_MIN and it stops being optional.

**What could not be checked.** Two things worth stating plainly, because they
bound how good this list can be:

* A resurfacing that went back to a pale finish reads as an original finish and
  no gate here catches it. The current capture is the only trustworthy tone
  reading available (see below), and a pale pool is a pale pool.
* More awkwardly, tone does not measurably track pool age across the set.
  Holding suburb constant, pools confirmed present in 1978-1991 read no paler
  today than pools that only appear by 2005: median difference 0.001, mean
  -0.009, and 6 of the 12 suburbs with enough of both go the other way. If a
  large share of 40-year-old pools were still on their original interior, they
  should read paler than 21-year-old ones as a group, and they do not. That is
  consistent with old pools being resurfaced often enough to cancel the effect,
  and equally consistent with the index carrying less finish information than
  the method assumes. Nothing in the collected evidence separates those two
  readings. What survives it is what the gates below are built on: the age is
  proven from imagery and independently audited, the address is proven from the
  cadastre, and green water is direct evidence. The tone reading narrows that
  list and should be treated as narrowing rather than as proof about any one
  pool - which is the case for posting to the tail of it and not to the 0.80
  boundary.
* The historical tone readings cannot rescue that. Comparing the 1998 and 2005
  captures on the 5,540 pools measured in both, they agree on the tone band
  only 35% of the time, and disagree directionally - 1,173 pools read pale in
  1998 and navy in 2005 against 185 the other way. That is per-capture colour
  balance on half-metre scans, not 1,173 pools resurfaced dark in seven years.
  Conditioning on the current reading confirms it: a pool navy today read navy
  in 2005 54% of the time, and a pool pale today read navy in 2005 36% of the
  time - a few points of signal buried in noise. So historical tone is not used
  as corroboration, and the fact that a lead reads pale in only one capture is
  not held against it.
"""
import os

# Fallback-matched addresses are accepted within this much of the parcel, which
# is OSM/cadastre registration slop. Beyond it the parcel is a guess.
ADDR_SLOP_M = 3.0
# A dating match that had to slide this far is probably a neighbour's pool.
AGE_DRIFT_M = 8.0
# Below this fraction of the footprint reading as water today, the tone was
# averaged over a partly non-water sample and is not a finish measurement.
WATER_FRAC_MIN = 0.85
# The tone bar, drawn twice. TONE_FLOOR is absolute and keeps mid-tone pools
# out wherever they sit; TONE_Z_MIN is how many suburb standard deviations
# above the suburb median the reading must sit, which is what stops tree cover
# and flight dates deciding the geography of the mail run.
TONE_FLOOR = 0.80
TONE_Z_MIN = 2.0
# A suburb needs this many measured pools before its own median and spread are
# trusted as the local baseline; below it, the citywide figures stand in. Same
# reasoning as valuation.py's MIN_SAMPLES_FOR_SUBURB_RATIO. The gate is not
# sensitive to the exact number - 12 through 60 yields 191 to 237 leads.
MIN_SUBURB_SAMPLES = 25

# The states worth a letter at all: an untouched-looking interior, or green
# water. Everything else either has already been redone or cannot be called.
# Widened to include pools resurfaced before 2005: 21-28 years ago against a
# 15-25 year finish life, so their interior is due again. Without this they
# could never reach mail-ready, however clean their evidence.
PRIME_STATES = ("neglected", "original_finish", "renovated_pre2005")

# Ordered, because the site ships each lead's blocks as a bitmask over this
# list rather than as text - thousands of copies of an English sentence cost
# real weight on the page, and the strings are identical every time.
BLOCK_ORDER = [
    ("not_prime", "Pool does not read as an original finish or green water"),
    ("tone_marginal", "Pale reading sits too close to the mid-tone boundary"),
    ("age_match_drift", "Dating match landed too far from the pool's mapped position"),
    ("addr_offparcel", "Pool sits outside the parcel this address belongs to"),
    ("shared_title", "Several pools share this address, so it is not one household"),
    ("not_household", "Not a private residential pool"),
    ("incomplete_address", "Missing suburb or postcode, so the address is not postable"),
    ("partial_water", "Only part of the footprint reads as water today"),
    ("value_unknown", "No estimated property value, so a value filter cannot see it"),
    ("addr_unverified", "No official address point sits near this pool, so the address is unproven"),
]
REASONS = dict(BLOCK_ORDER)
BIT = {code: 1 << i for i, (code, _) in enumerate(BLOCK_ORDER)}


def block_mask(blocks):
    """Pack a lead's block codes into one integer over BLOCK_ORDER."""
    m = 0
    for b in blocks:
        m |= BIT[b]
    return m


def best_age_hit(p):
    """The observation the age call actually rests on, or None."""
    hits = [o for o in (p.get("age_evidence") or [])
            if o.get("status") == "present"]
    if not hits:
        return None
    return max(hits, key=lambda o: (o.get("water_frac") or 0,
                                    o.get("cyan_contrast") or 0))


def mail_blocks(p):
    """Every reason this lead should not get a letter, in priority order."""
    out = []
    state = p.get("reno_state")
    if state not in PRIME_STATES:
        out.append("not_prime")
    elif state == "original_finish" and (
            (p.get("ti_now") or 0) < TONE_FLOOR
            or (p.get("tone_z") is None or p["tone_z"] < TONE_Z_MIN)):
        # Green water skips this: it is evidence, not a colour-balance call.
        out.append("tone_marginal")

    hit = best_age_hit(p)
    if hit is None or (hit.get("offset_m") or 0) >= AGE_DRIFT_M:
        out.append("age_match_drift")

    # Parcel containment was the best address evidence available until the
    # official address points were pulled in; now it is the weaker of the two,
    # so it only decides the cases the authoritative layer cannot.
    verify = p.get("address_verify")
    if verify == "verified":
        pass
    elif verify in ("suspect", "unverifiable"):
        out.append("addr_unverified")
    elif (p.get("address_match") == "nearby"
            and (p.get("address_offset_m") or 0) > ADDR_SLOP_M):
        out.append("addr_offparcel")

    if (p.get("pools_at_address") or 1) > 1:
        out.append("shared_title")

    if p.get("category") != "residential" or p.get("access") == "public":
        out.append("not_household")

    if not p.get("suburb") or not p.get("postcode"):
        out.append("incomplete_address")

    if (p.get("water_frac_now") or 0) < WATER_FRAC_MIN:
        out.append("partial_water")

    if not p.get("estimated_value"):
        out.append("value_unknown")

    return out


def suburb_baselines(leads):
    """Per-suburb median and spread of the current tone reading.

    This is the local background the tone gate is measured against. Suburbs
    with too few measured pools to have a trustworthy baseline of their own
    fall back to the citywide figures rather than to a noisy handful.
    """
    import statistics as st
    from collections import defaultdict
    ti = [p["ti_now"] for p in leads if p.get("ti_now") is not None]
    if not ti:
        return {}, {}, 0.0, 0.0
    city_med, city_sd = st.median(ti), st.pstdev(ti)
    by_sub = defaultdict(list)
    for p in leads:
        if p.get("ti_now") is not None:
            by_sub[p.get("suburb")].append(p["ti_now"])
    med, sd = {}, {}
    for sub, vals in by_sub.items():
        if len(vals) >= MIN_SUBURB_SAMPLES:
            med[sub], sd[sub] = st.median(vals), st.pstdev(vals)
        else:
            med[sub], sd[sub] = city_med, city_sd
    return med, sd, city_med, city_sd


def tone_z(p, med, sd, city_med, city_sd):
    """How far above its suburb's own baseline this pool's tone reads."""
    if p.get("ti_now") is None:
        return None
    sub = p.get("suburb")
    spread = sd.get(sub) or city_sd
    if spread < 0.02:            # a degenerate suburb spread would divide out
        spread = city_sd or 1.0
    return round((p["ti_now"] - med.get(sub, city_med)) / spread, 2)


def apply(leads):
    """Stamp every lead with its blocks and a mail_ready flag. Returns counts."""
    from collections import Counter
    med, sd, city_med, city_sd = suburb_baselines(leads)
    for p in leads:
        p["tone_z"] = tone_z(p, med, sd, city_med, city_sd)
    fired = Counter()
    ready = 0
    for p in leads:
        blocks = mail_blocks(p)
        p["mail_blocks"] = blocks
        p["mail_ready"] = not blocks
        p["mail_block_mask"] = block_mask(blocks)
        p["mail_block_note"] = "; ".join(REASONS[b] for b in blocks)
        for b in blocks:
            fired[b] += 1
        if not blocks:
            ready += 1
    return {"ready": ready, "total": len(leads), "fired": fired}


def report(leads, stats, min_value=2_000_000):
    """Print what each gate cost, so the thresholds can be argued with."""
    prime = [p for p in leads if p.get("reno_state") in PRIME_STATES]
    ready = [p for p in leads if p.get("mail_ready")]
    valued = [p for p in ready if (p.get("estimated_value") or 0) >= min_value]
    print("leads: %d | prime states: %d | mail-ready: %d | mail-ready >= $%s: %d"
          % (len(leads), len(prime), len(ready), format(min_value, ","),
             len(valued)))
    print("gates fired (a lead can trip several):")
    for k, v in stats["fired"].most_common():
        print("   %-19s %5d  %s" % (k, v, REASONS[k]))
    # What the tone bar alone is costing, either side of the chosen one.
    clean = [p for p in prime
             if not [b for b in mail_blocks(p) if b != "tone_marginal"]]
    print("prime leads clean on every non-tone gate: %d" % len(clean))
    print("mail-ready at other tone bars (all other gates held):")
    for z in (1.0, 1.5, 2.0, 2.5, 3.0):
        n = sum(1 for p in clean
                if p.get("reno_state") == "neglected"
                or ((p.get("ti_now") or 0) >= TONE_FLOOR
                    and (p.get("tone_z") or -9) >= z))
        print("   floor %.2f + z >= %.1f -> %4d%s"
              % (TONE_FLOOR, z, n,
                 "   <- current TONE_Z_MIN" if abs(z - TONE_Z_MIN) < 1e-9 else ""))
    print("   for reference, an absolute bar with no suburb baseline:")
    for bar in (0.85, 0.90, 0.95):
        n = sum(1 for p in clean if p.get("reno_state") == "neglected"
                or (p.get("ti_now") or 0) >= bar)
        print("      ti_now >= %.2f -> %4d" % (bar, n))
