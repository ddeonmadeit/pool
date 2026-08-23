"""Pin down the decade for the strongest leads.

The bulk pass answers the qualifying question - is this pool 20+ years old? -
using 1998 imagery, and stops there. That leaves every pre-1998 pool labelled
simply "1992-98", when many of them are actually 1970s or 80s pools and are far
better renovation prospects.

This pass walks those pools back through 1991 / 1986 / 1978. It is deliberately
run over a shortlist rather than the whole city: each extra year costs another
round of imagery fetches, and the ranking only needs to be exact near the top.
Records are appended to the same journal, and later records win when scoring
reads it, so this can be re-run to extend the shortlist at any time.
"""
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import age_verify as av
from score import shape_era_score

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
JOURNAL = os.path.join(DATA, "pool_ages.jsonl")

LIMIT = int(os.environ.get("REFINE_LIMIT", "4000"))
WORKERS = int(os.environ.get("REFINE_WORKERS", "28"))

_lock = threading.Lock()


def latest_records():
    recs = {}
    with open(JOURNAL) as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            recs[r["osm_id"]] = r
    return recs


def prelim_rank(p):
    """Order the shortlist without knowing the decade yet."""
    lot = p.get("lot_m2") or 0
    lot_pts = 1.0 if 800 <= lot < 5000 else (0.7 if 400 <= lot < 800 else 0.35)
    return 0.5 * shape_era_score(p) + 0.5 * lot_pts


def main():
    with open(os.path.join(DATA, "pools_addressed.json")) as f:
        pools = {p["osm_id"]: p for p in json.load(f)["pools"]}
    recs = latest_records()

    # Only pools whose evidence currently stops at 1998 can be refined further.
    cands = []
    for oid, r in recs.items():
        if r.get("earliest_year") != 1998:
            continue
        if len(r.get("observations", [])) > 1:
            continue  # already walked back
        p = pools.get(oid)
        if p and p.get("address"):
            cands.append(p)

    cands.sort(key=prelim_rank, reverse=True)
    todo = cands[:LIMIT]
    print(f"{len(cands)} refinable pools; refining top {len(todo)}", flush=True)
    if not todo:
        return

    fh = open(JOURNAL, "a")
    n = [0]

    def work(p):
        try:
            base = recs[p["osm_id"]]["observations"]
            earliest, obs = av.refine_pool(p["ring"], base)
            return {"osm_id": p["osm_id"], "earliest_year": earliest,
                    "observations": obs}
        except Exception as e:  # noqa: BLE001
            return None

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(work, p) for p in todo]
        for fut in as_completed(futs):
            rec = fut.result()
            if rec is None:
                continue
            with _lock:
                fh.write(json.dumps(rec) + "\n")
                n[0] += 1
                if n[0] % 250 == 0:
                    fh.flush()
                    print(f"  refined {n[0]}/{len(todo)}", flush=True)
    fh.close()
    print("REFINE COMPLETE", n[0])


if __name__ == "__main__":
    sys.exit(main())
