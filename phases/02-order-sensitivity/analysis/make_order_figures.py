"""Create figures for physical-order sensitivity over processed-row fraction."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MPL_CACHE = ROOT / "output" / ".matplotlib"
MPL_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE))

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["pdf.fonttype"] = 42
matplotlib.rcParams["ps.fonttype"] = 42
matplotlib.rcParams["font.size"] = 9
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

DERIVED = ROOT / "output" / "derived"
TABLES = ROOT / "output" / "tables"
FIGURES = ROOT / "output" / "figures"

THREADS = (1, 2, 4)
TASK_TITLES = {"Q1": "Q1 temporal", "Q2": "Q2 distribution"}
FIDELITY_COLUMNS = {"Q1": "rho_shape", "Q2": "js_similarity"}
FIDELITY_LABELS = {
    "Q1": "Pearson shape correlation",
    "Q2": "Jensen–Shannon similarity",
}
Q3_EVENTS = (
    ("tvf_rank", "TVF-rank"),
    ("tvf_top5_80", "TVF-top5-80"),
    ("tvf_top5_100", "TVF-top5-100"),
    ("tcov90", "TCov-90"),
)


def savefig(fig, name: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(FIGURES / f"{name}.png", bbox_inches="tight", dpi=220)
    plt.close(fig)


def measured(df: pd.DataFrame) -> pd.DataFrame:
    if "is_warmup" not in df:
        return df
    values = df["is_warmup"]
    if values.dtype == bool:
        return df[~values]
    return df[~values.astype(str).str.lower().isin({"true", "1", "yes"})]


def load_frames() -> pd.DataFrame:
    parts = []
    for query_id in ("Q1", "Q2", "Q3"):
        path = DERIVED / f"{query_id}_frames.csv"
        if path.exists():
            parts.append(measured(pd.read_csv(path)))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _plot_order_trajectories(ax, subset: pd.DataFrame, column: str, *, mask=None) -> None:
    for kind, color, alpha, linewidth in (
        ("permuted", "C0", 0.32, 0.8),
        ("canonical", "black", 1.0, 1.8),
    ):
        for _, run in subset[subset["dataset_kind"] == kind].groupby("run_id"):
            run = run.sort_values("processed_row_fraction")
            if mask is not None:
                run = run[mask(run)]
            ax.plot(
                run["processed_row_fraction"],
                run[column],
                color=color,
                alpha=alpha,
                linewidth=linewidth,
            )


def make_q1_q2_event_figure() -> None:
    path = TABLES / "run_results.csv"
    if not path.exists():
        return
    runs = pd.read_csv(path)
    events = (("tnc", "Numerical convergence"), ("tvf", "Visual fidelity"), ("tsv", "View stability"))
    fig, axes = plt.subplots(2, 3, figsize=(10.5, 5.7), sharex=True, sharey=True)
    rng = np.random.default_rng(20260926)

    for row_index, query_id in enumerate(("Q1", "Q2")):
        query_runs = runs[runs["query_id"] == query_id]
        for col_index, (event, title) in enumerate(events):
            ax = axes[row_index, col_index]
            for x, threads in enumerate(THREADS, start=1):
                subset = query_runs[query_runs["threads"] == threads]
                shuffled = pd.to_numeric(
                    subset[subset["dataset_kind"] == "permuted"][f"{event}_processed_row_fraction"],
                    errors="coerce",
                ).dropna()
                if not shuffled.empty:
                    jitter = rng.uniform(-0.09, 0.09, len(shuffled))
                    ax.scatter(np.full(len(shuffled), x) + jitter, shuffled, s=19, alpha=0.68, color="C0")
                    ax.boxplot(
                        [shuffled], positions=[x], widths=0.34, showfliers=False,
                        medianprops={"color": "C0", "linewidth": 1.5},
                    )
                original = pd.to_numeric(
                    subset[subset["dataset_kind"] == "canonical"][f"{event}_processed_row_fraction"],
                    errors="coerce",
                ).dropna()
                if not original.empty:
                    ax.scatter([x], [original.iloc[0]], marker="D", s=35, color="black", zorder=5)
            ax.set_ylim(-0.02, 1.02)
            ax.grid(axis="y", alpha=0.2)
            if row_index == 0:
                ax.set_title(title)
            if col_index == 0:
                ax.set_ylabel(f"{TASK_TITLES[query_id]}\nprocessed-row fraction")
            if row_index == 1:
                ax.set_xticks(range(1, len(THREADS) + 1), [str(value) for value in THREADS])
                ax.set_xlabel("worker threads")
    fig.suptitle("Q1–Q2 convergence events across physical orders\npoints: permutations; diamond: identity order")
    fig.tight_layout()
    savefig(fig, "q1_q2_order_sensitivity_events")


def make_q1_q2_fidelity_figure(frames: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(10.5, 5.7), sharex=True, sharey=True)
    for row_index, query_id in enumerate(("Q1", "Q2")):
        task_frames = frames[frames["query_id"] == query_id]
        for col_index, threads in enumerate(THREADS):
            ax = axes[row_index, col_index]
            _plot_order_trajectories(
                ax,
                task_frames[task_frames["threads"] == threads],
                FIDELITY_COLUMNS[query_id],
            )
            ax.axhline(0.90, color="0.50", linestyle=":", linewidth=0.9)
            ax.set_xlim(0, 1)
            ax.set_ylim(-0.05, 1.02)
            ax.grid(alpha=0.18)
            if row_index == 0:
                ax.set_title("1 thread" if threads == 1 else f"{threads} threads")
            if col_index == 0:
                ax.set_ylabel(f"{TASK_TITLES[query_id]}\n{FIDELITY_LABELS[query_id]}")
            if row_index == 1:
                ax.set_xlabel("processed-row fraction")
    fig.suptitle("Q1–Q2 task-specific fidelity\nblue: permutations; black: identity order")
    fig.tight_layout()
    savefig(fig, "q1_q2_fidelity_trajectories")


def make_q3_quality_dimensions(frames: pd.DataFrame) -> None:
    q3 = frames[frames["query_id"] == "Q3"]
    rows = (
        ("spearman_rho", "Rank fidelity among visible states", 0.90, (0.80, 1.01)),
        ("top_k_overlap", "Final top-5 recovered", 0.80, (-0.02, 1.02)),
        ("domain_coverage", "State-domain coverage", 0.90, (-0.02, 1.02)),
    )
    fig, axes = plt.subplots(3, 3, figsize=(10.5, 8.0), sharex=True)
    for row_index, (column, label, threshold, ylim) in enumerate(rows):
        for col_index, threads in enumerate(THREADS):
            ax = axes[row_index, col_index]
            subset = q3[q3["threads"] == threads]
            support_mask = None
            if column in {"spearman_rho", "top_k_overlap"}:
                support_mask = lambda run: run["eligible_for_fidelity"].astype(str).str.lower().isin({"true", "1"})
            _plot_order_trajectories(ax, subset, column, mask=support_mask)
            ax.axhline(threshold, color="0.50", linestyle=":", linewidth=0.9)
            ax.set_xlim(0, 1)
            ax.set_ylim(*ylim)
            ax.grid(alpha=0.18)
            if row_index == 0:
                ax.set_title("1 thread" if threads == 1 else f"{threads} threads")
            if col_index == 0:
                suffix = " (zoom: 0.80–1.00)" if row_index == 0 else ""
                ax.set_ylabel(label + suffix)
            if row_index == 2:
                ax.set_xlabel("processed-row fraction")
    handles = [
        Line2D([0], [0], color="C0", linewidth=1.5, label="permutations"),
        Line2D([0], [0], color="black", linewidth=1.8, label="identity order"),
        Line2D([0], [0], color="0.5", linestyle=":", label="event threshold"),
    ]
    fig.legend(handles=handles, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 0.995))
    fig.suptitle("Q3 separates local rank fidelity, top-5 recovery, and coverage", y=1.025)
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    savefig(fig, "q3_quality_dimensions")


def make_q3_event_comparison() -> None:
    path = TABLES / "run_results.csv"
    if not path.exists():
        return
    q3 = pd.read_csv(path)
    q3 = q3[q3["query_id"] == "Q3"]
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.4), sharey=True)
    rng = np.random.default_rng(20260926)
    positions = np.arange(1, len(Q3_EVENTS) + 1)

    for ax, threads in zip(axes, THREADS):
        subset = q3[q3["threads"] == threads]
        for x, (event, _) in zip(positions, Q3_EVENTS):
            shuffled = pd.to_numeric(
                subset[subset["dataset_kind"] == "permuted"][f"{event}_processed_row_fraction"],
                errors="coerce",
            ).dropna()
            jitter = rng.uniform(-0.08, 0.08, len(shuffled))
            ax.scatter(np.full(len(shuffled), x) + jitter, shuffled, s=22, alpha=0.72, color="C0")
            if not shuffled.empty:
                ax.boxplot(
                    [shuffled], positions=[x], widths=0.34, showfliers=False,
                    medianprops={"color": "C0", "linewidth": 1.6},
                )
            original = pd.to_numeric(
                subset[subset["dataset_kind"] == "canonical"][f"{event}_processed_row_fraction"],
                errors="coerce",
            ).dropna()
            if not original.empty:
                ax.scatter([x], [original.iloc[0]], marker="D", s=38, color="black", zorder=5)
        ax.set_title("1 thread" if threads == 1 else f"{threads} threads")
        ax.set_xticks(positions, [label for _, label in Q3_EVENTS], rotation=28, ha="right")
        ax.set_ylim(-0.02, 1.02)
        ax.grid(axis="y", alpha=0.2)
    axes[0].set_ylabel("processed-row fraction at persistent event")
    fig.suptitle("Q3 multidimensional fidelity events\npoints: permutations; diamond: identity order")
    fig.tight_layout()
    savefig(fig, "q3_fidelity_events")


def main() -> None:
    frames = load_frames()
    if frames.empty:
        print("  (no derived frames; skipping order figures)")
        return
    make_q1_q2_event_figure()
    make_q1_q2_fidelity_figure(frames)
    make_q3_quality_dimensions(frames)
    make_q3_event_comparison()
    print("Wrote revised order-sensitivity figures to", FIGURES)


if __name__ == "__main__":
    main()
