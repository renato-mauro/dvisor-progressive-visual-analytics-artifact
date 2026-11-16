"""Writes the LaTeX table bodies used by the manuscript and its supplement
from the CSV/JSON outputs, so that no number is transcribed by hand.

Usage: python make_tex_tables.py /path/to/paper/tables
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import common as c

OUT = c.OUT


def read(name: str) -> list[dict]:
    with open(OUT / name, newline="") as f:
        return list(csv.DictReader(f))


def num(v):
    return None if v in (None, "", "None") else float(v)


def pct(v, digits=1) -> str:
    v = num(v)
    return "--" if v is None else f"{100 * v:.{digits}f}"


def rng(lo, hi, digits=1) -> str:
    return f"{pct(lo, digits)}--{pct(hi, digits)}"


def sec(ms) -> str:
    v = num(ms)
    return "--" if v is None else f"{v / 1000:.1f}"


def write(dest: Path, name: str, lines: list[str]) -> None:
    (dest / name).write_text("\n".join(lines) + "\n")


EVENT_TEX = {"TNC": "TNC", "TVF": "TVF", "TSV": "TSV", "TNC-visible": "TNC-visible", "TVF-rank": "TVF-rank",
             "Top5-80": "Top5-80", "Top5-100": "Top5-100", "TCov-90": "TCov-90"}
ORDER_OF_EVENTS = {
    "Q1": ["TNC", "TVF", "TSV"], "Q2": ["TSV", "TVF", "TNC"],
    "Q3": ["TSV", "TNC-visible", "TVF-rank", "Top5-80", "Top5-100", "TCov-90"],
}
TASK = {"Q1": "Q1 series", "Q2": "Q2 distribution", "Q3": "Q3 ranking"}


def canonical(dest: Path, summary: dict) -> None:
    rows = {(r["query"], r["event"]): r for r in read("canonical_events.csv")}
    lines = []
    for q in c.QUERIES:
        first = summary[f"{q}_canonical_first_frame_ms"]["median"]
        final = summary[f"{q}_canonical_final_ms"]["median"]
        ff = summary[f"{q}_canonical_first_frame_row_fraction"]["median"]
        lines.append(f"{TASK[q]} & first frame & {pct(ff, 2)} & {sec(first)} & "
                     f"{100 * first / final:.0f} & & \\\\")
        for ev in ORDER_OF_EVENTS[q]:
            r = rows[(q, ev)]
            hold = num(r["hold_median"])
            hold_txt = "completion" if hold is not None and hold >= 0.9999 else pct(hold)
            lines.append(
                f" & {EVENT_TEX[ev]} & {pct(r['start_median'])} ({rng(r['start_min'], r['start_max'])}) & "
                f"{sec(r['start_ms_median'])} & {100 * num(r['start_ms_median']) / final:.0f} & "
                f"{hold_txt} & {r['runs_with_later_violation']} \\\\")
        lines.append(f" & final result & 100 & {sec(final)} & 100 & & \\\\")
        if q != "Q3":
            lines.append("\\addlinespace[2pt]")
    write(dest, "canonical_events.tex", lines)


def q2_milestones(dest: Path) -> None:
    rows = read("milestones_Q2.csv")
    canon = {r["target"]: r for r in rows if r["scope"].startswith("canonical")}
    perm = {r["target"]: r for r in rows if r["scope"].startswith("nine")}
    lines = []
    for t in ("0.01", "0.05", "0.1", "0.25", "0.5", "0.75"):
        a, b = canon[t], perm[t]
        cell = lambda r: (f"{num(r['numerical_error_median']):.3f} & {num(r['js_similarity_median']):.3f} & "  # noqa: E731
                          f"{num(r['wasserstein_distance_median']):.2f} & {num(r['max_bin_err_pp_median']):.2f}")
        lines.append(f"{100 * float(t):.0f}\\% & {cell(a)} & {cell(b)} \\\\")
    write(dest, "q2_milestones.tex", lines)


def joint(dest: Path) -> None:
    rows = read("joint_sensitivity.csv")
    lines = []
    for q in ("Q1", "Q2"):
        sel = [r for r in rows if r["query"] == q and r["scope"] == "canonical" and r["persistence"] == "3"]
        fids = sorted({r["fidelity_threshold"] for r in sel}, key=float)
        tvf = {f: next(r["tvf_median"] for r in sel if r["fidelity_threshold"] == f) for f in fids}
        lines.append(f"{TASK[q]} & TVF median & " + " & ".join(pct(tvf[f]) + "\\%" for f in fids) + " \\\\")
        for tn in sorted({r["nmae_threshold"] for r in sel}, key=float):
            line = [r for r in sel if r["nmae_threshold"] == tn]
            tnc = line[0]["tnc_median"]
            cells = " & ".join(next(r["tvf_before_tnc"] for r in line if r["fidelity_threshold"] == f)
                               for f in fids)
            lines.append(f" & NMAE $\\leq {float(tn):.3f}$, TNC median {pct(tnc)}\\% & {cells} \\\\")
        if q == "Q1":
            lines.append("\\addlinespace[2pt]")
    write(dest, "joint_sensitivity.tex", lines)
    # supplement: permuted runs and all persistence lengths
    lines = []
    for q in ("Q1", "Q2"):
        for scope, n in (("canonical", 10), ("permuted", 27)):
            for k in ("1", "3", "5"):
                for tn in ("0.025", "0.05", "0.1"):
                    sel = sorted((r for r in rows if r["query"] == q and r["scope"] == scope
                                  and r["persistence"] == k and r["nmae_threshold"] == tn),
                                 key=lambda r: float(r["fidelity_threshold"]))
                    cells = " & ".join(f"{r['tvf_before_tnc']}/{r['tnc_before_tvf']}/{r['same_frame']}" for r in sel)
                    lines.append(f"{q} & {scope} ({n}) & {k} & {float(tn):.3f} & {cells} \\\\")
            lines.append("\\addlinespace[2pt]")
    write(dest, "supp_joint_sensitivity.tex", lines)


def orders(dest: Path, summary: dict) -> None:
    disp = {(r["query"], r["event"], r["position"]): r for r in read("order_dispersion.csv")}
    sim = {(r["query"], r["event"], r["position"]): r for r in read("simulated_orders.csv")}
    lines = []
    for q in c.QUERIES:
        for i, ev in enumerate(ORDER_OF_EVENTS[q]):
            s, h = disp[(q, ev, "start")], disp[(q, ev, "hold")]
            ident = [num(s[f"identity_t{t}"]) for t in c.THREADS]
            ident_txt = pct(ident[0]) if max(ident) - min(ident) < 0.0005 else rng(min(ident), max(ident))
            viol = "/".join(s[f"perm_orders_with_later_violation_t{t}"] for t in c.THREADS)
            sm = sim[(q, ev, "start")]
            sh = sim[(q, ev, "hold")]
            lines.append(
                f"{TASK[q] if i == 0 else ''} & {EVENT_TEX[ev]} & {ident_txt} & "
                f"{pct(s['pooled_median'])} ({rng(s['pooled_min'], s['pooled_max'])}) & "
                f"{pct(h['pooled_median'])} ({rng(h['pooled_min'], h['pooled_max'])}) & {viol} & "
                f"{pct(sm['median'])} ({rng(sm['p05'], sm['p95'])}) & {pct(sh['median'])} \\\\")
        if q != "Q3":
            lines.append("\\addlinespace[2pt]")
    write(dest, "order_events.tex", lines)


def mechanism(dest: Path) -> None:
    rows = read("q3_mechanism.csv")
    label = {"UF-year (identity)": "state-year (canonical)", "year-UF": "year-state"}
    lines = []
    for r in rows:
        name = label.get(r["order"], r["order"])
        lines.append(
            f"{name} & {pct(r['tcov90'])} & {pct(r['present_80'])} & {pct(r['top5_80_start'])} & "
            f"{pct(r['top5_80_hold'])} & {pct(r['present_100'])} & {pct(r['top5_100_start'])} & "
            f"{pct(r['top5_100_hold'])} & {r['frames_overlap_below_presence']}/{r['eligible_frames']} \\\\")
        if r["order"] == "year-UF":
            lines.append("\\addlinespace[2pt]")
    write(dest, "q3_mechanism.tex", lines)


def workers(dest: Path) -> None:
    rows = read("worker_paired.csv")
    rep = {(r["query"], r["event"]): r for r in read("canonical_repetition_range.csv")}
    lines = []
    for q in c.QUERIES:
        for i, ev in enumerate(ORDER_OF_EVENTS[q]):
            sel = {r["pair"]: r for r in rows if r["query"] == q and r["event"] == ev}
            cells = " & ".join(
                f"{num(sel[p]['median_abs_diff_pp']):.1f} / {num(sel[p]['max_abs_diff_pp']):.1f}"
                for p in ("2 vs 1", "4 vs 1", "4 vs 2"))
            above = max(int(sel[p]["orders_above_1pp"]) for p in sel)
            lines.append(f"{TASK[q] if i == 0 else ''} & {EVENT_TEX[ev]} & {cells} & {above} & "
                         f"{num(rep[(q, ev)]['repetition_range_pp']):.1f} \\\\")
        if q != "Q3":
            lines.append("\\addlinespace[2pt]")
    write(dest, "workers.tex", lines)


def supplement(dest: Path, summary: dict) -> None:
    # persistence
    rows = read("persistence.csv")
    lines = []
    for q in c.QUERIES:
        for ev in ORDER_OF_EVENTS[q]:
            for scope, label in (("canonical", "canonical"), ("permuted", "permuted")):
                cells = []
                for k in ("1", "3", "5"):
                    r = next(x for x in rows if x["query"] == q and x["event"] == ev and x["scope"] == scope
                             and x["persistence"] == k)
                    cells.append(f"{pct(r['median'])} ({rng(r['min'], r['max'])}), {r['reached']}/{r['runs']}")
                lines.append(f"{q} & {EVENT_TEX[ev]} & {label} & " + " & ".join(cells) + " \\\\")
        lines.append("\\addlinespace[2pt]")
    write(dest, "supp_persistence.tex", lines)
    # per-order events at each worker count (first run / held to completion)
    rows = read("order_events.csv")
    for q in c.QUERIES:
        lines = []
        for ev in ORDER_OF_EVENTS[q]:
            for ds in c.DATASETS:
                cells = []
                for t in ("1", "2", "4"):
                    r = next(x for x in rows if x["query"] == q and x["event"] == ev and x["dataset"] == ds
                             and x["threads"] == t)
                    cells.append(f"{pct(r['start_row_fraction'])} & {pct(r['hold_row_fraction'])} & "
                                 f"{r['later_violations']}")
                name = "canonical" if ds == "original" else ds
                lines.append(f"{EVENT_TEX[ev] if ds == 'original' else ''} & {name} & " + " & ".join(cells) + " \\\\")
            lines.append("\\addlinespace[2pt]")
        write(dest, f"supp_order_events_{q}.tex", lines)
    # canonical events with confirmation frame
    rows = read("canonical_events.csv")
    lines = []
    for r in rows:
        lines.append(
            f"{r['query']} & {EVENT_TEX[r['event']]} & {r['reached']}/{r['runs']} & {pct(r['start_median'])} & "
            f"{pct(r['confirm_median'])} & {sec(r['start_ms_median'])} & {sec(r['confirm_ms_median'])} & "
            f"{pct(r['hold_median'])} & {r['runs_with_later_violation']} & "
            f"{r['runs_starting_at_first_eligible']} \\\\")
    write(dest, "supp_canonical_events.tex", lines)
    # Q1 by year
    rows = read("q1_years.csv")
    lines = []
    for year in range(2012, 2022):
        ident = next(r for r in rows if r["year"] == str(year) and r["order"] == "original")
        perm = [r for r in rows if r["year"] == str(year) and r["order"] != "original"]
        med = lambda ev: c.med(num(r[ev]) for r in perm)  # noqa: E731
        lines.append(
            f"{year} & {num(ident['final_rate_min_pct']):.2f}--{num(ident['final_rate_max_pct']):.2f} & "
            f"{pct(ident['TNC'])} & {pct(ident['TVF'])} & {pct(ident['TSV'])} & "
            f"{pct(med('TNC'))} & {pct(med('TVF'))} & {pct(med('TSV'))} \\\\")
    write(dest, "supp_q1_years.tex", lines)
    # simulated permutations
    rows = read("simulated_orders.csv")
    lines = []
    for r in rows:
        if r["event"].startswith("present"):
            continue
        share = "" if r["share_with_later_violation"] in ("", None) else f"{100 * num(r['share_with_later_violation']):.1f}"
        inside = "" if r["executed_orders"] in ("", None) else (
            f"{int(float(r['executed_orders_inside_p05_p95']))}/{int(float(r['executed_orders']))}")
        lines.append(
            f"{r['query']} & {EVENT_TEX[r['event']]} & {'first run' if r['position'] == 'start' else 'held'} & "
            f"{pct(r['p05'])} & {pct(r['p25'])} & {pct(r['median'])} & {pct(r['p75'])} & {pct(r['p95'])} & "
            f"{share} & {inside} \\\\")
    write(dest, "supp_simulated_orders.tex", lines)
    # milestones for Q1 and Q3
    rows = read("milestones_Q1.csv")
    lines = []
    for scope, label in (("canonical", "canonical"), ("nine", "permuted")):
        for r in (x for x in rows if x["scope"].startswith(scope)):
            lines.append(
                f"{label} & {100 * float(r['target']):.0f}\\% & {pct(r['selected_row_fraction_median'])} & "
                f"{num(r['contributing_units_median']):.1f} & {num(r['numerical_error_median']):.3f} & "
                f"{num(r['mae_pp_median']):.2f} & {num(r['max_err_pp_median']):.2f} & "
                f"{num(r['rho_shape_median']):.2f} & {num(r['trend_agreement_median']):.2f} \\\\")
        lines.append("\\addlinespace[2pt]")
    write(dest, "supp_q1_milestones.tex", lines)
    rows = read("milestones_Q3.csv")
    lines = []
    for scope, label in (("canonical", "canonical"), ("nine", "permuted")):
        for r in (x for x in rows if x["scope"].startswith(scope)):
            lines.append(
                f"{label} & {100 * float(r['target']):.0f}\\% & {num(r['covered_states_median']):.0f} & "
                f"{pct(r['support_median_median'], 0)} & {num(r['numerical_error_median']):.3f} & "
                f"{num(r['spearman_rho_median']):.3f} & {pct(r['top5_present_median'], 0)} & "
                f"{pct(r['top_k_overlap_median'], 0)} \\\\")
        lines.append("\\addlinespace[2pt]")
    write(dest, "supp_q3_milestones.tex", lines)


def context(dest: Path, summary: dict) -> None:
    # elapsed-time context of the order collection (single executions)
    t = summary["timing_context_order_collection"]
    lines = []
    for q in c.QUERIES:
        rows = [("first frame", "first_frame_ms_median")]
        rows += [(EVENT_TEX[ev], f"{ev}_start_ms_median") for ev in ORDER_OF_EVENTS[q]]
        rows += [("final result", "final_ms_median")]
        for i, (label, key) in enumerate(rows):
            cells = " & ".join(sec(t[f"{q}_permuted_t{w}"][key]) for w in c.THREADS)
            lines.append(f"{TASK[q] if i == 0 else ''} & {label} & {cells} \\\\")
        if q != "Q3":
            lines.append("\\addlinespace[2pt]")
    write(dest, "supp_timing_context.tex", lines)


def main() -> None:
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT / "tex"
    dest.mkdir(parents=True, exist_ok=True)
    summary = json.loads((OUT / "summary.json").read_text())
    canonical(dest, summary)
    q2_milestones(dest)
    joint(dest)
    orders(dest, summary)
    mechanism(dest)
    workers(dest)
    supplement(dest, summary)
    context(dest, summary)
    print("wrote", dest)


if __name__ == "__main__":
    main()
