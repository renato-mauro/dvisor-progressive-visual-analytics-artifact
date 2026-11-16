"""Figures built from the supplementary analyses.

progressive_snapshots.pdf  what a chart shows at four moments of one canonical
                        run: the Q1 monthly series and the Q2 counts by age
canonical_overview.pdf  ten canonical four-worker runs per task: numerical
                        error (upper row) and structural measures (lower row)
q1_q2_orders.pdf        structural similarity of Q1 and Q2 in the 90-run order
                        collection (canonical order and nine permutations)
q3_orders.pdf           one logical worker: state coverage, rank agreement
                        among visible states, presence of the final Top-5
                        states, and observed Top-5 overlap for the canonical
                        state-year order, the year-state order and the nine
                        executed permutations
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import common as c  # noqa: E402

FIG = c.OUT / "figures"
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"

plt.rcParams.update({
    "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8, "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5, "legend.fontsize": 7.5, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.linewidth": 0.6, "axes.spines.top": False,
    "axes.spines.right": False, "pdf.fonttype": 42, "font.family": "DejaVu Sans",
})


def style(ax):
    ax.grid(True, color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0", "25%", "50%", "75%", "100%"])


def threshold(ax, y, label, x=0.995, ha="right"):
    ax.axhline(y, color=MUTED, linewidth=0.7, linestyle=(0, (1, 2)))
    ax.text(x, y, label, color=MUTED, fontsize=6.5, ha=ha, va="bottom",
            transform=ax.get_yaxis_transform())


SNAPSHOT_TARGETS = (0.10, 0.25, 0.50, 1.00)
MONTHS = "JFMAMJJASOND"


def representative_run(query: str) -> list[dict]:
    """The canonical run whose final elapsed time is closest to the median."""
    import statistics
    runs = c.phase1_runs(query)
    finals = {rid: frames[-1]["elapsed_ms"] for rid, frames in runs.items()}
    median = statistics.median(finals.values())
    return runs[min(finals, key=lambda rid: (abs(finals[rid] - median), rid))]


def progressive_snapshots() -> None:
    fig, axes = plt.subplots(2, 4, figsize=(6.9, 3.5))

    def snapshot_frames(frames):
        rows = c.frame_rows(frames[0]["query_id"], frames)
        picked = [c.first_at_or_above(rows, t) for t in SNAPSHOT_TARGETS]
        return [(frames[r["frame_index"] - 1], r) for r in picked]

    def title(row):
        share = 100 * row["processed_row_fraction"]
        share_txt = "100%" if share >= 99.95 else f"{share:.1f}%"
        return f"{share_txt} of rows, {row['elapsed_ms'] / 1000:.1f} s"

    # Q1: monthly low-birth-weight rate
    frames = representative_run("Q1")
    rate = lambda res: [100 * r["low_weight_births"] / r["total_births"]  # noqa: E731
                        for r in sorted(res, key=lambda r: r["month"])]
    final = rate(frames[-1]["result"])
    shots = snapshot_frames(frames)
    values = [v for frame, _ in shots for v in rate(frame["result"])] + final
    lo, hi = min(values) - 0.15, max(values) + 0.15
    for ax, (frame, row) in zip(axes[0], shots):
        ax.grid(True, axis="y", color=GRID, linewidth=0.5)
        ax.set_axisbelow(True)
        ax.plot(range(12), final, color=MUTED, linewidth=1.0, linestyle=(0, (3, 2)), label="final result")
        ax.plot(range(12), rate(frame["result"]), color=BLUE, linewidth=1.4, marker="o", markersize=2.6,
                label="frame")
        ax.set_ylim(lo, hi)
        ax.set_xticks(range(12))
        ax.set_xticklabels(list(MONTHS), fontsize=6.5)
        ax.set_title(title(row), loc="left", color=INK, fontsize=7.5)
    axes[0, 0].set_ylabel("Q1: rate (%)")

    # Q2: low-birth-weight births by maternal age
    frames = representative_run("Q2")
    lo_age, hi_age = c.CONFIG["maternal_age_min"], c.CONFIG["maternal_age_max"]
    ages = list(range(lo_age, hi_age + 1))

    def counts(res):
        by_age = {r["maternal_age"]: r["low_weight_births"] for r in res}
        return [by_age.get(a, 0) / 1000 for a in ages]

    final = counts(frames[-1]["result"])
    for ax, (frame, row) in zip(axes[1], snapshot_frames(frames)):
        ax.grid(True, axis="y", color=GRID, linewidth=0.5)
        ax.set_axisbelow(True)
        ax.bar(ages, counts(frame["result"]), width=0.9, color=BLUE, linewidth=0)
        ax.step([a - 0.5 for a in ages] + [ages[-1] + 0.5], final + [final[-1]], where="post", color=MUTED,
                linewidth=1.0, linestyle=(0, (3, 2)))
        ax.set_ylim(0, max(final) * 1.08)
        ax.set_xlim(lo_age - 1, hi_age + 1)
        ax.set_xticks([10, 20, 30, 40, 50])
        ax.set_xlabel("maternal age")
        ax.set_title(title(row), loc="left", color=INK, fontsize=7.5)
    axes[1, 0].set_ylabel("Q2: births (thousands)")

    for row_axes in axes:
        for ax in row_axes[1:]:
            ax.tick_params(labelleft=False)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles[::-1], labels[::-1], loc="upper right", ncol=2, frameon=False, handlelength=2.4,
               labelcolor=INK, bbox_to_anchor=(0.995, 1.0), borderaxespad=0.1)
    fig.tight_layout(w_pad=0.6, h_pad=0.9, rect=(0, 0, 1, 0.94))
    fig.savefig(FIG / "progressive_snapshots.pdf")
    fig.savefig(FIG / "progressive_snapshots.png", dpi=200)
    plt.close(fig)


def canonical_overview() -> None:
    R = {q: [c.frame_rows(q, fr) for fr in c.phase1_runs(q).values()] for q in c.QUERIES}
    fig, axes = plt.subplots(2, 3, figsize=(6.9, 3.9), sharex=True)
    titles = {"Q1": "Q1 monthly rate", "Q2": "Q2 age distribution", "Q3": "Q3 state ranking"}
    x = lambda rows: [r["processed_row_fraction"] for r in rows]  # noqa: E731
    for j, q in enumerate(c.QUERIES):
        top, bot = axes[0, j], axes[1, j]
        style(top)
        style(bot)
        top.set_title(titles[q], loc="left", color=INK)
        for rows in R[q]:
            top.plot(x(rows), [r["numerical_error"] for r in rows], color=BLUE, linewidth=0.8, alpha=0.45)
        threshold(top, 0.05, "0.05")
        nominal_top = {"Q1": 0.15, "Q2": 0.30, "Q3": 0.15}[q]
        highest_nmae = max(
            (frame["numerical_error"] for rows in R[q] for frame in rows
             if frame["numerical_error"] is not None),
            default=0.0,
        )
        top.set_ylim(0, max(nominal_top, 1.10 * highest_nmae))
        if q == "Q1":
            for rows in R[q]:
                bot.plot(x(rows), [r["rho_shape"] for r in rows], color=BLUE, linewidth=0.8, alpha=0.45)
            bot.set_ylim(-0.25, 1.03)
            bot.text(0.42, 0.62, "Pearson with\nfinal series", color=INK, fontsize=7)
        elif q == "Q2":
            for rows in R[q]:
                bot.plot(x(rows), [r["js_similarity"] for r in rows], color=BLUE, linewidth=0.8, alpha=0.45)
            bot.set_ylim(-0.25, 1.03)
            bot.text(0.42, 0.62, "Jensen-Shannon\nsimilarity", color=INK, fontsize=7)
        else:
            for i, rows in enumerate(R[q]):
                bot.plot(x(rows), [r["spearman_rho"] for r in rows], color=BLUE, linewidth=0.8, alpha=0.45,
                         label="Spearman (visible)" if i == 0 else None)
                bot.plot(x(rows), [r["domain_coverage"] for r in rows], color=ORANGE, linewidth=0.8,
                         alpha=0.45, linestyle=(0, (4, 1.5)), label="coverage" if i == 0 else None)
                bot.plot(x(rows), [r["top_k_overlap"] for r in rows], color=AQUA, linewidth=0.8, alpha=0.45,
                         linestyle=(0, (1, 1)), label="Top-5 overlap" if i == 0 else None)
            bot.set_ylim(-0.25, 1.03)
            leg = bot.legend(loc="lower right", frameon=False, handlelength=1.8, borderaxespad=0.1,
                             labelcolor=INK, fontsize=6.8, labelspacing=0.25)
            for h in leg.legend_handles:
                h.set_alpha(1)
                h.set_linewidth(1.4)
        if q == "Q3":
            threshold(bot, 0.90, "0.90", x=0.30, ha="left")
        else:
            threshold(bot, 0.90, "0.90")
        bot.set_xlabel("query-relevant rows processed")
    axes[0, 0].set_ylabel("NMAE")
    axes[1, 0].set_ylabel("structural measure")
    fig.tight_layout(w_pad=1.2, h_pad=0.9)
    fig.savefig(FIG / "canonical_overview.pdf")
    fig.savefig(FIG / "canonical_overview.png", dpi=200)
    plt.close(fig)


def q3_orders() -> None:
    blocks = c.Blocks()
    orders = c.permutation_orders()
    series = {ds: c.frame_rows("Q3", c.simulate(blocks, "Q3", orders[ds])) for ds in c.DATASETS}
    year_state = c.frame_rows("Q3", c.simulate(blocks, "Q3", blocks.year_uf_order()))
    panels = (("domain_coverage", "States present (coverage)", (-0.03, 1.03)),
              ("spearman_rho", "Spearman among visible states", (0.80, 1.005)),
              ("top5_present", "Final Top-5 states present", (-0.03, 1.03)),
              ("top_k_overlap", "Top-5 overlap observed", (-0.03, 1.03)))
    fig, axes = plt.subplots(2, 2, figsize=(6.9, 4.3), sharex=True)
    x = lambda rows: [r["processed_row_fraction"] for r in rows]  # noqa: E731
    y = lambda rows, col: [r[col] if r[col] is not None else float("nan") for r in rows]  # noqa: E731
    for ax, (col, title, ylim) in zip(axes.flat, panels):
        style(ax)
        ax.set_title(title, loc="left", color=INK)
        for i, ds in enumerate(c.DATASETS[1:]):
            ax.step(x(series[ds]), y(series[ds], col), where="post", color=BLUE, linewidth=0.7, alpha=0.5,
                    label="nine permutations" if i == 0 else None)
        ax.step(x(series["original"]), y(series["original"], col), where="post", color=INK, linewidth=1.5,
                label="state-year (canonical)")
        ax.step(x(year_state), y(year_state, col), where="post", color=ORANGE, linewidth=1.5,
                linestyle=(0, (4, 1.5)), label="year-state")
        ax.set_ylim(*ylim)
    for ax in axes[1]:
        ax.set_xlabel("query-relevant rows processed")
    axes[0, 0].set_ylabel("fraction of 27 states")
    axes[0, 1].set_ylabel("correlation (axis from 0.80)")
    axes[1, 0].set_ylabel("fraction of 5 states")
    axes[1, 1].set_ylabel("fraction of 5 states")
    threshold(axes[0, 0], 0.90, "0.90", x=0.40, ha="left")
    threshold(axes[0, 1], 0.90, "0.90")
    threshold(axes[1, 1], 0.80, "0.80", x=0.86, ha="left")
    leg = axes[0, 0].legend(loc="lower right", frameon=False, handlelength=2.2, borderaxespad=0.3,
                            labelcolor=INK)
    for h in leg.legend_handles:
        h.set_alpha(1)
    fig.tight_layout(w_pad=1.4, h_pad=0.9)
    fig.savefig(FIG / "q3_orders.pdf")
    fig.savefig(FIG / "q3_orders.png", dpi=200)
    plt.close(fig)


def q1_q2_orders() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(6.9, 2.5))
    spec = (("Q1", "rho_shape", "Q1: Pearson with final series", (-0.4, 1.03)),
            ("Q2", "js_similarity", "Q2: Jensen-Shannon similarity", (0.80, 1.005)))
    for ax, (q, col, title, ylim) in zip(axes, spec):
        style(ax)
        ax.set_title(title, loc="left", color=INK)
        runs = {key: c.frame_rows(q, fr) for key, fr in c.phase2_runs(q).items()}
        first = True
        for (ds, t), rows in runs.items():
            if ds == "original":
                continue
            ax.plot([r["processed_row_fraction"] for r in rows],
                    [r[col] if r[col] is not None else float("nan") for r in rows],
                    color=BLUE, linewidth=0.6, alpha=0.4,
                    label="nine permutations, 1/2/4 workers" if first else None)
            first = False
        first = True
        for t in c.THREADS:
            rows = runs[("original", t)]
            ax.plot([r["processed_row_fraction"] for r in rows],
                    [r[col] if r[col] is not None else float("nan") for r in rows],
                    color=INK, linewidth=1.3, label="canonical, 1/2/4 workers" if first else None)
            first = False
        ax.set_ylim(*ylim)
        ax.set_xlabel("query-relevant rows processed")
        threshold(ax, 0.90, "0.90")
    axes[0].set_ylabel("correlation")
    axes[1].set_ylabel("similarity (axis from 0.80)")
    leg = axes[0].legend(loc="lower right", frameon=False, handlelength=2.2, borderaxespad=0.3, labelcolor=INK)
    for h in leg.legend_handles:
        h.set_alpha(1)
    fig.tight_layout(w_pad=1.4)
    fig.savefig(FIG / "q1_q2_orders.pdf")
    fig.savefig(FIG / "q1_q2_orders.png", dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    FIG.mkdir(parents=True, exist_ok=True)
    progressive_snapshots()
    canonical_overview()
    q1_q2_orders()
    q3_orders()
    print("wrote", FIG)
