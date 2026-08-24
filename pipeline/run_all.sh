#!/usr/bin/env bash
# End-to-end pipeline. Every stage is resumable, so re-running is cheap.
set -u
cd "$(dirname "$0")"
echo "=== [1/7] harvest pools from OpenStreetMap ==="
POOL_WORKERS=${POOL_WORKERS:-5} python3 -u fetch_pools.py || exit 1
echo "=== [2/7] attach addresses from NSW cadastre ==="
python3 -u geocode.py || exit 1
echo "=== [3/7] build suburb postcode + council lookup ==="
python3 -u suburbs.py || exit 1
echo "=== [4/7] date pools against historical aerial imagery ==="
AGE_WORKERS=${AGE_WORKERS:-14} python3 -u run_age.py || exit 1
echo "=== [5/7] score and rank leads ==="
python3 -u score.py || exit 1
echo "=== [6/7] enrich commercial contacts ==="
python3 -u enrich_contacts.py || true
echo "=== [7/7] estimate property values + build site ==="
python3 -u valuation.py || true
python3 -u build_site.py || exit 1
echo "=== pipeline complete ==="
