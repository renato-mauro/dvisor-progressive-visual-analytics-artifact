"""Stage 1 of the order-sensitivity offline pipeline.

Reads every dataset x query x thread-count trace, computes per-frame metrics
and per-run derived times (analyze.py), and writes:

    output/derived/<query_id>_frames.csv    (one row per run x frame)
    output/derived/<query_id>_summary.csv   (one row per run)

Warm-up runs, if explicitly requested, remain in both CSV layers with an
``is_warmup`` marker. The order-sensitivity table and figure builders exclude
them explicitly; the configured primary experiment has zero warm-ups.

Run with `python analysis/run_analysis.py` (from the project root, with the
venv active) or via `python analysis/build_all.py` for the full pipeline.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from analyze import ANALYZERS, compute_derived_times

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text())
OUTPUT = ROOT / "output"


def load_frames(path: Path) -> list[dict]:
    frames = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                frames.append(json.loads(line))
    return frames


def flatten_derived_time(prefix: str, d: dict | None) -> dict:
    if d is None:
        return {
            f"{prefix}_frame_index": None,
            f"{prefix}_elapsed_ms": None,
            f"{prefix}_fragment_fraction": None,
            f"{prefix}_processed_rows": None,
            f"{prefix}_processed_row_fraction": None,
            f"{prefix}_transferred_bytes": None,
        }
    return {
        f"{prefix}_frame_index": d["frame_index"],
        f"{prefix}_elapsed_ms": d["elapsed_ms"],
        f"{prefix}_fragment_fraction": d["fragment_fraction"],
        f"{prefix}_processed_rows": d["processed_rows"],
        f"{prefix}_processed_row_fraction": d["processed_row_fraction"],
        f"{prefix}_transferred_bytes": d["transferred_bytes"],
    }


def analyze_query(query_id: str) -> tuple[list[dict], list[dict]]:
    raw_dir = OUTPUT / "raw" / query_id
    run_files = sorted(raw_dir.glob("*.jsonl"))
    if not run_files:
        print(f"  (no raw runs found for {query_id} in {raw_dir})")
        return [], []

    analyzer = ANALYZERS[query_id]
    all_frame_rows: list[dict] = []
    summary_rows: list[dict] = []

    for run_file in run_files:
        run_id = run_file.stem
        frames = load_frames(run_file)
        if not frames:
            continue
        meta_path = OUTPUT / "metadata" / f"{run_id}.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}

        result = analyzer(frames, CONFIG)
        frame_rows = result["frames"]
        all_frame_rows.extend(frame_rows)

        derived = compute_derived_times(frame_rows, query_id, CONFIG)
        last = frame_rows[-1]
        summary = {
            "run_id": run_id,
            "query_id": query_id,
            "is_warmup": meta.get("is_warmup", "warmup" in run_id),
            "dataset_id": meta.get("dataset_id", last.get("dataset_id")),
            "dataset_kind": meta.get("dataset_kind", last.get("dataset_kind")),
            "dataset_url": meta.get("dataset_url"),
            "permutation_seed": meta.get("permutation_seed", last.get("permutation_seed")),
            "permutation_order_sha256": meta.get("permutation_order_sha256"),
            "threads": meta.get("threads", last.get("threads")),
            "execution_sequence": meta.get("execution_sequence", last.get("execution_sequence")),
            "execution_order_seed": meta.get("execution_order_seed"),
            "total_elapsed_ms": last["elapsed_ms"],
            "total_fragments": last["total_fragments"],
            "period_start_year": last["period_start_year"],
            "period_end_year": last["period_end_year"],
            "period_total_rows": last["period_total_rows"],
            "total_transferred_bytes": last["transferred_bytes"],
            "total_request_count": last["request_count"],
            "final_result_sha256": meta.get("final_result_sha256"),
        }
        for event_name, event_value in derived.items():
            summary.update(flatten_derived_time(event_name, event_value))
        summary_rows.append(summary)

    return all_frame_rows, summary_rows


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    derived_dir = OUTPUT / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)

    for query_id in ANALYZERS:
        print(f"Analyzing {query_id} ...")
        frame_rows, summary_rows = analyze_query(query_id)
        write_csv(derived_dir / f"{query_id}_frames.csv", frame_rows)
        write_csv(derived_dir / f"{query_id}_summary.csv", summary_rows)
        print(f"  {len(summary_rows)} run(s), {len(frame_rows)} frame-rows written.")

    print("\nDerived tables written to", derived_dir)


if __name__ == "__main__":
    main()
