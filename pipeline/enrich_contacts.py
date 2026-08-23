"""Attach contact details where they legitimately exist.

Important distinction, and the reason this module only covers part of the list:

* **Residential pools** - there is no lawful bulk source of a private owner's
  phone or email in NSW, and unsolicited marketing email/SMS to individuals
  breaches the Spam Act 2003. Addressed physical mail is the compliant channel,
  so residential leads carry an address and nothing else by design.
* **Commercial and strata pools** - hotels, motels, caravan parks, gyms, clubs,
  sports centres and apartment buildings are businesses. Their published
  business contact details are fair game for B2B outreach, and OpenStreetMap
  already carries many of them.

This module pulls the published business contacts for the second group only.
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from common import http_post
from config import OVERPASS_MIRRORS

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
CACHE = os.path.join(DATA, "cache", "contacts")

CONTACT_KEYS = ("phone", "contact:phone", "contact:mobile", "website",
                "contact:website", "email", "contact:email", "operator",
                "operator:type", "brand", "addr:housenumber", "addr:street",
                "addr:suburb", "addr:postcode")

NEARBY = """[out:json][timeout:60];
(
  nwr(around:90,{lat},{lon})["tourism"~"hotel|motel|apartment|caravan_site|resort"];
  nwr(around:90,{lat},{lon})["leisure"~"sports_centre|fitness_centre|water_park"];
  nwr(around:90,{lat},{lon})["amenity"~"school|college|university|community_centre"];
  nwr(around:90,{lat},{lon})["club"];
  nwr(around:90,{lat},{lon})["building"="apartments"]["name"];
);
out tags center 12;
"""


def pick_contacts(tags):
    out = {}
    for k in CONTACT_KEYS:
        if tags.get(k):
            out[k.replace("contact:", "")] = tags[k]
    if tags.get("name"):
        out["name"] = tags["name"]
    return out


def query_nearby(lat, lon):
    key = f"{lat:.5f}_{lon:.5f}.json"
    path = os.path.join(CACHE, key)
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:  # noqa: BLE001
            pass
    q = NEARBY.format(lat=lat, lon=lon)
    for mirror in OVERPASS_MIRRORS:
        try:
            raw = http_post(mirror, {"data": q}, timeout=120, retries=1)
            doc = json.loads(raw.decode("utf-8", "replace"))
            os.makedirs(CACHE, exist_ok=True)
            with open(path, "w") as f:
                json.dump(doc, f)
            return doc
        except Exception:  # noqa: BLE001
            time.sleep(2)
    return {"elements": []}


def best_match(doc):
    """Pick the richest nearby business record."""
    best = None
    best_score = 0
    for el in doc.get("elements", []):
        c = pick_contacts(el.get("tags", {}))
        if not c.get("name"):
            continue
        score = sum(1 for k in ("phone", "mobile", "website", "email") if c.get(k)) * 2
        score += 1 if c.get("operator") else 0
        if score > best_score:
            best_score, best = score, c
    return best if best_score > 0 else None


def main():
    src = os.path.join(DATA, "leads.json")
    with open(src) as f:
        doc = json.load(f)
    leads = doc["leads"]

    targets = [p for p in leads
               if p.get("category") in ("public_commercial", "strata_or_commercial")]
    print(f"{len(targets)} commercial/strata leads to enrich "
          f"(of {len(leads)} total)", flush=True)
    if not targets:
        print("nothing to enrich")
        return

    done = [0]

    def work(p):
        try:
            return p, best_match(query_nearby(p["lat"], p["lon"]))
        except Exception:  # noqa: BLE001
            return p, None

    found = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(work, p) for p in targets]
        for fut in as_completed(futs):
            p, c = fut.result()
            done[0] += 1
            if c:
                p["contact"] = c
                found += 1
            if done[0] % 25 == 0:
                print(f"  [{done[0]}/{len(targets)}] contacts found: {found}",
                      flush=True)

    with open(src, "w") as f:
        json.dump(doc, f)
    with_phone = sum(1 for p in leads
                     if (p.get("contact") or {}).get("phone")
                     or (p.get("contact") or {}).get("mobile"))
    with_email = sum(1 for p in leads if (p.get("contact") or {}).get("email"))
    with_site = sum(1 for p in leads if (p.get("contact") or {}).get("website"))
    print(f"enriched {found} leads | phone: {with_phone} | "
          f"email: {with_email} | website: {with_site}")
    print("UPDATED", src)


if __name__ == "__main__":
    sys.exit(main())
