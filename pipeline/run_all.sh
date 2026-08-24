#!/usr/bin/env bash
# End-to-end pipeline. Every stage is resumable, so re-running is cheap.
set -u
cd "$(dirname "$0")"
echo "=== [1/10] harvest pools from OpenStreetMap ==="
POOL_WORKERS=${POOL_WORKERS:-5} python3 -u fetch_pools.py || exit 1
echo "=== [2/10] attach addresses from NSW cadastre ==="
python3 -u geocode.py || exit 1
echo "=== [3/10] build suburb postcode + council lookup ==="
python3 -u suburbs.py || exit 1
echo "=== [4/10] date pools against historical aerial imagery ==="
AGE_WORKERS=${AGE_WORKERS:-14} python3 -u run_age.py || exit 1
echo "=== [5/10] read each pool's finish off current imagery ==="
python3 -u run_renovation.py || exit 1
echo "=== [6/10] score and rank leads ==="
python3 -u score.py || exit 1
echo "=== [7/10] enrich commercial contacts ==="
python3 -u enrich_contacts.py || true
echo "=== [8/10] estimate property values ==="
python3 -u valuation.py || true
echo "=== [9/10] verify addresses against the NSW address points ==="
python3 -u verify_addresses.py || true
# score.py already ran the mail gate, but it ran before the valuation and the
# address check existed, so every lead was blocked on value_unknown. Re-running
# it here is what makes the gate see the enrichment above.
python3 -u requalify.py || exit 1
echo "=== [10/10] build site ==="
python3 -u build_site.py || exit 1
echo "=== pipeline complete ==="
