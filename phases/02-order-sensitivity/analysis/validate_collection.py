"""Validate completeness and invariants of the 90-run collection."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text())
OUTPUT = ROOT / "output"


def run_id(query_id: str, dataset_id: str, threads: int, index: int = 1) -> str:
    return f"{query_id}-{dataset_id}-t{threads:02d}-run-{index:03d}"


def expected_runs() -> list[tuple[str, str, int, str]]:
    rows = []
    for dataset in CONFIG["datasets"]:
        for threads in CONFIG["thread_counts"]:
            for query_id in ("Q1", "Q2", "Q3"):
                for index in range(1, int(CONFIG["runs"]["measured_runs"]) + 1):
                    rows.append((query_id, dataset["id"], int(threads), run_id(query_id, dataset["id"], int(threads), index)))
    return rows


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def validate_run(query_id: str, dataset_id: str, threads: int, rid: str) -> dict:
    raw_path = OUTPUT / "raw" / query_id / f"{rid}.jsonl"
    metadata_path = OUTPUT / "metadata" / f"{rid}.json"
    if not raw_path.exists() or not metadata_path.exists():
        missing = []
        if not raw_path.exists():
            missing.append(str(raw_path.relative_to(ROOT)))
        if not metadata_path.exists():
            missing.append(str(metadata_path.relative_to(ROOT)))
        return {"run_id": rid, "status": "missing", "missing": missing}

    frames = load_jsonl(raw_path)
    metadata = json.loads(metadata_path.read_text())
    errors = []
    if not frames:
        errors.append("empty trace")
    else:
        if frames[-1].get("is_final") is not True:
            errors.append("last frame is not marked final")
        fractions = [frame.get("processed_row_fraction") for frame in frames]
        if any(value is None for value in fractions):
            errors.append("missing processed_row_fraction")
        elif any(b + 1e-15 < a for a, b in zip(fractions, fractions[1:])):
            errors.append("processed_row_fraction is not monotonic")
        elif not math.isclose(float(fractions[-1]), 1.0, rel_tol=0.0, abs_tol=1e-12):
            errors.append("final processed_row_fraction is not 1")
        if frames[-1].get("frame_index") != frames[-1].get("total_fragments"):
            errors.append("final frame index differs from total_fragments")
        if query_id != "Q1" and int(frames[-1].get("period_total_rows", -1)) != int(CONFIG["expected_dataset_rows"]):
            errors.append("unexpected full-period row count")

    expected_fields = {
        "query_id": query_id,
        "dataset_id": dataset_id,
        "threads": threads,
    }
    for key, expected in expected_fields.items():
        if metadata.get(key) != expected:
            errors.append(f"metadata {key}={metadata.get(key)!r}, expected {expected!r}")
        if frames and frames[-1].get(key) != expected:
            errors.append(f"trace {key}={frames[-1].get(key)!r}, expected {expected!r}")
    if metadata.get("is_warmup") is not False:
        errors.append("measured-run metadata is not marked is_warmup=false")
    if not metadata.get("final_result_sha256"):
        errors.append("missing final_result_sha256")

    return {
        "run_id": rid,
        "status": "invalid" if errors else "ok",
        "errors": errors,
        "frames": len(frames),
        "period_total_rows": frames[-1].get("period_total_rows") if frames else None,
        "final_result_sha256": metadata.get("final_result_sha256"),
    }


def validate(allow_incomplete: bool = False) -> dict:
    expected = expected_runs()
    results = [validate_run(*row) for row in expected]
    missing = [row for row in results if row["status"] == "missing"]
    invalid = [row for row in results if row["status"] == "invalid"]

    hash_sets: dict[str, set[str]] = {"Q1": set(), "Q2": set(), "Q3": set()}
    for (query_id, _, _, _), result in zip(expected, results):
        if result["status"] == "ok" and result.get("final_result_sha256"):
            hash_sets[query_id].add(result["final_result_sha256"])
    hash_mismatches = {
        query_id: sorted(values)
        for query_id, values in hash_sets.items()
        if len(values) > 1
    }
    execution_sequences = []
    for result in results:
        if result["status"] != "ok":
            continue
        metadata_path = OUTPUT / "metadata" / f"{result['run_id']}.json"
        execution_sequences.append(json.loads(metadata_path.read_text()).get("execution_sequence"))
    sequence_error = None
    if not missing and not invalid:
        expected_sequences = list(range(1, len(expected) + 1))
        if sorted(execution_sequences) != expected_sequences:
            sequence_error = "execution_sequence values are not exactly 1..90"

    report = {
        "expected_measured_runs": len(expected),
        "valid_runs": sum(row["status"] == "ok" for row in results),
        "missing_runs": [row["run_id"] for row in missing],
        "invalid_runs": invalid,
        "final_result_hashes_by_query": {key: sorted(value) for key, value in hash_sets.items()},
        "final_result_hash_mismatches": hash_mismatches,
        "execution_sequence_error": sequence_error,
        "complete": not missing and not invalid and not hash_mismatches and sequence_error is None,
    }
    out_dir = OUTPUT / "validation"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "collection_validation.json").write_text(json.dumps(report, indent=2) + "\n")

    print(f"Expected: {len(expected)} measured runs")
    print(f"Valid: {report['valid_runs']}; missing: {len(missing)}; invalid: {len(invalid)}")
    if hash_mismatches:
        print("Final-result mismatch:", ", ".join(hash_mismatches))
    if sequence_error:
        print("Execution-order mismatch:", sequence_error)
    if not report["complete"] and not allow_incomplete:
        raise RuntimeError("Collection validation failed; see output/validation/collection_validation.json")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()
    validate(allow_incomplete=args.allow_incomplete)


if __name__ == "__main__":
    main()
