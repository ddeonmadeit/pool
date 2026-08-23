#!/usr/bin/env bash
# End-to-end pipeline. Every stage is resumable, so re-running is cheap.
set -u
cd "$(dirname "$0")"
echo "=== [1/5] harvest pools from OpenStreetMap ==="
POOL_WORKERS=${POOL_WORKERS:-5} python3 -u fetch_pools.py || exit 1
echo "=== [2/5] attach addresses from NSW cadastre ==="
python3 -u geocode.py || exit 1
echo "=== [3/5] date pools against historical aerial imagery ==="
AGE_WORKERS=${AGE_WORKERS:-14} python3 -u run_age.py || exit 1
echo "=== [4/5] score and rank leads ==="
python3 -u score.py || exit 1
echo "=== [5/5] build dashboard + CSV extracts ==="
python3 -u build_dashboard.py || exit 1
echo "=== pipeline complete ==="
