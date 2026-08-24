# Sydney Pool Renovation Leads

Finds Sydney properties whose swimming pool is **provably 20+ years old**, attaches
the street address of each, and publishes an outreach dashboard for tracking a
direct-mail campaign.

Built for a landscaping business selling pool-surround renovations.

---

## The core problem, and how it is solved

There is no published list of "old pools in Sydney". The NSW Swimming Pool
Register is a public register, but it is an address-by-address lookup with no
bulk extract and no construction dates, and its entry on data.nsw.gov.au is just
a link to the website. So pool age has to be *established*, not looked up.

This pipeline establishes it from primary evidence:

| Question | Source | How |
|---|---|---|
| Where are the pools? | OpenStreetMap | `leisure=swimming_pool` polygons across Greater Sydney |
| Whose property is it? | NSW Spatial Services cadastre | Point-in-polygon against the Property layer -> exact street address + block size |
| How old is the pool? | **NSW Historical Aerial Imagery** | Sample the pool's footprint in 1978 / 1986 / 1991 / 1998 / 2005 imagery. Visible water in a given year proves the pool existed then. |

The age test is the important part. Because each pool's exact footprint is
already known, the detector never has to *find* pools in old photos - it only
answers "was there water at these coordinates in year Y?". Imagery from 2005
proves 20+ years; 1998 proves nearly 30; 1978 proves nearly 50.

### Why the detector is trustworthy

Two failure modes were found and fixed during development:

1. **Georeferencing drift.** NSW's historical mosaics do not land perfectly on
   the modern cadastre - offsets of 5-8 m are common on sloping ground, and a
   strict footprint mask reported dozens of real pools as absent. The detector
   now slides the footprint over a +/-10 m search window and keeps the best
   response, with a penalty proportional to distance so a pool at its mapped
   position always beats a neighbour's pool several metres away. Typical winning
   offsets dropped from 5-9 m to 0.5-2.5 m once this bias was added, which is
   itself evidence the matches are landing on the right pool.
2. **Colour-balance drift between captures.** Absolute colour thresholds do not
   transfer between a 1978 and a 2005 capture. Detection therefore requires the
   footprint to be markedly more cyan than its own local background, not to hit
   a fixed RGB value.

A 12-pool visual audit against the source imagery returned 11 correct
detections and 1 correct rejection (a yard that was bare ground in 1998 and has
a pool today).

---

## Layout

```
pipeline/
  config.py           endpoints, bounding box, thresholds
  common.py           HTTP retries, tile maths, planar geometry
  fetch_pools.py      OSM -> pool polygons + shape metrics
  geocode.py          NSW cadastre -> street address + block size
  age_verify.py       historical imagery -> pool age (the core of it)
  run_age.py          bulk qualifying pass (is this pool 20+ years old?)
  refine_ages.py      walks the shortlist back to pin down the decade
  suburbs.py          suburb -> postcode and council
  score.py            lead ranking
  qualify.py          which leads are clean enough to post to, and why not
  requalify.py        re-run that gate over the shipped data/leads.json
  enrich_contacts.py  business contacts for commercial/strata pools only
  build_site.py       the site: one self-contained page carrying every lead
  site_css.py         stylesheet (RawLeads-style dark console)
  site_js.py          client logic: virtualised table, filters, tracking
  run_all.sh          end-to-end
data/
  leads.json          scored, ranked, qualified leads
  leads_full.csv      every field, every lead, with the hold reason on each
  mail_merge.csv      the mail-ready leads only, for a mail house
site/
  index.html          build published as an Artifact
docs/
  index.html          same page, served by GitHub Pages
  *.csv               downloadable extracts
```

## Running it

```bash
cd pipeline
./run_all.sh
```

Every stage caches to `data/cache/` and is resumable - an interrupted run picks
up where it stopped. A full Sydney run is dominated by imagery tile fetches.

Dating runs in two passes for cost reasons. `run_age.py` answers only the
qualifying question - visible in 1998, or failing that 2005? - which is one or
two imagery lookups per pool. `refine_ages.py` then walks the shortlist back
through 1991 / 1986 / 1978 to pin down the decade, because that is what
separates a 1978 pool from a 1997 one at the top of the list. Refining every
pool in Sydney would roughly triple the run for detail that only matters near
the top, so `REFINE_LIMIT` bounds it. Both passes append to the same journal
and later records win, so the shortlist can be extended by re-running.

Tunables live in `config.py`: `SYDNEY_BBOX` to change the area, `GRID_STEP` for
Overpass chunking, `TARGET_BUILT_BEFORE` for the age cutoff. Worker counts come
from the `POOL_WORKERS` and `AGE_WORKERS` environment variables.

