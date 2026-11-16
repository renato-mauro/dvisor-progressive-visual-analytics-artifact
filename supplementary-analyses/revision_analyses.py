"""Supplementary offline analyses of the archived traces.

Everything here is recomputed from the raw frames of the two collections and
from the per-row-group contributions in blocks/. No query is executed.

Outputs (output/):
  canonical_events.csv     events of the ten canonical four-worker runs, with
                           confirmation frame, later violations, hold point
                           and elapsed time
  order_events.csv         the same detail for each of the 90 order runs
  order_dispersion.csv     dispersion across the nine executed permutations
  worker_paired.csv        paired differences between worker counts by order
  q3_mechanism.csv         presence of the final Top-5 states versus observed
                           Top-5 recovery, per order, one logical worker
  simulated_orders.csv     event quantiles over simulated block permutations
  milestones.csv           chart-scale quantities at fixed row fractions
  joint_sensitivity.csv    TNC/TVF order per run over thresholds and persistence
  persistence.csv          event positions for persistence 1, 3 and 5
  q1_years.csv             Q1 events for every year, one logical worker
  robustness.json          effect of weight and delivery codes
  summary.json             scalar facts quoted in the manuscript
"""
from __future__ import annotations

import csv
import json
import random
import statistics
from multiprocessing import Pool

import common as c

EVENT_LABEL = {
    "tnc": "TNC", "tvf": "TVF", "tsv": "TSV", "tnc_visible": "TNC-visible", "tvf_rank": "TVF-rank",
    "tvf_top5_80": "Top5-80", "tvf_top5_100": "Top5-100", "tcov90": "TCov-90",
}
NMAE_GRID = (0.025, 0.05, 0.10)
FID_GRID = (0.85, 0.90, 0.925, 0.95)
K_GRID = (1, 3, 5)
N_SIM = 1000
SIM_SEED = 20261115


