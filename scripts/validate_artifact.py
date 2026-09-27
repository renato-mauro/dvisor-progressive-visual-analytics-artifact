"""Validate both collections and their shared final answers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
PHASE1 = ROOT / "phases" / "01-fixed-order"
PHASE2 = ROOT / "phases" / "02-order-sensitivity"
REPORT_PATH = ROOT / "validation" / "integrated_validation.json"


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def canonical_result_hash(rows: list[dict]) -> str:
    normalized = [{key: row[key] for key in sorted(row)} for row in rows]
    normalized.sort(key=lambda row: json.dumps(row, separators=(",", ":")))
    payload = json.dumps(normalized, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def validate_phase1() -> dict:
    expected = []
    for query_id in ("Q1", "Q2", "Q3"):
        expected.append((query_id, f"{query_id}-warmup-001"))
        expected.extend((query_id, f"{query_id}-run-{index:03d}") for index in range(1, 11))

    missing: list[str] = []
    invalid: list[dict] = []
    hashes = {query_id: set() for query_id in ("Q1", "Q2", "Q3")}
    for query_id, run_id in expected:
        raw_path = PHASE1 / "output" / "raw" / query_id / f"{run_id}.jsonl"
        metadata_path = PHASE1 / "output" / "metadata" / f"{run_id}.json"
        absent = [str(path.relative_to(ROOT)) for path in (raw_path, metadata_path) if not path.exists()]
        if absent:
            missing.extend(absent)
            continue
        frames = load_jsonl(raw_path)
        errors = []
        if not frames:
            errors.append("empty trace")
        else:
            fractions = [float(frame["processed_fraction"]) for frame in frames]
            if any(b < a for a, b in zip(fractions, fractions[1:])):
                errors.append("non-monotonic fragment progress")
            if not frames[-1].get("is_final"):
                errors.append("last frame is not final")
            if abs(fractions[-1] - 1.0) > 1e-12:
                errors.append("final fragment progress is not one")
            hashes[query_id].add(canonical_result_hash(frames[-1]["result"]))
        if errors:
            invalid.append({"run_id": run_id, "errors": errors})

    dataset = json.loads((PHASE1 / "output" / "metadata" / "dataset-info.json").read_text())
    return {
        "expected_runs_including_warmups": len(expected),
        "missing": missing,
        "invalid": invalid,
        "dataset": dataset,
        "final_result_hashes_by_query": {key: sorted(value) for key, value in hashes.items()},
        "complete": not missing and not invalid and all(len(value) == 1 for value in hashes.values()),
    }


def main() -> None:
    subprocess.run(
        [sys.executable, str(PHASE2 / "analysis" / "validate_collection.py")],
        cwd=PHASE2,
        check=True,
    )
    phase1 = validate_phase1()
    phase2 = json.loads(
        (PHASE2 / "output" / "validation" / "collection_validation.json").read_text()
    )
    phase1_hashes = phase1["final_result_hashes_by_query"]
    phase2_hashes = phase2["final_result_hashes_by_query"]
    cross_phase_match = phase1_hashes == phase2_hashes
    dataset_ok = (
        phase1["dataset"].get("dataset_rows") == 28_789_402
        and phase1["dataset"].get("row_groups") == 270
        and phase1["dataset"].get("dataset_bytes") == 917_760_169
        and phase1["dataset"].get("dataset_sha256")
        == "11ed73f53fa129c88d72440f8e0250bcbc1b6cba34955ac0de9805763f892327"
    )
    report = {
        "phase1": phase1,
        "phase2": phase2,
        "cross_phase_final_results_match": cross_phase_match,
        "shared_identity_dataset_matches_expected": dataset_ok,
        "complete": phase1["complete"] and phase2["complete"] and cross_phase_match and dataset_ok,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Phase 1: {phase1['expected_runs_including_warmups']} traces; complete={phase1['complete']}")
    print(f"Phase 2: {phase2['valid_runs']} measured traces; complete={phase2['complete']}")
    print(f"Cross-phase final results match: {cross_phase_match}")
    print(f"Shared identity dataset matches expected: {dataset_ok}")
    if not report["complete"]:
        raise RuntimeError(f"Integrated validation failed; see {REPORT_PATH}")


if __name__ == "__main__":
    main()
