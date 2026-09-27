"""Build tables for physical-order and concurrency sensitivity."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DERIVED = ROOT / "output" / "derived"
TABLES = ROOT / "output" / "tables"

TASK_LABELS = {"Q1": "Q1 temporal", "Q2": "Q2 distribution", "Q3": "Q3 ranking"}
FIDELITY_COLUMNS = {"Q1": "rho_shape", "Q2": "js_similarity", "Q3": "spearman_rho"}
EVENTS_BY_QUERY = {
    "Q1": ("tnc", "tvf", "tsv"),
    "Q2": ("tnc", "tvf", "tsv"),
    "Q3": (
        "tnc_visible",
        "tvf_rank",
        "tvf_top5_80",
        "tvf_top5_100",
        "tcov90",
        "tsv",
    ),
}
EVENT_LABELS = {
    "tnc": "TNC",
    "tvf": "TVF",
    "tsv": "TSV",
    "tnc_visible": "TNC-visible",
    "tvf_rank": "TVF-rank",
    "tvf_top5_80": "TVF-top5-80",
    "tvf_top5_100": "TVF-top5-100",
    "tcov90": "TCov-90",
}
MILESTONES = [0.10, 0.25, 0.50, 0.75, 1.00]


def measured(df: pd.DataFrame) -> pd.DataFrame:
    if "is_warmup" not in df:
        return df
    values = df["is_warmup"]
    if values.dtype == bool:
        return df[~values]
    return df[~values.astype(str).str.lower().isin({"true", "1", "yes"})]


def quantiles(series: pd.Series) -> tuple[float, float, float]:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return (float("nan"),) * 3
    return float(values.median()), float(values.quantile(0.25)), float(values.quantile(0.75))


def load_summaries() -> pd.DataFrame:
    parts = []
    for query_id in ("Q1", "Q2", "Q3"):
        path = DERIVED / f"{query_id}_summary.csv"
        if not path.exists():
            continue
        part = measured(pd.read_csv(path))
        part.insert(0, "task", TASK_LABELS[query_id])
        parts.append(part)
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True).sort_values(["query_id", "threads", "dataset_id"])


def build_event_summary(runs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    scoped = runs.assign(scope=np.where(runs["dataset_kind"] == "canonical", "original", "permuted"))
    for (query_id, threads, scope), group in scoped.groupby(["query_id", "threads", "scope"], sort=True):
        for event in EVENTS_BY_QUERY[query_id]:
            values = group[f"{event}_processed_row_fraction"]
            median, q1, q3 = quantiles(values)
            rows.append(
                {
                    "task": TASK_LABELS[query_id],
                    "query_id": query_id,
                    "threads": int(threads),
                    "scope": scope,
                    "event": event,
                    "event_label": EVENT_LABELS[event],
                    "n_runs": len(group),
                    "n_reached": int(values.notna().sum()),
                    "row_fraction_median": median,
                    "row_fraction_iqr_low": q1,
                    "row_fraction_iqr_high": q3,
                    "anticipation_median": 1.0 - median if pd.notna(median) else float("nan"),
                }
            )
    return pd.DataFrame(rows)


def build_order_effects(runs: pd.DataFrame) -> pd.DataFrame:
    """Quantify dispersion across shuffled orders and locate the contextual
    canonical result relative to that ensemble."""
    rows = []
    for (query_id, threads), group in runs.groupby(["query_id", "threads"], sort=True):
        original = group[group["dataset_kind"] == "canonical"]
        permuted = group[group["dataset_kind"] == "permuted"]
        for event in EVENTS_BY_QUERY[query_id]:
            column = f"{event}_processed_row_fraction"
            shuffled = pd.to_numeric(permuted[column], errors="coerce").dropna()
            canonical = pd.to_numeric(original[column], errors="coerce").dropna()
            shuffled_median, shuffled_q1, shuffled_q3 = quantiles(shuffled)
            canonical_value = float(canonical.iloc[0]) if not canonical.empty else float("nan")
            rows.append(
                {
                    "task": TASK_LABELS[query_id],
                    "query_id": query_id,
                    "threads": int(threads),
                    "event": event,
                    "event_label": EVENT_LABELS[event],
                    "permuted_n_total": len(permuted),
                    "permuted_n_reached": len(shuffled),
                    "permuted_reach_rate": len(shuffled) / len(permuted) if len(permuted) else float("nan"),
                    "permuted_median": shuffled_median,
                    "permuted_iqr_low": shuffled_q1,
                    "permuted_iqr_high": shuffled_q3,
                    "permuted_iqr_width": shuffled_q3 - shuffled_q1,
                    "permuted_min": float(shuffled.min()) if not shuffled.empty else float("nan"),
                    "permuted_max": float(shuffled.max()) if not shuffled.empty else float("nan"),
                    "canonical_context_value": canonical_value,
                    "canonical_minus_permuted_median": canonical_value - shuffled_median,
                }
            )
    return pd.DataFrame(rows)


def load_frames() -> pd.DataFrame:
    parts = []
    for query_id in ("Q1", "Q2", "Q3"):
        path = DERIVED / f"{query_id}_frames.csv"
        if path.exists():
            parts.append(measured(pd.read_csv(path)))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def build_milestones(frames: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    per_run_rows = []
    for (query_id, run_id), group in frames.groupby(["query_id", "run_id"], sort=True):
        group = group.sort_values("processed_row_fraction")
        fidelity_column = FIDELITY_COLUMNS[query_id]
        for milestone in MILESTONES:
            reached = group[group["processed_row_fraction"] >= milestone]
            # Progressive answers exist only at frame boundaries. Select the
            # first observed answer that has reached the requested data
            # fraction rather than a possibly earlier nearest neighbor.
            row = reached.iloc[0] if not reached.empty else group.iloc[-1]
            per_run_rows.append(
                {
                    "task": TASK_LABELS[query_id],
                    "query_id": query_id,
                    "run_id": run_id,
                    "dataset_id": row["dataset_id"],
                    "dataset_kind": row["dataset_kind"],
                    "permutation_seed": row.get("permutation_seed", np.nan),
                    "threads": int(row["threads"]),
                    "target_row_fraction": milestone,
                    "selected_row_fraction": row["processed_row_fraction"],
                    "numerical_error": row.get("numerical_error", np.nan),
                    "visual_fidelity": row.get(fidelity_column, np.nan),
                    "domain_coverage": row.get("domain_coverage", np.nan),
                    "top_k_overlap": row.get("top_k_overlap", np.nan),
                    "covered_states": row.get("covered_states", np.nan),
                }
            )
    per_run = pd.DataFrame(per_run_rows)
    if per_run.empty:
        return per_run, per_run

    per_run["scope"] = np.where(per_run["dataset_kind"] == "canonical", "original", "permuted")
    summary_rows = []
    group_columns = ["query_id", "threads", "scope", "target_row_fraction"]
    for keys, group in per_run.groupby(group_columns, sort=True):
        query_id, threads, scope, target = keys
        out = {
            "task": TASK_LABELS[query_id],
            "query_id": query_id,
            "threads": int(threads),
            "scope": scope,
            "target_row_fraction": target,
            "n_runs": len(group),
        }
        for column in (
            "selected_row_fraction",
            "numerical_error",
            "visual_fidelity",
            "domain_coverage",
            "top_k_overlap",
            "covered_states",
        ):
            median, q1, q3 = quantiles(group[column])
            out[f"{column}_median"] = median
            out[f"{column}_iqr_low"] = q1
            out[f"{column}_iqr_high"] = q3
        summary_rows.append(out)
    return per_run, pd.DataFrame(summary_rows)


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    runs = load_summaries()
    if runs.empty:
        print("  (no derived summaries; skipping order tables)")
        return
    runs.to_csv(TABLES / "run_results.csv", index=False)
    q3_columns = [
        "run_id",
        "dataset_id",
        "dataset_kind",
        "threads",
    ] + [
        column
        for event in EVENTS_BY_QUERY["Q3"]
        for column in (
            f"{event}_frame_index",
            f"{event}_processed_row_fraction",
            f"{event}_elapsed_ms",
        )
    ]
    runs.loc[runs["query_id"] == "Q3", q3_columns].to_csv(
        TABLES / "q3_event_results.csv", index=False
    )
    build_event_summary(runs).to_csv(TABLES / "event_summary.csv", index=False)
    build_order_effects(runs).to_csv(TABLES / "order_effects.csv", index=False)

    frames = load_frames()
    milestones, milestone_summary = build_milestones(frames)
    milestones.to_csv(TABLES / "milestones_by_run.csv", index=False)
    milestone_summary.to_csv(TABLES / "milestone_summary.csv", index=False)
    print("Wrote run, event, and milestone order-sensitivity tables to", TABLES)


if __name__ == "__main__":
    main()
