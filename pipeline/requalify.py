"""Re-run the mail-qualification gate over an existing data/leads.json.

`score.py` applies the same gate as part of a full pipeline run, but a full run
needs data/pools_addressed.json and the imagery cache, both of which are
regenerable intermediates and not carried in the repository. Everything
qualify.py needs - the tone readings, the dating evidence with its match
offsets, the cadastre match quality and offset, the valuation - is already
recorded on each lead, so the gate can be re-applied, re-argued and re-tuned
against the shipped lead file without refetching a single tile.
"""
import json
import os
import sys
from datetime import date

import qualify

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")


def main():
    path = os.path.join(DATA, "leads.json")
    with open(path) as f:
        doc = json.load(f)
    leads = doc["leads"]

    stats = qualify.apply(leads)
    qualify.report(leads, stats)

    doc["qualified"] = str(date.today())
    doc["mail_ready"] = stats["ready"]
    with open(path, "w") as f:
        json.dump(doc, f)
    print("WROTE", path)


if __name__ == "__main__":
    sys.exit(main())