## Scoring

`lead_score` (0-100) blends:

- **50% confirmed age** - a pool visible in 1978 imagery outranks one first seen in 2005.
- **18% shape era** - free-form and kidney shapes fill their bounding rectangle
  poorly and are hallmarks of 1970s-80s construction; narrow high-aspect
  rectangles read as modern lap pools that were probably built recently.
- **14% block size** - a bigger parcel means more surround, coping and paving.
- **18% imagery confidence** - how clean the evidence was, discounted when the
  winning match sat well away from the pool's mapped position.

## Qualifying a lead for the mail run

Ranking orders the whole list. Qualifying is a separate and stricter question,
because a letter is spent whether or not the lead behind it was sound, so
`qualify.py` applies hard gates and records on every lead exactly which ones
fired. 1,187 of 8,411 leads clear all of them; 1,008 also clear the $2M value
filter the site opens with. `mail_merge.csv` carries only those, and the site
opens on the same set.

| Gate | Why |
|---|---|
| No official address point near the pool | The authoritative check. Each assigned address is looked up in the NSW principal address points and the distance to the pool measured; 121 leads have no plausible point and are held back. This replaced a parcel-containment rule that got it wrong both ways - see below. |
| Dating match slid 8 m or more | The age detector searches ±10 m to absorb georeferencing drift. A match that had to travel that far probably found the pool next door, and with it the neighbour's construction date. |
| Several pools on one address | The fingerprint of a duplex, dual occupancy or estate: the addressee may not be who can commission the work. |
| Not a private residential pool | A club or council pool is not this offer. |
| Missing suburb or postcode | Not postable as it stands. |
| Footprint only partly reads as water | The tone was averaged over a mixed sample, so it is not a finish measurement. |
| No estimated value | Cannot be judged against the value filter, and is silently invisible to it. |
| Pale reading not convincing against its own suburb | See below. |

### Is the address on the envelope actually right?

Parcel containment used to answer this alone: `geocode.py` puts a pool inside a
cadastral parcel where it can and otherwise takes the nearest parcel within
30 m, and any such fallback more than 3 m out was rejected as probably the
neighbour's title. That was the best available inference, but it was only ever
an inference about geometry, never a check that the address exists.

`verify_addresses.py` adds the real check, against the NSW **principal address
points** - the authoritative record of where an address is. For each lead it
measures the distance from the pool to the official point for its assigned
address. Across all 8,411 leads: **8,290 verified (98.6%)**, 118 unverifiable,
3 suspect. Of the 1,961 leads that came from the nearest-parcel fallback -
the ones the old rule most distrusted - **1,915 (97.7%) verify**.

Run against the prime set, the two rules disagree in both directions, and the
parcel rule is wrong in both:

- **409 prime leads it rejected** verify against an official address point a
  median of 27 m away (max 68 m). That is the distance from a backyard pool to
  its own house on a normal Sydney block, not a mis-assignment. These were good
  leads being thrown away.
- **31 leads it accepted** have no plausible official point at all. Those are
  the genuinely wrong addresses, and they were heading for the mail run.

So the authoritative check now decides, and parcel containment only rules on
the leads it cannot see. Net effect on the mail run: 980 → 1,187 mail-ready.

A related fix came out of the same audit. Suburb was being read off the end of
the address string by looking for a street type, which mis-parsed three ways -
`BELMORE ROAD NORTH RIVERWOOD` became "North Riverwood", `THE CLOISTERS ST
IVES` became "Ives" (`ST` read as an abbreviated `STREET`), and streets with no
street type at all (`THE GREENWAY`) fell back to the last word. Matching the
tail of the address against the authoritative 746-suburb list instead, longest
match first, resolves all three without knowing anything about street naming.
Postcode coverage went from 8,363 to **8,411 of 8,411**.

### What the tone reading can and cannot carry

The last gate costs by far the most leads, and the reason is worth stating
plainly rather than burying in a threshold.

`ti_now` across the whole set is **one smooth distribution**, peaking around
0.44 with a long pale tail. There is no trough at 0.80, or anywhere else. So
the 0.80 line dividing "original finish" from "mid tone" is a visually
calibrated slice through a continuum, not a boundary between two separated
populations, and a reading of 0.81 is not a pale pool - it is a pool that
landed just on the pale side of a drawn line. Ranking on that is fine. Posting
on it is not, which is why the mail run wants readings well out on the tail.

Two further measurements bound how much the reading is worth:

