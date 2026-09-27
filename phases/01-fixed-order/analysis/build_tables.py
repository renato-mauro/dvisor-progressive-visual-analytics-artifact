"""Build publication tables from the derived per-frame and per-run CSVs.

The primary progress coordinate is processed_row_fraction: cumulative query-
relevant input rows divided by the total rows in the period covered by the
query. fragment_fraction is retained as an execution diagnostic but is never
labelled as a fraction of data.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import metrics as m
from analyze import COVERAGE_GATED, FIDELITY_COLUMN

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text())
DERIVED = ROOT / "output" / "derived"
TABLES = ROOT / "output" / "tables"

TASK_LABELS = {"Q1": "Q1 temporal", "Q2": "Q2 distribution", "Q3": "Q3 ranking"}
METRIC_LABELS = {"Q1": "Pearson", "Q2": "Jensen-Shannon", "Q3": "Spearman"}
MILESTONES = [0.25, 0.50, 0.75, 1.00]
FIDELITY_THRESHOLDS = [0.85, 0.90, 0.925, 0.95]
NMAE_THRESHOLDS = [0.025, 0.05, 0.10]


def median_iqr(series: pd.Series) -> tuple[float, float, float]:
    s = series.dropna()
    if s.empty:
        return (float("nan"),) * 3
    return float(s.median()), float(s.quantile(0.25)), float(s.quantile(0.75))


def fmt_ms(x: float) -> str:
    return "n/a" if pd.isna(x) else f"{int(x + 0.5):,}"


def fmt_pct(x: float) -> str:
    return "n/a" if pd.isna(x) else f"{100 * x:.1f}\\%"


def _measured_frames(query_id: str) -> pd.DataFrame:
    frames = pd.read_csv(DERIVED / f"{query_id}_frames.csv")
    summary = pd.read_csv(DERIVED / f"{query_id}_summary.csv")
    measured_ids = set(summary[~summary["is_warmup"].astype(bool)]["run_id"])
    return frames[frames["run_id"].isin(measured_ids)]


def _stable_event(
    run_frames: pd.DataFrame,
    column: str,
    threshold: float,
    direction: str,
    coverage_gated: bool = False,
) -> pd.Series | None:
    ordered = run_frames.sort_values("frame_index")
    values = []
    for _, row in ordered.iterrows():
        if coverage_gated and not bool(row.get("eligible_for_fidelity", False)):
            values.append(None)
        else:
            value = row.get(column, np.nan)
            values.append(None if pd.isna(value) else float(value))
    idx = m.first_stable_run(
        values,
        threshold,
        int(CONFIG["thresholds"]["persistence_k"]),
        direction,
    )
    return None if idx < 0 else ordered.iloc[idx]


def build_main_results_table() -> pd.DataFrame:
    rows = []
    for query_id in ("Q1", "Q2", "Q3"):
        path = DERIVED / f"{query_id}_summary.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path)
        measured = df[~df["is_warmup"].astype(bool)]
        final_med, final_q1, final_q3 = median_iqr(measured["total_elapsed_ms"])

        row = {
            "task": TASK_LABELS[query_id],
            "n_runs": len(measured),
            "period_start_year": int(measured["period_start_year"].iloc[0]),
            "period_end_year": int(measured["period_end_year"].iloc[0]),
            "period_total_rows": int(measured["period_total_rows"].iloc[0]),
            "final_time_ms_median": final_med,
            "final_time_ms_iqr_low": final_q1,
            "final_time_ms_iqr_high": final_q3,
            "visual_metric": METRIC_LABELS[query_id],
        }
        for event in ("tnc", "tvf", "tsv"):
            row[f"{event}_ms_median"] = median_iqr(measured[f"{event}_elapsed_ms"])[0]
            row[f"{event}_row_fraction_median"] = median_iqr(
                measured[f"{event}_processed_row_fraction"]
            )[0]
            row[f"{event}_fragment_fraction_median"] = median_iqr(
                measured[f"{event}_fragment_fraction"]
            )[0]
        rows.append(row)
    return pd.DataFrame(rows)


def build_milestones_table() -> pd.DataFrame:
    rows = []
    for query_id in ("Q1", "Q2", "Q3"):
        frames = _measured_frames(query_id)
        fidelity_col = FIDELITY_COLUMN[query_id]
        for milestone in MILESTONES:
            nmae_values = []
            fidelity_values = []
            coverage_values = []
            selected_row_fractions = []
            for _, run_frames in frames.groupby("run_id"):
                idx = (run_frames["processed_row_fraction"] - milestone).abs().idxmin()
                row = run_frames.loc[idx]
                selected_row_fractions.append(row["processed_row_fraction"])
                nmae_values.append(row["numerical_error"])
                fidelity_values.append(row.get(fidelity_col, np.nan))
                coverage_values.append(row.get("domain_coverage", np.nan))
            rows.append(
                {
                    "task": TASK_LABELS[query_id],
                    "target_row_fraction": milestone,
                    "selected_row_fraction_median": float(pd.Series(selected_row_fractions).median()),
                    "numerical_error_median": float(pd.Series(nmae_values).median()),
                    "visual_fidelity_median": float(pd.Series(fidelity_values).median()),
                    "domain_coverage_median": float(pd.Series(coverage_values).median()),
                    "visual_metric": METRIC_LABELS[query_id],
                }
            )
    return pd.DataFrame(rows)


def build_fidelity_sensitivity_table() -> pd.DataFrame:
    rows = []
    for query_id in ("Q1", "Q2", "Q3"):
        frames = _measured_frames(query_id)
        for threshold in FIDELITY_THRESHOLDS:
            events = []
            for _, run_frames in frames.groupby("run_id"):
                event = _stable_event(
                    run_frames,
                    FIDELITY_COLUMN[query_id],
                    threshold,
                    "above",
                    COVERAGE_GATED[query_id],
                )
                if event is not None:
                    events.append(event)
            rows.append(
                {
                    "task": TASK_LABELS[query_id],
                    "threshold": threshold,
                    "n_runs_reaching_event": len(events),
                    "tvf_elapsed_ms_median": float(pd.Series([x["elapsed_ms"] for x in events]).median()),
                    "tvf_row_fraction_median": float(pd.Series([x["processed_row_fraction"] for x in events]).median()),
                    "tvf_fragment_fraction_median": float(pd.Series([x["fragment_fraction"] for x in events]).median()),
                }
            )
    return pd.DataFrame(rows)


def build_q2_nmae_sensitivity_table() -> pd.DataFrame:
    frames = _measured_frames("Q2")
    measures = {
        "compositional_nmae": "Compositional NMAE",
        "progress_adjusted_nmae": "Progress-adjusted count NMAE",
        "raw_count_completeness_error": "Raw-count completeness error",
    }
    rows = []
    for column, label in measures.items():
        for threshold in NMAE_THRESHOLDS:
            events = []
            for _, run_frames in frames.groupby("run_id"):
                event = _stable_event(run_frames, column, threshold, "below")
                if event is not None:
                    events.append(event)
            rows.append(
                {
                    "measure": label,
                    "threshold": threshold,
                    "n_runs_reaching_event": len(events),
                    "elapsed_ms_median": float(pd.Series([x["elapsed_ms"] for x in events]).median()),
                    "row_fraction_median": float(pd.Series([x["processed_row_fraction"] for x in events]).median()),
                    "fragment_fraction_median": float(pd.Series([x["fragment_fraction"] for x in events]).median()),
                }
            )
    return pd.DataFrame(rows)


def write_main_results_tex(df: pd.DataFrame, path: Path):
    lines = [
        "% Auto-generated by analysis/build_tables.py. Do not edit by hand.",
        "\\begin{table}[H]",
        "\\centering",
        "\\caption{Median final time and convergence events. Parentheses contain the median fraction of query-relevant rows processed.}",
        "\\label{tab:main-results-generated}",
        "\\small",
        "\\begin{tabularx}{\\textwidth}{L{2.5cm} Y Y Y Y}",
        "\\toprule",
        "\\textbf{Task} & \\textbf{Final time} & \\textbf{TNC} & \\textbf{TVF} & \\textbf{TSV} \\\\",
        "\\midrule",
    ]
    for _, row in df.iterrows():
        cells = []
        for event in ("tnc", "tvf", "tsv"):
            cells.append(
                f"{fmt_ms(row[f'{event}_ms_median'])} ms "
                f"({fmt_pct(row[f'{event}_row_fraction_median'])})"
            )
        lines.append(
            f"{row['task']} & {fmt_ms(row['final_time_ms_median'])} ms & "
            + " & ".join(cells)
            + " \\\\"
        )
    lines += ["\\bottomrule", "\\end{tabularx}", "\\end{table}", ""]
    path.write_text("\n".join(lines))


def write_milestones_tex(df: pd.DataFrame, path: Path):
    lines = [
        "% Auto-generated by analysis/build_tables.py. Do not edit by hand.",
        "\\begin{table}[H]",
        "\\centering",
        "\\caption{Median numerical error, visual fidelity, and domain coverage at processed-row milestones.}",
        "\\label{tab:milestones-generated}",
        "\\small",
        "\\begin{tabularx}{\\textwidth}{L{3.05cm} L{1.0cm} L{1.25cm} L{1.25cm} Y L{1.65cm}}",
        "\\toprule",
        "{\\footnotesize\\textbf{Task}} & {\\footnotesize\\textbf{Rows}} & {\\footnotesize\\textbf{NMAE}} & {\\footnotesize\\shortstack{\\textbf{Visual}\\\\\\textbf{fidelity}}} & {\\footnotesize\\textbf{Method}} & {\\footnotesize\\textbf{Coverage}} \\\\",
        "\\midrule",
    ]
    for _, row in df.iterrows():
        nmae = "n/a" if pd.isna(row["numerical_error_median"]) else f"{row['numerical_error_median']:.3f}"
        fidelity = "n/a" if pd.isna(row["visual_fidelity_median"]) else f"{row['visual_fidelity_median']:.3f}"
        coverage = fmt_pct(row["domain_coverage_median"])
        lines.append(
            f"{row['task']} & {fmt_pct(row['target_row_fraction'])} & {nmae} & "
            f"{fidelity} & {row['visual_metric']} & {coverage} \\\\"
        )
    lines += ["\\bottomrule", "\\end{tabularx}", "\\end{table}", ""]
    path.write_text("\n".join(lines))


def main():
    TABLES.mkdir(parents=True, exist_ok=True)

    main_results = build_main_results_table()
    main_results.to_csv(TABLES / "main_results.csv", index=False)
    write_main_results_tex(main_results, TABLES / "main_results.tex")

    milestones = build_milestones_table()
    milestones.to_csv(TABLES / "milestones.csv", index=False)
    write_milestones_tex(milestones, TABLES / "milestones.tex")

    fidelity = build_fidelity_sensitivity_table()
    fidelity.to_csv(TABLES / "fidelity_sensitivity.csv", index=False)

    q2_nmae = build_q2_nmae_sensitivity_table()
    q2_nmae.to_csv(TABLES / "q2_nmae_sensitivity.csv", index=False)

    print("Wrote main results, milestones, fidelity sensitivity, and Q2 NMAE sensitivity tables to", TABLES)


if __name__ == "__main__":
    main()
