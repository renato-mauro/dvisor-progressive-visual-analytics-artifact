"""Resolves every \\newcommand placeholder macro defined at the top of
anotacoes/draft/paperdraft.tex (\\TargetYear, \\NumRuns, \\HardwareDescription,
...) to the actual value this experiment run used or measured, and writes
them to output/tables/paper_placeholders.json / .txt for convenient copying
into the paper later. This script only reads already-collected data — it
never writes to paperdraft.tex itself.
"""
from __future__ import annotations

import json
import platform
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text())
OUTPUT = ROOT / "output"


def first_available_metadata() -> dict | None:
    meta_dir = OUTPUT / "metadata"
    for p in sorted(meta_dir.glob("*-run-001.json")):
        return json.loads(p.read_text())
    for p in sorted(meta_dir.glob("*.json")):
        if p.name != "dataset-info.json":
            return json.loads(p.read_text())
    return None


def main():
    dataset_info_path = OUTPUT / "metadata" / "dataset-info.json"
    dataset_info = json.loads(dataset_info_path.read_text()) if dataset_info_path.exists() else {}
    sample_meta = first_available_metadata() or {}

    n_runs_by_query = {}
    for query_id in ("Q1", "Q2", "Q3"):
        summary_path = OUTPUT / "derived" / f"{query_id}_summary.csv"
        if summary_path.exists():
            df = pd.read_csv(summary_path)
            n_runs_by_query[query_id] = int((~df["is_warmup"].astype(bool)).sum())

    placeholders = {
        "TargetYear": CONFIG["target_year"],
        "CesareanCode": CONFIG["cesarean_code"],
        "NumRuns": CONFIG["runs"]["measured_runs"],
        "NumRuns_actual_by_query": n_runs_by_query,
        "HardwareDescription": f"{sample_meta.get('cpu_model', '?')} ({sample_meta.get('cpu_count', '?')} logical CPUs, {round(sample_meta.get('total_memory_bytes', 0) / 1e9, 1)} GB RAM)" if sample_meta else None,
        "BrowserDescription": f"{sample_meta.get('browser_name', '?')} {sample_meta.get('browser_version', '?')}" if sample_meta else None,
        "NetworkDescription": "not controlled/measured by this harness — runs were made over whatever network connection the machine had at collection time (see config.runs.cache_policy for the one condition that *is* controlled)",
        "CachePolicy": CONFIG["runs"]["cache_policy"],
        "DatasetExactRows": dataset_info.get("dataset_rows"),
        "DatasetExactSize": dataset_info.get("dataset_bytes"),
        "dataset_sha256": dataset_info.get("dataset_sha256"),
        "operating_system_sample": sample_meta.get("operating_system"),
        "node_version_sample": sample_meta.get("node_version"),
        "python_version": platform.python_version(),
        "_note": "Generated from actually-collected run metadata/config, not hand-typed. Re-run analysis/resolve_paper_placeholders.py after collecting more runs to refresh. Copy these values into paperdraft.tex's \\newcommand definitions by hand — this script never edits that file.",
    }

    tables_dir = OUTPUT / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    out_path = tables_dir / "paper_placeholders.json"
    out_path.write_text(json.dumps(placeholders, indent=2, ensure_ascii=False))
    print("Wrote", out_path)
    for k, v in placeholders.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