def write_csv(name: str, rows: list[dict]) -> None:
    c.OUT.mkdir(exist_ok=True)
    if not rows:
        return
    fields = list(rows[0].keys())
    with open(c.OUT / name, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def rnd(v, n=6):
    return None if v is None else round(v, n)


def flat_event(detail: dict) -> dict:
    g = lambda key, field: (detail[key][field] if detail.get(key) else None)  # noqa: E731
    return {
        "reached": detail["reached"],
        "start_row_fraction": rnd(g("start", "row_fraction")),
        "start_frame": g("start", "frame_index"),
        "start_elapsed_ms": g("start", "elapsed_ms"),
        "confirm_row_fraction": rnd(g("confirm", "row_fraction")),
        "confirm_frame": g("confirm", "frame_index"),
        "confirm_elapsed_ms": g("confirm", "elapsed_ms"),
        "later_violations": detail["later_violations"],
        "hold_row_fraction": rnd(g("hold", "row_fraction")),
        "hold_elapsed_ms": g("hold", "elapsed_ms"),
        "first_eligible_row_fraction": rnd(g("first_eligible", "row_fraction")),
        "starts_at_first_eligible": (
            detail["reached"] and detail["first_eligible"] is not None
            and detail["start"]["index"] == detail["first_eligible"]["index"]
        ),
    }


def stats(values) -> dict:
    vals = [v for v in values if v is not None]
    if not vals:
        return {"n": 0, "median": None, "min": None, "max": None, "q25": None, "q75": None}
    return {"n": len(vals), "median": rnd(statistics.median(vals)), "min": rnd(min(vals)),
            "max": rnd(max(vals)), "q25": rnd(c.quantile(vals, 0.25)), "q75": rnd(c.quantile(vals, 0.75))}


# ------------------------------------------------------ canonical collection

def canonical(summary: dict) -> dict:
    rows_out, per_run = [], []
    cache = {}
    for q in c.QUERIES:
        runs = c.phase1_runs(q)
        R = {rid: c.frame_rows(q, fr) for rid, fr in runs.items()}
        cache[q] = R
        E = {rid: c.all_events(q, rows) for rid, rows in R.items()}
        first_ms = [rows[0]["elapsed_ms"] for rows in R.values()]
        final_ms = [rows[-1]["elapsed_ms"] for rows in R.values()]
        summary[f"{q}_canonical_first_frame_ms"] = stats(first_ms)
        summary[f"{q}_canonical_final_ms"] = stats(final_ms)
        summary[f"{q}_canonical_first_frame_row_fraction"] = stats(
            rows[0]["processed_row_fraction"] for rows in R.values())
        summary[f"{q}_frames_per_run"] = sorted({len(rows) for rows in R.values()})
        for ev in next(iter(E.values())):
            ds = [E[rid][ev] for rid in E]
            fl = [flat_event(d) for d in ds]
            for rid, f in zip(E, fl):
                per_run.append({"query": q, "run_id": rid, "event": EVENT_LABEL[ev], **f})
            reached = [f for f in fl if f["reached"]]
            row = {
                "query": q, "event": EVENT_LABEL[ev], "runs": len(fl), "reached": len(reached),
                "start_median": stats(f["start_row_fraction"] for f in fl)["median"],
                "start_min": stats(f["start_row_fraction"] for f in fl)["min"],
                "start_max": stats(f["start_row_fraction"] for f in fl)["max"],
                "confirm_median": stats(f["confirm_row_fraction"] for f in fl)["median"],
                "hold_median": stats(f["hold_row_fraction"] for f in fl)["median"],
                "hold_min": stats(f["hold_row_fraction"] for f in fl)["min"],
                "hold_max": stats(f["hold_row_fraction"] for f in fl)["max"],
                "runs_with_later_violation": sum(1 for f in reached if f["later_violations"]),
                "runs_starting_at_first_eligible": sum(1 for f in reached if f["starts_at_first_eligible"]),
                "start_ms_median": stats(f["start_elapsed_ms"] for f in fl)["median"],
                "confirm_ms_median": stats(f["confirm_elapsed_ms"] for f in fl)["median"],
                "hold_ms_median": stats(f["hold_elapsed_ms"] for f in fl)["median"],
                "final_ms_median": statistics.median(final_ms),
                "first_frame_ms_median": statistics.median(first_ms),
            }
            if q == "Q1":
                units = [R[rid][E[rid][ev]["start"]["index"]]["contributing_units"]
                         for rid in E if E[rid][ev]["reached"]]
                row["units_at_start_median"] = statistics.median(units)
                row["units_at_start_min"] = min(units)
                row["units_at_start_max"] = max(units)
            rows_out.append(row)
    write_csv("canonical_events.csv", rows_out)
    write_csv("canonical_events_by_run.csv", per_run)
    return cache


# ---------------------------------------------------------- order collection

def order_runs(summary: dict) -> dict:
    cache, detail_rows, disp_rows, pair_rows = {}, [], [], []
    canon = {}
    for q in c.QUERIES:
        runs = c.phase2_runs(q)
        R = {key: c.frame_rows(q, fr) for key, fr in runs.items()}
        cache[q] = R
        E = {key: c.all_events(q, rows) for key, rows in R.items()}
        events = list(next(iter(E.values())))
        # run-to-run range of the canonical four-worker repetitions (first collection)
        p1 = {rid: c.all_events(q, c.frame_rows(q, fr)) for rid, fr in c.phase1_runs(q).items()}
        for ev in events:
            for (ds, t), e in E.items():
                detail_rows.append({"query": q, "event": EVENT_LABEL[ev], "dataset": ds, "threads": t,
                                    **flat_event(e[ev])})
            perms = c.DATASETS[1:]
            for field in ("start", "hold"):
                row = {"query": q, "event": EVENT_LABEL[ev], "position": field}
                for t in c.THREADS:
                    row[f"identity_t{t}"] = rnd(c.frac(E[("original", t)][ev], field))
                    s = stats(c.frac(E[(ds, t)][ev], field) for ds in perms)
                    row[f"perm_median_t{t}"], row[f"perm_min_t{t}"], row[f"perm_max_t{t}"] = (
                        s["median"], s["min"], s["max"])
                    row[f"perm_reached_t{t}"] = sum(1 for ds in perms if E[(ds, t)][ev]["reached"])
                    row[f"perm_orders_with_later_violation_t{t}"] = sum(
                        1 for ds in perms if E[(ds, t)][ev]["later_violations"])
                pooled = stats(c.frac(E[(ds, t)][ev], field) for ds in perms for t in c.THREADS)
                row.update(pooled_median=pooled["median"], pooled_min=pooled["min"], pooled_max=pooled["max"],
                           pooled_q25=pooled["q25"], pooled_q75=pooled["q75"])
                disp_rows.append(row)
            # paired differences by order, in percentage points of processed rows
            for a, b in ((1, 2), (1, 4), (2, 4)):
                diffs = {}
                for ds in c.DATASETS:
                    fa, fb = c.frac(E[(ds, a)][ev]), c.frac(E[(ds, b)][ev])
                    if fa is not None and fb is not None:
                        diffs[ds] = (fb - fa) * 100
                absd = {ds: abs(v) for ds, v in diffs.items()}
                worst = max(absd, key=absd.get)
                pair_rows.append({
                    "query": q, "event": EVENT_LABEL[ev], "pair": f"{b} vs {a}", "orders": len(diffs),
                    "median_diff_pp": rnd(statistics.median(diffs.values()), 3),
                    "median_abs_diff_pp": rnd(statistics.median(absd.values()), 3),
                    "max_abs_diff_pp": rnd(absd[worst], 3), "order_with_max": worst,
                    "orders_above_1pp": sum(1 for v in absd.values() if v > 1),
                    "orders_above_5pp": sum(1 for v in absd.values() if v > 5),
                })
            rep = [c.frac(d[ev]) for d in p1.values()]
            canon[(q, ev)] = {"query": q, "event": EVENT_LABEL[ev],
                              "canonical_repetitions": len(rep),
                              "repetition_min": rnd(min(rep)), "repetition_max": rnd(max(rep)),
                              "repetition_range_pp": rnd((max(rep) - min(rep)) * 100, 3)}
    write_csv("order_events.csv", detail_rows)
    write_csv("order_dispersion.csv", disp_rows)
    write_csv("worker_paired.csv", pair_rows)
    write_csv("canonical_repetition_range.csv", list(canon.values()))
    return cache


# -------------------------------------------------------------- Q3 mechanism

def _presence(rows: list[dict], need: float):
    for r in rows:
        if r["top5_present"] >= need - 1e-9:
            return r["processed_row_fraction"]
    return None


def q3_mechanism_row(name: str, rows: list[dict]) -> dict:
    E = c.all_events("Q3", rows)
    eligible = [r for r in rows if r["eligible_for_fidelity"]]
    below = [r for r in eligible if r["top_k_overlap"] < r["top5_present"] - 1e-9]
    out = {"order": name}
    for label, need, ev in (("80", 0.8, "tvf_top5_80"), ("100", 1.0, "tvf_top5_100")):
        hold = E[ev]["hold"]
        out[f"present_{label}"] = rnd(_presence(rows, need))
        out[f"top5_{label}_start"] = rnd(c.frac(E[ev]))
        out[f"top5_{label}_hold"] = rnd(c.frac(E[ev], "hold"))
        out[f"top5_{label}_later_violations"] = E[ev]["later_violations"]
        out[f"support_median_at_hold_{label}"] = rnd(rows[hold["index"]]["support_median"]) if hold else None
    out.update(
        tcov90=rnd(c.frac(E["tcov90"])), tvf_rank=rnd(c.frac(E["tvf_rank"])),
        tnc_visible=rnd(c.frac(E["tnc_visible"])), tsv=rnd(c.frac(E["tsv"])),
        tsv_hold=rnd(c.frac(E["tsv"], "hold")),
        eligible_frames=len(eligible), frames_overlap_below_presence=len(below),
        cutoff_ties=sum(1 for r in rows if r["cutoff_tie"]),
    )
    return out


def q3_mechanism(blocks: c.Blocks, orders: dict, summary: dict) -> dict:
    named = {"UF-year (identity)": orders["original"], "year-UF": blocks.year_uf_order()}
    named.update({ds: orders[ds] for ds in c.DATASETS[1:]})
    rows_by_order = {name: c.frame_rows("Q3", c.simulate(blocks, "Q3", order)) for name, order in named.items()}
    table = [q3_mechanism_row(name, rows) for name, rows in rows_by_order.items()]
    write_csv("q3_mechanism.csv", table)
    perms = [r for r in table if r["order"].startswith("shuf")]
    for key in ("present_80", "top5_80_start", "top5_80_hold", "present_100", "top5_100_start",
                "top5_100_hold", "tcov90", "support_median_at_hold_100", "support_median_at_hold_80"):
        summary[f"Q3_logical_perm_{key}"] = stats(r[key] for r in perms)
    final = rows_by_order["year-UF"][-1]
    summary["Q3_final_top5"] = final["final_top5"]
    yu = rows_by_order["year-UF"]
    summary["Q3_year_uf_milestones"] = [
        {"target": t, **{k: rnd(c.first_at_or_above(yu, t)[k], 4) for k in (
            "processed_row_fraction", "domain_coverage", "spearman_rho", "top_k_overlap",
            "top5_present", "numerical_error", "support_median")},
         "covered_states": c.first_at_or_above(yu, t)["covered_states"]}
        for t in (0.05, 0.10, 0.25, 0.50)
    ]
    return rows_by_order


# ------------------------------------------------- simulated block permutations

def _sim_one(args):
    seed, n = args
    blocks = _sim_one.blocks
    rng = random.Random(seed)
    order = list(range(n))
    rng.shuffle(order)
    out = {}
    for q in c.QUERIES:
        rows = c.frame_rows(q, c.simulate(blocks, q, order))
        for ev, d in c.all_events(q, rows).items():
            out[(q, ev, "start")] = c.frac(d)
            out[(q, ev, "hold")] = c.frac(d, "hold")
            out[(q, ev, "violated")] = bool(d["later_violations"]) if d["reached"] else None
        if q == "Q3":
            out[(q, "present_80", "start")] = _presence(rows, 0.8)
            out[(q, "present_100", "start")] = _presence(rows, 1.0)
    return out


def _sim_init():
    _sim_one.blocks = c.Blocks()


def simulated_orders(summary: dict, executed: dict) -> None:
    n = c.Blocks().n
    with Pool(initializer=_sim_init) as pool:
        results = pool.map(_sim_one, [(SIM_SEED + i, n) for i in range(N_SIM)], chunksize=10)
    keys = [k for k in results[0] if k[2] != "violated"]
    table = []
    for q, ev, pos in keys:
        vals = [r[(q, ev, pos)] for r in results if r[(q, ev, pos)] is not None]
        row = {"query": q, "event": EVENT_LABEL.get(ev, ev), "position": pos, "simulations": N_SIM,
               "reached": len(vals)}
        for name, qq in (("p05", 0.05), ("p25", 0.25), ("median", 0.5), ("p75", 0.75), ("p95", 0.95)):
            row[name] = rnd(c.quantile(vals, qq))
        if (q, ev, "violated") in results[0] and pos == "start":
            row["share_with_later_violation"] = rnd(
                sum(1 for r in results if r[(q, ev, "violated")]) / N_SIM, 4)
        else:
            row["share_with_later_violation"] = None
        ex = executed.get((q, ev, pos))
        if ex:
            lo, hi = c.quantile(vals, 0.05), c.quantile(vals, 0.95)
            row["executed_orders_inside_p05_p95"] = sum(1 for v in ex if v is not None and lo <= v <= hi)
            row["executed_orders"] = len(ex)
        else:
            row["executed_orders_inside_p05_p95"] = None
            row["executed_orders"] = None
        table.append(row)
    write_csv("simulated_orders.csv", table)
    summary["simulated_orders"] = {"n": N_SIM, "seed": SIM_SEED}


# ----------------------------------------------------------------- milestones

MILESTONE_COLUMNS = {
    "Q1": ("numerical_error", "mae_pp", "max_err_pp", "rho_shape", "trend_agreement", "contributing_units"),
    "Q2": ("numerical_error", "tv_distance", "js_distance", "js_similarity", "wasserstein_distance",
           "max_bin_err_pp"),
    "Q3": ("numerical_error", "spearman_rho", "top_k_overlap", "top5_present", "domain_coverage",
           "covered_states", "support_median"),
}
TARGETS = (0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90)


def milestones(canon: dict, order: dict) -> None:
    table = []
    for q in c.QUERIES:
        groups = {
            "canonical, 4 workers, 10 runs": list(canon[q].values()),
            "identity, 1/2/4 workers": [rows for (ds, _), rows in order[q].items() if ds == "original"],
            "nine permutations, 1/2/4 workers": [rows for (ds, _), rows in order[q].items() if ds != "original"],
        }
        for scope, runs in groups.items():
            for target in TARGETS:
                sel = [c.first_at_or_above(rows, target) for rows in runs]
                row = {"query": q, "scope": scope, "target": target, "runs": len(sel),
                       "selected_row_fraction_median": rnd(statistics.median(
                           s["processed_row_fraction"] for s in sel))}
                for col in MILESTONE_COLUMNS[q]:
                    s = stats(s_[col] for s_ in sel)
                    row[f"{col}_median"], row[f"{col}_min"], row[f"{col}_max"] = s["median"], s["min"], s["max"]
                table.append(row)
    # one file per query keeps the columns homogeneous
    for q in c.QUERIES:
        write_csv(f"milestones_{q}.csv", [r for r in table if r["query"] == q])


# ------------------------------------------------- thresholds and persistence

def sensitivity(canon: dict, order: dict) -> None:
    joint, persist = [], []
    for q in ("Q1", "Q2"):
        groups = {
            "canonical": list(canon[q].values()),
            "permuted": [rows for (ds, _), rows in order[q].items() if ds != "original"],
        }
        for scope, runs in groups.items():
            for k in K_GRID:
                for tn in NMAE_GRID:
                    for tf in FID_GRID:
                        tnc, tvf = [], []
                        for rows in runs:
                            e = c.all_events(q, rows, k=k, overrides={"tnc": tn, "tvf": tf})
                            tnc.append(c.frac(e["tnc"]))
                            tvf.append(c.frac(e["tvf"]))
                        both = [(a, b) for a, b in zip(tnc, tvf) if a is not None and b is not None]
                        joint.append({
                            "query": q, "scope": scope, "persistence": k, "nmae_threshold": tn,
                            "fidelity_threshold": tf, "runs": len(runs),
                            "tnc_reached": sum(v is not None for v in tnc),
                            "tvf_reached": sum(v is not None for v in tvf),
                            "tvf_before_tnc": sum(1 for a, b in both if b < a),
                            "tnc_before_tvf": sum(1 for a, b in both if a < b),
                            "same_frame": sum(1 for a, b in both if a == b),
                            "tnc_median": rnd(c.med(tnc)), "tvf_median": rnd(c.med(tvf)),
                        })
    for q in c.QUERIES:
        groups = {
            "canonical": list(canon[q].values()),
            "identity": [rows for (ds, _), rows in order[q].items() if ds == "original"],
            "permuted": [rows for (ds, _), rows in order[q].items() if ds != "original"],
        }
        for scope, runs in groups.items():
            for k in K_GRID:
                ev_all = [c.all_events(q, rows, k=k) for rows in runs]
                for ev in ev_all[0]:
                    s = stats(c.frac(e[ev]) for e in ev_all)
                    persist.append({"query": q, "scope": scope, "event": EVENT_LABEL[ev], "persistence": k,
                                    "runs": len(runs), "reached": s["n"], "median": s["median"],
                                    "min": s["min"], "max": s["max"]})
    write_csv("joint_sensitivity.csv", joint)
    write_csv("persistence.csv", persist)


# -------------------------------------------------------------- Q1 other years

def q1_years(blocks: c.Blocks, orders: dict, summary: dict) -> None:
    table = []
    for year in range(2012, 2022):
        for ds in c.DATASETS:
            rows = c.frame_rows("Q1", c.simulate(blocks, "Q1", orders[ds], year=year))
            e = c.all_events("Q1", rows)
            fin = [r["low_weight_births"] / r["total_births"] * 100
                   for r in c.simulate(blocks, "Q1", orders[ds], year=year)[-1]["result"]]
            table.append({"year": year, "order": ds, "final_rate_min_pct": rnd(min(fin), 3),
                          "final_rate_max_pct": rnd(max(fin), 3),
                          **{EVENT_LABEL[ev]: rnd(c.frac(d)) for ev, d in e.items()},
                          **{f"{EVENT_LABEL[ev]}_hold": rnd(c.frac(d, "hold")) for ev, d in e.items()}})
    write_csv("q1_years.csv", table)
    ident = [r for r in table if r["order"] == "original"]
    perm = [r for r in table if r["order"] != "original"]
    for ev in ("TNC", "TVF", "TSV"):
        summary[f"Q1_years_identity_{ev}"] = stats(r[ev] for r in ident)
        summary[f"Q1_years_permuted_{ev}"] = stats(r[ev] for r in perm)
        by_year = [statistics.median(r[ev] for r in perm if r["year"] == y and r[ev] is not None)
                   for y in range(2012, 2022)]
        summary[f"Q1_years_permuted_median_by_year_{ev}"] = stats(by_year)
    summary["Q1_years_identity_tnc_before_tvf"] = sum(
        1 for r in ident if r["TNC"] is not None and r["TVF"] is not None and r["TNC"] < r["TVF"])
    summary["Q1_2018_identity"] = next(r for r in ident if r["year"] == 2018)


# ------------------------------------------------------------------ robustness

def robustness(blocks: c.Blocks, orders: dict) -> dict:
    out = {}
    prof = c._read_csv(c.BLOCKS / "column_profile.csv")[0]
    out["column_profile"] = prof
    b = list(blocks.block.values())
    y18 = [r for r in b if r["year"] == 2018]
    out["weights"] = {
        "all_years_lt500": sum(r["weight_lt500"] for r in b),
        "all_years_zero": sum(r["weight_zero"] for r in b),
        "all_years_ge9000": sum(r["weight_ge9000"] for r in b),
        "all_years_low_weight": sum(r["low_weight_births"] for r in b),
        "y2018_rows": sum(r["total_births"] for r in y18),
        "y2018_lt500": sum(r["weight_lt500"] for r in y18),
        "y2018_zero": sum(r["weight_zero"] for r in y18),
        "y2018_low_weight": sum(r["low_weight_births"] for r in y18),
        "block_share_lt500_max": max(r["weight_lt500"] / r["total_births"] for r in b),
        "block_share_lt500_median": statistics.median(r["weight_lt500"] / r["total_births"] for r in b),
    }

    def run(q, ds, variant):
        frames = c.simulate(blocks, q, orders[ds], variant=variant)
        rows = c.frame_rows(q, frames)
        return frames, rows, {ev: c.frac(d) for ev, d in c.all_events(q, rows).items()}

    for q in ("Q1", "Q2"):
        base_f, _, _ = run(q, "original", "paper")
        var_f, _, _ = run(q, "original", "ge500")
        if q == "Q1":
            a = [r["low_weight_births"] / r["total_births"] * 100 for r in base_f[-1]["result"]]
            v = [r["low_weight_births"] / r["total_births"] * 100 for r in var_f[-1]["result"]]
            cmp = {"pearson_between_finals": c.m.pearson(a, v),
                   "max_abs_diff_pp": max(abs(x - y) for x, y in zip(a, v)),
                   "mean_rate_paper_pct": sum(a) / len(a), "mean_rate_ge500_pct": sum(v) / len(v)}
        else:
            lo, hi = c.CONFIG["maternal_age_min"], c.CONFIG["maternal_age_max"]

            def dist(frames):
                cnt = {r["maternal_age"]: r["low_weight_births"] for r in frames[-1]["result"]
                       if lo <= r["maternal_age"] <= hi}
                tot = sum(cnt.values())
                return [cnt.get(a, 0) / tot for a in range(lo, hi + 1)]
            a, v = dist(base_f), dist(var_f)
            cmp = {"js_similarity_between_finals": c.m.js_similarity(a, v),
                   "nmae_between_finals": c.m.nmae(v, a),
                   "wasserstein_years_between_finals": c.m.wasserstein1d(v, a, 1),
                   "max_bin_diff_pp": max(abs(x - y) for x, y in zip(a, v)) * 100}
        events = {}
        for ds in c.DATASETS:
            _, _, e0 = run(q, ds, "paper")
            _, _, e1 = run(q, ds, "ge500")
            events[ds] = {ev: {"paper": rnd(e0[ev]), "ge500": rnd(e1[ev])} for ev in e0}
        diffs = {ev: [abs(events[ds][ev]["paper"] - events[ds][ev]["ge500"]) * 100 for ds in c.DATASETS
                      if events[ds][ev]["paper"] is not None and events[ds][ev]["ge500"] is not None]
                 for ev in next(iter(events.values()))}
        out[f"{q}_ge500"] = {
            "final_comparison": cmp, "events_by_order": events,
            "max_abs_event_shift_pp": {ev: rnd(max(v), 3) for ev, v in diffs.items()},
            "orders_with_shift_above_1pp": {ev: sum(1 for x in v if x > 1) for ev, v in diffs.items()},
        }

    # Q3: ignored delivery code in the denominator
    uf_tot, uf_ign = {}, {}
    for r in b:
        uf_tot[r["uf"]] = uf_tot.get(r["uf"], 0) + r["total_births"]
        uf_ign[r["uf"]] = uf_ign.get(r["uf"], 0) + r["ignored_delivery"]
    share = {uf: uf_ign[uf] / uf_tot[uf] for uf in uf_tot}
    base_f, _, _ = run("Q3", "original", "paper")
    var_f, _, _ = run("Q3", "original", "known_delivery")
    rate = lambda frames: {r["state"]: r["cesarean_births"] / r["total_births"] for r in frames[-1]["result"]}  # noqa: E731
    ra, rv = rate(base_f), rate(var_f)
    states = sorted(ra)
    top = lambda rr: [s for s, _ in c.m.sort_ranked_desc([(s, rr[s]) for s in states])[:c.TOP_K]]  # noqa: E731
    order_of = lambda rr: [s for s, _ in c.m.sort_ranked_desc([(s, rr[s]) for s in states])]  # noqa: E731
    events = {}
    named = dict(orders)
    named["year-UF"] = blocks.year_uf_order()
    for ds, order in named.items():
        e0 = {ev: c.frac(d) for ev, d in c.all_events(
            "Q3", c.frame_rows("Q3", c.simulate(blocks, "Q3", order))).items()}
        e1 = {ev: c.frac(d) for ev, d in c.all_events(
            "Q3", c.frame_rows("Q3", c.simulate(blocks, "Q3", order, variant="known_delivery"))).items()}
        events[ds] = {ev: {"paper": rnd(e0[ev]), "known_delivery": rnd(e1[ev])} for ev in e0}
    diffs = {ev: [abs(events[ds][ev]["paper"] - events[ds][ev]["known_delivery"]) * 100 for ds in events
                  if events[ds][ev]["paper"] is not None and events[ds][ev]["known_delivery"] is not None]
             for ev in next(iter(events.values()))}
    out["Q3_known_delivery"] = {
        "ignored_total": sum(uf_ign.values()),
        "ignored_share_overall": sum(uf_ign.values()) / sum(uf_tot.values()),
        "ignored_share_by_uf_min": min(share.values()), "ignored_share_by_uf_max": max(share.values()),
        "uf_with_max_share": max(share, key=share.get),
        "ignored_share_by_uf": {str(k): rnd(v) for k, v in sorted(share.items())},
        "spearman_between_final_rankings": c.m.spearman([ra[s] for s in states], [rv[s] for s in states]),
        "same_final_top5_set": set(top(ra)) == set(top(rv)), "same_final_top5_order": top(ra) == top(rv),
        "final_top5_paper": top(ra), "final_top5_known_delivery": top(rv),
        "same_full_order": order_of(ra) == order_of(rv),
        "max_abs_rate_diff_pp": max(abs(ra[s] - rv[s]) for s in states) * 100,
        "events_by_order": events,
        "max_abs_event_shift_pp": {ev: rnd(max(v), 3) for ev, v in diffs.items()},
        "orders_with_shift_above_1pp": {ev: sum(1 for x in v if x > 1) for ev, v in diffs.items()},
    }
    (c.OUT / "robustness.json").write_text(json.dumps(out, indent=2))
    return out


# ----------------------------------------------------------------- other facts

def extra_facts(canon: dict, order: dict, blocks: c.Blocks, summary: dict) -> None:
    import numpy as np
    q2 = [r for rows in canon["Q2"].values() for r in rows]
    x = np.array([r["numerical_error"] for r in q2])
    summary["Q2_corr_nmae_js_distance"] = float(np.corrcoef(x, [r["js_distance"] for r in q2])[0, 1])
    summary["Q2_corr_nmae_wasserstein"] = float(np.corrcoef(x, [r["wasserstein_distance"] for r in q2])[0, 1])
    summary["Q2_corr_nmae_max_bin"] = float(np.corrcoef(x, [r["max_bin_err_pp"] for r in q2])[0, 1])
    summary["Q2_frames_pooled"] = len(q2)
    summary["Q2_zero_mass_frames_all_runs"] = sum(
        1 for rows in list(canon["Q2"].values()) + list(order["Q2"].values()) for r in rows
        if not r["low_weight_mass"])
    ratio = [r["js_distance"] / r["tv_distance"] for r in q2 if r["tv_distance"] > 0]
    summary["Q2_js_distance_over_tv_median"] = statistics.median(ratio)
    # chart-scale reading of the two Q2 events in the canonical runs
    for ev in ("tvf", "tnc"):
        sel = []
        for rows in canon["Q2"].values():
            e = c.all_events("Q2", rows)
            sel.append(rows[e[ev]["start"]["index"]])
        summary[f"Q2_canonical_at_{ev}"] = {k: rnd(statistics.median(s[k] for s in sel), 4) for k in (
            "processed_row_fraction", "numerical_error", "tv_distance", "js_distance",
            "wasserstein_distance", "max_bin_err_pp")}
    lo, hi = c.CONFIG["maternal_age_min"], c.CONFIG["maternal_age_max"]
    fin = {r["maternal_age"]: r["low_weight_births"]
           for r in next(iter(c.phase1_runs("Q2").values()))[-1]["result"] if lo <= r["maternal_age"] <= hi}
    tot = sum(fin.values())
    summary["Q2_final"] = {"mass": tot, "peak_age": max(fin, key=fin.get),
                           "peak_share_pct": rnd(100 * max(fin.values()) / tot, 3),
                           "mean_age": rnd(sum(a * n for a, n in fin.items()) / tot, 3)}
    # Q1 final series and chart-scale reading of its events
    q1_final = next(iter(c.phase1_runs("Q1").values()))[-1]["result"]
    rates = [r["low_weight_births"] / r["total_births"] * 100 for r in q1_final]
    summary["Q1_final"] = {"rate_min_pct": rnd(min(rates), 3), "rate_max_pct": rnd(max(rates), 3),
                           "rate_range_pp": rnd(max(rates) - min(rates), 3),
                           "rate_mean_pct": rnd(sum(rates) / len(rates), 3)}
    for ev in ("tnc", "tvf", "tsv"):
        sel = []
        for rows in canon["Q1"].values():
            e = c.all_events("Q1", rows)
            sel.append(rows[e[ev]["start"]["index"]])
        summary[f"Q1_canonical_at_{ev}"] = {k: rnd(statistics.median(s[k] for s in sel), 4) for k in (
            "processed_row_fraction", "numerical_error", "mae_pp", "max_err_pp", "rho_shape",
            "trend_agreement", "contributing_units")}
    summary["Q1_canonical_first_frame"] = {
        k: stats(rows[0][k] for rows in canon["Q1"].values()) for k in ("rho_shape", "processed_row_fraction")}
    summary["Q1_negative_first_frame_runs"] = sum(
        1 for rows in canon["Q1"].values() if rows[0]["rho_shape"] is not None and rows[0]["rho_shape"] < 0)
    # non-monotone fidelity: runs whose Pearson falls below 0.90 after first reaching it
    def dips(rows):
        seen = False
        for r in rows:
            v = r["rho_shape"]
            if v is None:
                continue
            if v >= 0.9:
                seen = True
            elif seen:
                return True
        return False
    summary["Q1_canonical_runs_with_fidelity_dip"] = sum(dips(rows) for rows in canon["Q1"].values())
    summary["Q1_order_runs_with_fidelity_dip"] = sum(dips(rows) for rows in order["Q1"].values())
    # Q3 canonical reading at fixed fractions and state counts
    summary["Q3_states"] = len(canon["Q3"][next(iter(canon["Q3"]))][-1]["final_top5"]) and 27
    summary["Q3_tcov90_states_required"] = min(
        n for n in range(1, 28) if n / 27 >= c.TH["domain_coverage_theta"])
    cut = [r for rows in list(canon["Q3"].values()) + list(order["Q3"].values()) for r in rows if r["cutoff_tie"]]
    summary["Q3_cutoff_ties_all_runs"] = len(cut)
    undefined = sum(1 for rows in list(canon["Q3"].values()) + list(order["Q3"].values()) for r in rows
                    if r["eligible_for_fidelity"] and r["spearman_rho"] is None)
    summary["Q3_undefined_spearman_in_eligible_frames"] = undefined
    refine = []
    for rows, frames in ((c.frame_rows("Q3", fr), fr) for fr in c.phase1_runs("Q3").values()):
        final = {r["state"]: r["cesarean_births"] / r["total_births"] for r in frames[-1]["result"]}
        refine.append(sum(1 for f in frames for r in f["result"]
                          if r["cesarean_births"] / r["total_births"] != final[r["state"]]))
    summary["Q3_canonical_frame_state_pairs_differing_from_final"] = stats(refine)
    # row-group size heterogeneity
    sizes = [b["total_births"] for b in blocks.block.values()]
    s18 = [b["total_births"] for b in blocks.block.values() if b["year"] == 2018]
    summary["row_group_size_ratio_all"] = rnd(max(sizes) / min(sizes), 2)
    summary["row_group_size_ratio_2018"] = rnd(max(s18) / min(s18), 2)
    by_uf = {}
    for b in blocks.block.values():
        by_uf[b["uf"]] = by_uf.get(b["uf"], 0) + b["total_births"]
    summary["largest_uf_share"] = rnd(max(by_uf.values()) / sum(by_uf.values()), 4)
    summary["uf_sequence_identity"] = blocks.uf_sequence()


def timing_context(canon: dict, order: dict, summary: dict) -> None:
    """Elapsed times. Repeated canonical runs support timing statements; the
    single executions of the order collection are descriptive context only."""
    out = {}
    for q in c.QUERIES:
        for t in c.THREADS:
            runs = [rows for (ds, tt), rows in order[q].items() if ds != "original" and tt == t]
            ev_all = [c.all_events(q, rows) for rows in runs]
            entry = {"final_ms_median": statistics.median(rows[-1]["elapsed_ms"] for rows in runs),
                     "first_frame_ms_median": statistics.median(rows[0]["elapsed_ms"] for rows in runs)}
            for ev in ev_all[0]:
                entry[f"{EVENT_LABEL[ev]}_start_ms_median"] = c.med(
                    e[ev]["start"]["elapsed_ms"] if e[ev]["start"] else None for e in ev_all)
                entry[f"{EVENT_LABEL[ev]}_hold_ms_median"] = c.med(
                    e[ev]["hold"]["elapsed_ms"] if e[ev]["hold"] else None for e in ev_all)
            out[f"{q}_permuted_t{t}"] = entry
            ident = order[q][("original", t)]
            ev = c.all_events(q, ident)
            out[f"{q}_identity_t{t}"] = {
                "final_ms": ident[-1]["elapsed_ms"], "first_frame_ms": ident[0]["elapsed_ms"],
                **{f"{EVENT_LABEL[k]}_start_ms": (d["start"]["elapsed_ms"] if d["start"] else None)
                   for k, d in ev.items()}}
    summary["timing_context_order_collection"] = out
    below = []
    for rows in canon["Q3"].values():
        below.append(sum(1 for r in rows if r["eligible_for_fidelity"]
                         and r["top_k_overlap"] < r["top5_present"] - 1e-9))
    summary["Q3_canonical_frames_overlap_below_presence"] = stats(below)
    summary["Q3_canonical_support_median_at_10pct"] = stats(
        c.first_at_or_above(rows, 0.10)["support_median"] for rows in canon["Q3"].values())


def main() -> None:
    c.OUT.mkdir(exist_ok=True)
    blocks = c.Blocks()
    orders = c.permutation_orders()
    summary: dict = {}
    canon = canonical(summary)
    order = order_runs(summary)
    q3_mechanism(blocks, orders, summary)
    milestones(canon, order)
    sensitivity(canon, order)
    q1_years(blocks, orders, summary)
    robustness(blocks, orders)
    extra_facts(canon, order, blocks, summary)
    timing_context(canon, order, summary)
    executed = {}
    for q in c.QUERIES:
        for (ds, t), rows in order[q].items():
            if ds == "original" or t != 1:
                continue
            for ev, d in c.all_events(q, rows).items():
                executed.setdefault((q, ev, "start"), []).append(c.frac(d))
                executed.setdefault((q, ev, "hold"), []).append(c.frac(d, "hold"))
    simulated_orders(summary, executed)
    (c.OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print("wrote", c.OUT)


if __name__ == "__main__":
    main()