- **Tone has a strong per-suburb component**, and the bar is drawn against it
  rather than in absolute terms. Suburb medians run 0.42 (Thornleigh) to 0.78
  (Ashfield), sd 0.078 across the 59 suburbs with 30+ leads, against a
  within-suburb sd of 0.19. The pale end is the treeless inner east and west,
  the dark end the canopied north - capture conditions and shade, not pool
  finishes. Checked inside each suburb the effect disappears, which is how you
  know it is the frame and not the pools: each suburb's dearer half reads
  +0.005 paler than its cheaper half, a coin flip across 42 suburbs, while
  between suburbs the same measure spans 0.36. An absolute bar therefore hands
  whole suburbs a head start, and compounds with the value filter, which
  selects those same eastern suburbs for unrelated reasons - drawn at an
  absolute 0.90 the mail list came out 43% inner-east and inner-west against
  21% of the leads overall. A lead now has to clear an absolute floor
  (`TONE_FLOOR`, no mid-tone pools anywhere) **and** read as an outlier against
  its own suburb's median and spread (`TONE_Z_MIN`). That finds the palest
  pools in Cherrybrook and Wahroonga, where an absolute bar found none, and
  stops taking half of Strathfield. The result is 12% inner-east and
  inner-west, and 92 suburbs represented rather than a handful. The gate is not
  knife-edged on `MIN_SUBURB_SAMPLES`: 12 through 60 yields 191 to 237 leads.
- **Tone does not measurably track pool age.** Holding suburb constant, pools
  confirmed present in 1978-1991 read no paler today than pools that only
  appear by 2005 (median difference 0.001, mean -0.009, 6 of 12 suburbs going
  the other way). If a large share of 40-year-old pools were still on their
  original interior, they should read paler as a group. They do not. That is
  equally consistent with old pools being resurfaced often enough to cancel the
  effect and with the index carrying less finish information than the method
  assumes, and nothing collected here separates the two.

What survives that unambiguously is what the mail run actually rests on: the
**age** is proven from imagery and independently audited, the **address** is
proven from the cadastre, and **green water** is direct evidence of deferred
maintenance. Tone narrows the list; it is not proof about any one pool.

### Ages that were never looked for: closed

`refine_ages.py` walks pools back through 1991 / 1986 / 1978, and that pass was
for a long time capped by a refinement budget, which left 2,476 leads sitting at
`earliest_confirmed_year == 1998` on a single observation - a floor set by the
budget rather than a finding. That gap is now closed: **no lead is left with a
1998 floor and only one observation**, and all 1,997 leads still dated 1998
carry an explicit 1991 *absent* observation behind them. Their date is negative
evidence now, not missing data.

Walking the shortlist back moved roughly 1,600 leads older, and the era
distribution shifted accordingly:

| earliest confirmed | before | after |
|---|---|---|
| 1986 | 1,270 | **2,099** |
| 1991 | 1,653 | **2,432** |
| 1998 | 3,605 | 1,997 |
| 2005 | 1,883 | 1,883 |

The 1,883 leads at 2005 are deliberately not walked back: each carries
`[(1998, absent), (2005, present)]`, so the pool demonstrably did not exist in
1998 and looking earlier can only confirm the same absence. For the same reason
104 mail-ready leads have no observation older than 1998 - all 104 are 2005-era
pools, not unmeasured ones.

The gates still do not filter on confirmed age, because 20+ years is already
guaranteed by the qualifying question itself; the refined date sharpens ranking
rather than admission.

### Historical tone is not used as corroboration

The obvious fix - require the pool to read pale in the old captures too - does
not work, because the old captures do not agree with each other. On the 5,540
pools readable in both, the 1998 and 2005 captures land in the same tone band
only **35%** of the time, and they disagree in a fixed direction: 1,173 pools
read pale in 1998 and navy in 2005, against 185 the other way. That is
per-capture colour balance on half-metre scans, not 1,173 pools resurfaced dark
in seven years. Conditioning on the current reading says the same: a pool navy
today read navy in 2005 54% of the time, and a pool pale today read navy in
2005 36% of the time.

So `renovated_recent` and `renovated_pre2005` split a currently-dark pool on
weak evidence. Both are already outside the prime set, and no gate holds it
against a lead that reads pale in only one capture. The surround-paving signal
was rejected on the same grounds: its spread is near identical whether a pool
reads original or already redone.

## Estimated property value

There is no free bulk automated valuation model for NSW property. What is
published, and used here:

- **Current land value** for almost every property, from the NSW Valuer
  General, updated 1 July each year - the freehold value of the land alone,
  excluding the house.
