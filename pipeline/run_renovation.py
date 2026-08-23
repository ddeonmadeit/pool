"""Classify every lead as untouched, already renovated, neglected or gone.

Parallel and resumable in the same way as the dating pass: results stream to
data/pool_reno.jsonl and cached tiles mean re-runs cost almost nothing.
"""
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import age_verify as av
import renovation as rv

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(DATA, "pool_reno.jsonl")

_lock = threading.Lock()


def load_done():
    done = set()
    if os.path.exists(OUT):
        with open(OUT) as f:
            for line in f:
                try:
                    done.add(json.loads(line)["osm_id"])
                except Exception:  # noqa: BLE001 - tolerate a torn final line
                    pass
    return done


def main():
    with open(os.path.join(DATA, "pools_addressed.json")) as f:
        pools = {p["osm_id"]: p for p in json.load(f)["pools"]}
    with open(os.path.join(DATA, "leads.json")) as f:
        leads = json.load(f)["leads"]

    done = load_done()
    todo = [p for p in leads if p["osm_id"] not in done]
    print("%d leads, %d already done, %d to do" % (len(leads), len(done), len(todo)),
          flush=True)
    if not todo:
        return

    workers = int(os.environ.get("RENO_WORKERS", "20"))
    fh = open(OUT, "a")
    n = [0]

    def work(lead):
        oid = lead["osm_id"]
        src = pools.get(oid)
        if not src or not src.get("ring"):
            return {"osm_id": oid, "state": "unknown", "reason": "no geometry"}
        ring = src["ring"]
        try:
            pnow = rv.probe(rv.current_tile, ring)
            p05 = rv.probe(lambda z, x, y: av.fetch_tile(2005, z, x, y), ring)
            p98 = rv.probe(lambda z, x, y: av.fetch_tile(1998, z, x, y), ring)
            rec = rv.classify(p98, p05, pnow)
            rec["osm_id"] = oid
            return rec
        except Exception as e:  # noqa: BLE001 - one bad pool must not stop the run
            return {"osm_id": oid, "state": "unknown",
                    "reason": "%s: %s" % (type(e).__name__, e)}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(work, p) for p in todo]
        for fut in as_completed(futs):
            rec = fut.result()
            with _lock:
                fh.write(json.dumps(rec) + "\n")
                n[0] += 1
                if n[0] % 500 == 0:
                    fh.flush()
                    print("  classified %d/%d" % (n[0], len(todo)), flush=True)
    fh.close()
    print("RENOVATION PASS COMPLETE ->", OUT)


if __name__ == "__main__":
    sys.exit(main())
