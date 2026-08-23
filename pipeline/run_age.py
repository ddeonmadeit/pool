"""Run historical-imagery dating over every pool, in parallel and resumably.

Results stream to data/pool_ages.jsonl so a long run can be interrupted and
restarted without losing work. Tiles are cached on disk, so neighbouring pools
that share imagery tiles cost almost nothing after the first.
"""
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import age_verify as av

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(DATA, "pool_ages.jsonl")

_lock = threading.Lock()

# The bulk pass only has to answer "is this pool 20+ years old?". Pinning the
# exact decade is a separate, much smaller job run over the shortlist.
REFINE = os.environ.get("AGE_REFINE", "0") == "1"
SKIP_UNADDRESSED = os.environ.get("AGE_ALL", "0") != "1"


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
    src = os.path.join(DATA, "pools_addressed.json")
    if not os.path.exists(src):
        src = os.path.join(DATA, "pools_raw.json")
    with open(src) as f:
        pools = json.load(f)["pools"]

    # A pool with no address can never become a mailable lead, so do not spend
    # imagery fetches on one.
    if SKIP_UNADDRESSED:
        pools = [p for p in pools if p.get("address")]

    done = load_done()
    todo = [p for p in pools if p["osm_id"] not in done]
    print(f"{len(pools)} pools, {len(done)} already dated, {len(todo)} to do",
          flush=True)

    workers = int(os.environ.get("AGE_WORKERS", "12"))
    counter = [0]
    fh = open(OUT, "a")

    def work(p):
        try:
            earliest, obs = av.date_pool(p["ring"], refine=REFINE)
            return {
                "osm_id": p["osm_id"],
                "earliest_year": earliest,
                "observations": obs,
            }
        except Exception as e:  # noqa: BLE001 - never let one pool kill the run
            return {"osm_id": p["osm_id"], "earliest_year": None,
                    "error": f"{type(e).__name__}: {e}"}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(work, p) for p in todo]
        for fut in as_completed(futs):
            rec = fut.result()
            with _lock:
                fh.write(json.dumps(rec) + "\n")
                counter[0] += 1
                if counter[0] % 200 == 0:
                    fh.flush()
                    print(f"  dated {counter[0]}/{len(todo)}", flush=True)
    fh.close()
    print("DONE ->", OUT)


if __name__ == "__main__":
    sys.exit(main())