- **Actual sale prices**, recent for only a slice of any suburb - and often a
  stale slice at that. A property whose pool has never been renovated is
  exactly the kind of property unlikely to have changed hands recently either;
  the very first lead this was tested against last sold in 2003.

So sale price is never used per-property as "the" value - it is too often
decades old. Instead it calibrates a **land-to-value ratio**: for properties
with a sale in the last 3 years, `price / current land value` says how much of
a typical property's worth sits in the land right now. The median of that
ratio per suburb, applied to every lead's own current land value, gives every
property an estimate on the same current footing. Suburbs without enough
recent sales (`valuation.py`'s `MIN_SAMPLES_FOR_SUBURB_RATIO`) fall back to the
citywide median ratio.

This is a shortlisting filter, not a market appraisal - do not quote the
number back to a homeowner.

## Contact details

Residential leads carry an **address only**, deliberately. There is no lawful
bulk source of a private owner's phone or email in NSW, and unsolicited
marketing email or SMS to individuals breaches the Spam Act 2003. Addressed
physical mail is the compliant channel and needs nothing more than the address.

Commercial and strata pools - hotels, motels, caravan parks, gyms, clubs, sports
centres, apartment buildings - are businesses, and `enrich_contacts.py` attaches
their published business phone, email and website where OpenStreetMap has them.

## Coverage, honestly

OpenStreetMap does not have every pool in Sydney. Coverage is excellent in some
areas and patchy in others, so this finds a large, high-quality subset rather
than a complete census. Everything it does find has a verified address and
imagery-backed age. To extend coverage, the same age and address machinery works
on any pool polygon source - the only replaceable part is `fetch_pools.py`.

## Sources

- OpenStreetMap contributors, ODbL
- NSW Spatial Services - cadastre, geocoded addressing, historical imagery
  (Department of Customer Service, CC BY 4.0)


## The site

`docs/index.html` is one self-contained page holding **every** qualified lead,
not just the mail-ready ones - it opens filtered to those, and the Condition
control widens it back out. Nothing is truncated: the whole set ships inline as
a packed array-of-arrays and the table is virtualised, so only the ~30 rows
actually on screen exist in the DOM at any moment. Measured in headless
Chromium with the font host blocked, all 8,411 leads reach interactive in
**0.33 s**, and re-filtering the full set takes **10 ms**. Each lead's hold
reasons ship as a bitmask over `qualify.BLOCK_ORDER` rather than as text -
8,411 copies of the same English sentences cost 670 KB on their own, which is
most of the page again.

Outreach state is kept in `localStorage`, keyed by pool id. **Back up** copies it
to the clipboard as JSON and **Restore** reads it back, which is how you move
tracking to another machine. **Copy tracked CSV** puts everything you have
touched on the clipboard for a spreadsheet.

### Hosting on GitHub Pages

The site is plain static files, so Pages serves it directly - no build step and
no workflow. The repository is public, so Pages is free and carries no
advertising.

Turn it on once, in the repository's **Settings -> Pages**:

| Field | Value |
|---|---|
| Source | Deploy from a branch |
| Branch | `claude/sydney-pools-outreach-tracker-dnj6uj` |
| Folder | `/docs` |

Save, wait a minute, and the site is live at
`https://ddeonmadeit.github.io/pool/`. Every later push to that branch
redeploys it automatically.

This one switch has to be thrown by hand. A workflow using
`actions/configure-pages` with `enablement: true` was tried first and GitHub
refused it - creating a Pages site needs repository-admin scope, which the
Actions `GITHUB_TOKEN` does not carry ("Resource not accessible by
integration"). Nothing in CI can grant itself that.

**For a URL closer to `sdlfinder.com`,** rename the repository to `sdlfinder`
(Settings -> General -> Repository name). The site then serves from
`https://ddeonmadeit.github.io/sdlfinder/`, which is the closest free address
available. Renaming keeps history and redirects the old URL; update the git
remote afterwards with
`git remote set-url origin https://github.com/ddeonmadeit/sdlfinder`.

### Custom domain

`sdlfinder.com` has no DNS records, so it appears unregistered - but a domain
is the one part of this that costs money (roughly AUD 15-25 a year from any
registrar). GitHub Pages then serves it free, with a free certificate and no
advertising.

After buying it: create a file `docs/CNAME` whose only content is the bare
hostname, push, then point DNS at GitHub:

```
A     @    185.199.108.153
A     @    185.199.109.153
A     @    185.199.110.153
A     @    185.199.111.153
CNAME www  ddeonmadeit.github.io.
```

Set the domain under Settings -> Pages, and tick *Enforce HTTPS* once the
certificate is issued (usually within the hour).
