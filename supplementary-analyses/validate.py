"""Checks that make the offline simulations and the final reference auditable.

1. The final result of each query computed by DuckDB equals the final frame
   of every DVISOR execution in both phases (independent-engine check).
2. A logical one-worker merge of the per-row-group contributions, following
   the manifest order of each dataset, reproduces every frame of the thirty
   archived one-worker traces.
"""
from __future__ import annotations

import csv
import json

import common as c

KEYS = {"Q1": "month", "Q2": "maternal_age", "Q3": "state"}


def duckdb_final(query: str) -> list[dict]:
    with open(c.BLOCKS / f"duckdb_final_{query.lower()}.csv", newline="") as f:
        return [{k: int(v) for k, v in row.items()} for row in csv.DictReader(f)]


def main() -> None:
    blocks = c.Blocks()
    orders = c.permutation_orders()
    report = {"cross_engine": {}, "one_worker_replay": {}}

    for q in c.QUERIES:
        ref = c.canonical_result(duckdb_final(q))
        p1 = c.phase1_runs(q)
        p2 = c.phase2_runs(q)
        finals = [frames[-1]["result"] for frames in list(p1.values()) + list(p2.values())]
        equal = sum(1 for res in finals if c.canonical_result(res) == ref)
        report["cross_engine"][q] = {
            "groups": len(ref), "executions": len(finals), "identical_to_duckdb": equal,
        }

        replay = {}
        for ds in c.DATASETS:
            trace = p2[(ds, 1)]
            sim = c.simulate(blocks, q, orders[ds])
            same_len = len(trace) == len(sim)
            mismatches = sum(
                1 for a, b in zip(trace, sim)
                if c.canonical_result(a["result"]) != c.canonical_result(b["result"])
            )
            replay[ds] = {"frames": len(trace), "simulated_frames": len(sim),
                          "same_length": same_len, "mismatching_frames": mismatches}
        report["one_worker_replay"][q] = replay

    c.OUT.mkdir(exist_ok=True)
    (c.OUT / "validation.json").write_text(json.dumps(report, indent=2))
    for q, r in report["cross_engine"].items():
        print(q, r)
    for q, r in report["one_worker_replay"].items():
        bad = {ds: v for ds, v in r.items() if v["mismatching_frames"] or not v["same_length"]}
        print(q, "one-worker replay mismatches:", bad or "none")


if __name__ == "__main__":
    main()
