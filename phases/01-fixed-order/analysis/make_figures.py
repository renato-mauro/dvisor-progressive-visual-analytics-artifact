"""Stage 3: derived CSVs (+ the representative run's raw trace) -> every
figure used in the paper (Results section, plus one Methods-section figure
showing each task's final, converged view). All figures are saved as PDF
(vector; pdf.fonttype=42 so text stays real, searchable/editable text rather
than embedded bitmaps or Type 3 outlines) plus a PNG twin at the same size
for quick inspection — the PDF is what belongs in the manuscript.

For each task, one run is picked as the "representative" run (the measured
run whose total elapsed time is closest to the median across measured runs)
to draw single-trace figures (snapshots, per-run convergence curves) from —
averaging frame-by-frame values across runs with slightly different fragment
arrival timing would not correspond to any real execution, whereas picking
one genuine, typical run does.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["pdf.fonttype"] = 42
matplotlib.rcParams["ps.fonttype"] = 42
matplotlib.rcParams["font.size"] = 9
import matplotlib.pyplot as plt
import pandas as pd

from analyze import FIDELITY_COLUMN, STABILITY_COLUMN

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text())
DERIVED = ROOT / "output" / "derived"
RAW = ROOT / "output" / "raw"
FIGURES = ROOT / "output" / "figures"

TASK_TITLES = {"Q1": "Q1: Temporal shape", "Q2": "Q2: Distribution shape", "Q3": "Q3: Ranking"}
FIDELITY_LABELS = {"Q1": "Pearson $\\rho$ (shape)", "Q2": "Jensen–Shannon similarity", "Q3": "Spearman $\\rho_s$"}
STABILITY_LABELS = {"Q1": "Pearson $\\rho$ (stability)", "Q2": "JS similarity (stability)", "Q3": "Spearman $\\rho_s$ (stability)"}
MILESTONES = [0.25, 0.50, 0.75, 1.00]
MILESTONE_LABELS = ["25% of rows", "50% of rows", "75% of rows", "Final"]
MONTH_INITIALS = list("JFMAMJJASOND")
STATE_ABBREVIATIONS = {
    11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO",
    21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL",
    28: "SE", 29: "BA", 31: "MG", 32: "ES", 33: "RJ", 35: "SP", 41: "PR",
    42: "SC", 43: "RS", 50: "MS", 51: "MT", 52: "GO", 53: "DF",
}


def savefig(fig, name: str):
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(FIGURES / f"{name}.png", bbox_inches="tight", dpi=200)
    plt.close(fig)


def load_frames(path: Path) -> list[dict]:
    frames = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                frames.append(json.loads(line))
    return frames


def representative_run_id(query_id: str) -> str | None:
    summary_path = DERIVED / f"{query_id}_summary.csv"
    if not summary_path.exists():
        return None
    df = pd.read_csv(summary_path)
    measured = df[~df["is_warmup"].astype(bool)]
    if measured.empty:
        return None
    med = measured["total_elapsed_ms"].median()
    return measured.iloc[(measured["total_elapsed_ms"] - med).abs().argsort().iloc[0]]["run_id"]


def result_total_rows(result: list[dict]) -> int:
    return int(sum(r.get("total_births", 0) or 0 for r in result))


def nearest_frame(raw_frames: list[dict], fraction: float) -> dict:
    """Frame nearest a fraction of query-relevant rows, not fragments."""
    period_total_rows = result_total_rows(raw_frames[-1]["result"])
    return min(
        raw_frames,
        key=lambda frame: abs(
            result_total_rows(frame["result"]) / period_total_rows - fraction
        ),
    )


# ---- Q1: line-chart snapshots + convergence ----

def q1_series_from_result(result: list[dict]) -> dict:
    return {r["month"]: (r["low_weight_births"] / r["total_births"] if r["total_births"] > 0 else None) for r in result}


def make_q1_figures(run_id: str):
    raw_frames = load_frames(RAW / "Q1" / f"{run_id}.jsonl")
    final_series = q1_series_from_result(raw_frames[-1]["result"])
    months = sorted(final_series.keys())
    final_rates = [final_series[mo] for mo in months]
    y_max = max(r for r in final_rates if r is not None) * 1.2

    fig, axes = plt.subplots(1, 4, figsize=(11, 2.6), sharey=True)
    for ax, frac, label in zip(axes, MILESTONES, MILESTONE_LABELS):
        frame = nearest_frame(raw_frames, frac)
        series = q1_series_from_result(frame["result"])
        y = [series.get(mo) for mo in months]
        ax.plot(months, final_rates, "--", color="0.6", linewidth=1, label="final")
        ax.plot(months, y, "-o", color="C0", markersize=3, linewidth=1.5, label="partial")
        ax.set_title(label, fontsize=9)
        ax.set_xlabel("month")
        ax.set_ylim(0, y_max)
        ax.set_xticks(months)
        ax.set_xticklabels(MONTH_INITIALS, fontsize=7)
    axes[0].set_ylabel("low-birth-weight rate")
    axes[0].legend(fontsize=7, loc="upper left")
    fig.suptitle(f"Q1: progressive snapshots ({run_id})", y=1.05)
    savefig(fig, "q1_snapshots")

    frames_df = pd.read_csv(DERIVED / "Q1_frames.csv")
    run_frames = frames_df[frames_df["run_id"] == run_id].sort_values("processed_row_fraction")
    for x_col, x_label, suffix in (("processed_row_fraction", "processed-row fraction", "by_fraction"), ("elapsed_ms", "elapsed time (ms)", "by_time")):
        fig, ax1 = plt.subplots(figsize=(5.2, 3.2))
        ax1.plot(run_frames[x_col], run_frames["numerical_error"], color="C0", label="NMAE")
        ax1.set_xlabel(x_label)
        ax1.set_ylabel("NMAE")
        ax1.set_ylim(bottom=0)
        ax2 = ax1.twinx()
        ax2.plot(run_frames[x_col], run_frames["rho_shape"], color="C1", label="$\\rho$ (shape)")
        ax2.plot(run_frames[x_col], run_frames["trend_agreement"], color="C2", linestyle=":", label="trend agreement")
        ax2.set_ylabel("Pearson correlation / trend agreement")
        ax2.set_ylim(0, 1.05)
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=7, loc="lower right")
        fig.suptitle(f"Q1: convergence vs. {x_label} ({run_id})")
        savefig(fig, f"q1_convergence_{suffix}")


# ---- Q2: histogram snapshots + convergence ----

def q2_series_from_result(result: list[dict], dense_domain: list[int]) -> list[int]:
    by_age = {r["maternal_age"]: r["low_weight_births"] for r in result if dense_domain[0] <= r["maternal_age"] <= dense_domain[-1]}
    return [by_age.get(a, 0) for a in dense_domain]


def make_q2_figures(run_id: str):
    min_age, max_age = CONFIG["maternal_age_min"], CONFIG["maternal_age_max"]
    dense_domain = list(range(min_age, max_age + 1))
    raw_frames = load_frames(RAW / "Q2" / f"{run_id}.jsonl")
    final_counts = q2_series_from_result(raw_frames[-1]["result"], dense_domain)
    y_max = max(final_counts) * 1.2

    fig, axes = plt.subplots(1, 4, figsize=(11, 2.6), sharey=True)
    for ax, frac, label in zip(axes, MILESTONES, MILESTONE_LABELS):
        frame = nearest_frame(raw_frames, frac)
        counts = q2_series_from_result(frame["result"], dense_domain)
        ax.bar(dense_domain, counts, width=1.0, color="C0")
        ax.plot(dense_domain, final_counts, "--", color="0.4", linewidth=1)
        ax.set_title(label, fontsize=9)
        ax.set_xlabel("maternal age")
        ax.set_ylim(0, y_max)
    axes[0].set_ylabel("low-birth-weight births")
    fig.suptitle(f"Q2: progressive snapshots, counts ({run_id})", y=1.05)
    savefig(fig, "q2_snapshots_counts")

    fig, axes = plt.subplots(1, 4, figsize=(11, 2.6), sharey=True)
    final_total = sum(final_counts) or 1
    final_prop = [c / final_total for c in final_counts]
    y_max_p = max(final_prop) * 1.2
    for ax, frac, label in zip(axes, MILESTONES, MILESTONE_LABELS):
        frame = nearest_frame(raw_frames, frac)
        counts = q2_series_from_result(frame["result"], dense_domain)
        total = sum(counts) or 1
        prop = [c / total for c in counts]
        ax.bar(dense_domain, prop, width=1.0, color="C0")
        ax.plot(dense_domain, final_prop, "--", color="0.4", linewidth=1)
        ax.set_title(label, fontsize=9)
        ax.set_xlabel("maternal age")
        ax.set_ylim(0, y_max_p)
    axes[0].set_ylabel("proportion")
    fig.suptitle(f"Q2: progressive snapshots, normalized ({run_id})", y=1.05)
    savefig(fig, "q2_snapshots_proportions")

    # Publication view: absolute accumulation and normalized shape at the
    # same processed-row milestones. The two rows make explicit why raw
    # counts may remain incomplete even when the distributional shape is
    # already close to the final result.
    fig, axes = plt.subplots(2, 4, figsize=(11, 5.0), sharex="col", sharey="row")
    for col, (frac, label) in enumerate(zip(MILESTONES, MILESTONE_LABELS)):
        frame = nearest_frame(raw_frames, frac)
        counts = q2_series_from_result(frame["result"], dense_domain)
        total = sum(counts) or 1
        prop = [c / total for c in counts]

        ax_count = axes[0, col]
        ax_count.bar(dense_domain, counts, width=1.0, color="C0")
        ax_count.plot(dense_domain, final_counts, "--", color="0.4", linewidth=1)
        ax_count.set_title(label, fontsize=9)
        ax_count.set_ylim(0, y_max)

        ax_prop = axes[1, col]
        ax_prop.bar(dense_domain, prop, width=1.0, color="C0")
        ax_prop.plot(dense_domain, final_prop, "--", color="0.4", linewidth=1)
        ax_prop.set_ylim(0, y_max_p)
        ax_prop.set_xlabel("maternal age")

    axes[0, 0].set_ylabel("low-birth-weight births")
    axes[1, 0].set_ylabel("proportion")
    fig.suptitle(f"Q2: progressive snapshots, counts and proportions ({run_id})", y=1.01)
    fig.tight_layout()
    savefig(fig, "q2_snapshots_counts_and_proportions")

    frames_df = pd.read_csv(DERIVED / "Q2_frames.csv")
    run_frames = frames_df[frames_df["run_id"] == run_id].sort_values("processed_row_fraction")
    for x_col, x_label, suffix in (("processed_row_fraction", "processed-row fraction", "by_fraction"), ("elapsed_ms", "elapsed time (ms)", "by_time")):
        fig, ax1 = plt.subplots(figsize=(5.2, 3.2))
        ax1.plot(run_frames[x_col], run_frames["numerical_error"], color="C0", label="NMAE (proportions)")
        ax1.set_xlabel(x_label)
        ax1.set_ylabel("NMAE")
        ax1.set_ylim(bottom=0)
        ax2 = ax1.twinx()
        ax2.plot(run_frames[x_col], run_frames["js_similarity"], color="C1", label="JS similarity")
        ax2.set_ylabel("JS similarity")
        ax2.set_ylim(0, 1.05)
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=7, loc="lower right")
        fig.suptitle(f"Q2: convergence vs. {x_label} ({run_id})")
        savefig(fig, f"q2_convergence_{suffix}")

    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    ax.plot(run_frames["processed_row_fraction"], run_frames["wasserstein_distance"], color="C3")
    ax.set_xlabel("processed-row fraction")
    ax.set_ylabel("Wasserstein distance (years)")
    fig.suptitle(f"Q2: Wasserstein distance ({run_id})")
    savefig(fig, "q2_wasserstein")

    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    ax.plot(run_frames["processed_row_fraction"], run_frames["compositional_nmae"], color="C0", label="compositional NMAE")
    ax.plot(run_frames["processed_row_fraction"], run_frames["progress_adjusted_nmae"], color="C2", linestyle=":", label="progress-adjusted count NMAE")
    ax.plot(run_frames["processed_row_fraction"], run_frames["raw_count_completeness_error"], color="0.5", linestyle="--", label="raw-count completeness error")
    ax.set_xlabel("processed-row fraction")
    ax.set_ylabel("normalized absolute error")
    ax.set_ylim(-0.02, 1.02)
    ax.legend(fontsize=7)
    fig.suptitle(f"Q2 - numerical-error definitions ({run_id})")
    savefig(fig, "q2_nmae_variants")


# ---- Q3: ranked-bar snapshots + convergence ----

def q3_ranking_from_result(result: list[dict]) -> list[tuple]:
    ranked = [(r["state"], r["cesarean_births"] / r["total_births"]) for r in result if r["total_births"] > 0]
    return sorted(ranked, key=lambda kv: kv[1], reverse=True)


def make_q3_figures(run_id: str):
    raw_frames = load_frames(RAW / "Q3" / f"{run_id}.jsonl")
    final_ranking = q3_ranking_from_result(raw_frames[-1]["result"])
    x_max = max(v for _, v in final_ranking) * 1.15
    milestones = [0.50, 0.75, 0.90, 1.00]
    milestone_labels = ["50% of rows", "75% of rows", "90% of rows", "Final"]

    fig, axes = plt.subplots(1, 4, figsize=(12, 4.2))
    for ax, frac, label in zip(axes, milestones, milestone_labels):
        frame = nearest_frame(raw_frames, frac)
        ranking = q3_ranking_from_result(frame["result"])
        states = [STATE_ABBREVIATIONS.get(int(s), str(s)) for s, _ in ranking]
        values = [v for _, v in ranking]
        ax.barh(range(len(states)), values, color="C0")
        ax.set_yticks(range(len(states)))
        ax.set_yticklabels(states, fontsize=6)
        ax.invert_yaxis()
        ax.set_xlim(0, x_max)
        ax.set_title(label, fontsize=9)
        ax.set_xlabel("cesarean rate")
    fig.suptitle(f"Q3: progressive ranking snapshots ({run_id})", y=1.02)
    fig.tight_layout()
    savefig(fig, "q3_snapshots")

    frames_df = pd.read_csv(DERIVED / "Q3_frames.csv")
    run_frames = frames_df[frames_df["run_id"] == run_id].sort_values("processed_row_fraction")
    for x_col, x_label, suffix in (("processed_row_fraction", "processed-row fraction", "by_fraction"), ("elapsed_ms", "elapsed time (ms)", "by_time")):
        fig, ax1 = plt.subplots(figsize=(5.2, 3.2))
        ax1.plot(run_frames[x_col], run_frames["numerical_error"], color="C0", linestyle="--", marker="o", markersize=2, label="NMAE (covered states)")
        ax1.set_xlabel(x_label)
        ax1.set_ylabel("NMAE")
        nmae_max = float(run_frames["numerical_error"].max())
        ax1.set_ylim(0, max(0.05, nmae_max * 1.1))

        # spearman_rho/top_k_overlap are computed over the states already
        # covered. Their values can become nearly perfect while annual
        # fragments are still refining state rates and other states remain
        # absent. domain_coverage is therefore overlaid explicitly so the
        # figure does not imply that the national ranking has converged.
        ax2 = ax1.twinx()
        ax2.plot(run_frames[x_col], run_frames["spearman_rho"], color="C1", label="Spearman $\\rho_s$ (covered states)")
        ax2.plot(run_frames[x_col], run_frames["top_k_overlap"], color="C2", linestyle=":", label=f"Top-{CONFIG['top_k']} overlap")
        ax2.plot(run_frames[x_col], run_frames["domain_coverage"], color="0.4", linestyle="-.", label="domain coverage")
        ax2.set_ylabel("ranking fidelity / domain coverage")
        ax2.set_ylim(0, 1.05)
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=7, loc="lower right")
        fig.suptitle(f"Q3: convergence vs. {x_label} ({run_id})")
        savefig(fig, f"q3_convergence_{suffix}")


# ---- comparative summary figure (3 tasks x 2 columns) ----

def make_convergence_summary(rep_runs: dict):
    fig, axes = plt.subplots(3, 2, figsize=(8.5, 9.5))
    for row, query_id in enumerate(("Q1", "Q2", "Q3")):
        run_id = rep_runs.get(query_id)
        if run_id is None:
            continue
        frames_df = pd.read_csv(DERIVED / f"{query_id}_frames.csv")
        run_frames = frames_df[frames_df["run_id"] == run_id].sort_values("processed_row_fraction")

        ax_num, ax_vis = axes[row]
        ax_num.plot(run_frames["processed_row_fraction"], run_frames["numerical_error"], color="C0")
        ax_num.set_ylabel(f"{TASK_TITLES[query_id]}\nNMAE")
        ax_num.set_xlim(0, 1)
        ax_num.set_ylim(bottom=0)

        fidelity_col = FIDELITY_COLUMN[query_id]
        ax_vis.plot(run_frames["processed_row_fraction"], run_frames[fidelity_col], color="C1", label=FIDELITY_LABELS[query_id])
        ax_vis.set_ylabel(FIDELITY_LABELS[query_id])
        ax_vis.set_ylim(0, 1.05)
        ax_vis.set_xlim(0, 1)
        # Q3's fidelity is computed only over already-covered states. Without
        # domain_coverage overlaid, this row could misleadingly suggest global
        # convergence while part of the national state domain remains absent.
        if query_id == "Q3":
            ax_vis.plot(run_frames["processed_row_fraction"], run_frames["domain_coverage"], color="0.5", linestyle="--", label="domain coverage")
            ax_vis.legend(fontsize=6, loc="lower right")

        if row == 0:
            ax_num.set_title("Numerical convergence")
            ax_vis.set_title("Visual convergence")
        if row == 2:
            ax_num.set_xlabel("processed-row fraction")
            ax_vis.set_xlabel("processed-row fraction")

    fig.suptitle("Numerical vs. visual convergence across tasks", y=1.0)
    fig.tight_layout()
    savefig(fig, "convergence_summary")


# ---- Methods-section figure: each task's final, converged view ----

def make_task_overview_figure(rep_runs: dict):
    """A Methods-section figure (not a Results one): what each task's own
    visualization looks like once fully converged, with no reference to
    progressive behavior — replaces the paper's placeholder for
    fig:task-overview, which only ever asked for "three planned task
    examples", not a convergence comparison."""
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.2))

    q1_frames = load_frames(RAW / "Q1" / f"{rep_runs['Q1']}.jsonl")
    q1_final = q1_series_from_result(q1_frames[-1]["result"])
    months = sorted(q1_final.keys())
    axes[0].plot(months, [q1_final[m] for m in months], "-o", color="C0", markersize=3)
    axes[0].set_title("Q1: temporal (final)")
    axes[0].set_xlabel("month")
    axes[0].set_ylabel("low-birth-weight rate")
    axes[0].set_xticks(months)
    axes[0].set_xticklabels(MONTH_INITIALS, fontsize=7)
    axes[0].set_ylim(0, max(q1_final.values()) * 1.1)

    min_age, max_age = CONFIG["maternal_age_min"], CONFIG["maternal_age_max"]
    dense_domain = list(range(min_age, max_age + 1))
    q2_frames = load_frames(RAW / "Q2" / f"{rep_runs['Q2']}.jsonl")
    q2_final = q2_series_from_result(q2_frames[-1]["result"], dense_domain)
    axes[1].bar(dense_domain, q2_final, width=1.0, color="C0")
    axes[1].set_title("Q2: distribution (final)")
    axes[1].set_xlabel("maternal age")
    axes[1].set_ylabel("low-birth-weight births")

    q3_frames = load_frames(RAW / "Q3" / f"{rep_runs['Q3']}.jsonl")
    q3_final = q3_ranking_from_result(q3_frames[-1]["result"])
    states = [STATE_ABBREVIATIONS.get(int(s), str(s)) for s, _ in q3_final]
    values = [v for _, v in q3_final]
    axes[2].barh(range(len(states)), values, color="C0")
    axes[2].set_yticks(range(len(states)))
    axes[2].set_yticklabels(states, fontsize=6)
    axes[2].invert_yaxis()
    axes[2].set_title("Q3: ranking (final)")
    axes[2].set_xlabel("cesarean rate")

    fig.tight_layout()
    savefig(fig, "task_overview")


def main():
    rep_runs = {}
    for query_id, make_fn in (("Q1", make_q1_figures), ("Q2", make_q2_figures), ("Q3", make_q3_figures)):
        run_id = representative_run_id(query_id)
        if run_id is None:
            print(f"  (skipping {query_id}: no derived data)")
            continue
        rep_runs[query_id] = run_id
        print(f"Making {query_id} figures from representative run {run_id} ...")
        make_fn(run_id)

    if len(rep_runs) == 3:
        print("Making task-overview figure (Methods section) ...")
        make_task_overview_figure(rep_runs)
        print("Making comparative summary figure ...")
        make_convergence_summary(rep_runs)

    print("\nFigures written to", FIGURES)


if __name__ == "__main__":
    main()
