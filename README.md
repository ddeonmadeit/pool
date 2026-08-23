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
  enrich_contacts.py  business contacts for commercial/strata pools only
  build_site.py       the site: one self-contained page carrying every lead
  site_css.py         stylesheet (RawLeads-style dark console)
  site_js.py          client logic: virtualised table, filters, tracking
  run_all.sh          end-to-end
data/
  leads.json          scored, ranked leads
  leads_full.csv      every field, every lead
  mail_merge.csv      address-only extract for a mail house
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

`docs/index.html` is one self-contained page holding **every** qualified lead.
Nothing is truncated: the whole set ships inline as a packed array-of-arrays and
the table is virtualised, so only the ~30 rows actually on screen exist in the
DOM at any moment. Measured with the font host unreachable, 10,419 leads reach
usable in **0.24 s**, and filtering the full set takes about a third of a second.
Packing the data rather than pre-rendering table markup also made the page
*smaller* than the earlier 2,500-row version - 1.0 MB against 2.1 MB.

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
