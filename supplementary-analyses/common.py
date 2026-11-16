"""Shared helpers for the supplementary offline analyses.

The per-frame metric definitions are imported unchanged from
phases/02-order-sensitivity/analysis so that every number produced here uses
the same code as the official tables. This module adds:

* loaders for the archived traces of both phases;
* per-frame quantities requested in review (Top-5 presence bound, per-state
  support, rate error in percentage points, chart-scale distribution error);
* event bookkeeping beyond the first sustained run (confirmation frame, later
  violations, first frame from which the criterion holds until completion);
* a logical one-worker merge that rebuilds cumulative frames from per-row-group
  contributions for any row-group order.
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
from pathlib import Path
from typing import Iterable, Optional, Sequence

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PHASE1 = ROOT / "phases" / "01-fixed-order"
PHASE2 = ROOT / "phases" / "02-order-sensitivity"
BLOCKS = HERE / "blocks"
OUT = HERE / "output"

sys.path.insert(0, str(PHASE2 / "analysis"))
import analyze as an  # noqa: E402
import metrics as m  # noqa: E402

CONFIG = json.loads((PHASE2 / "config" / "experiment.json").read_text())
TH = CONFIG["thresholds"]
TOP_K = CONFIG["top_k"]
QUERIES = ("Q1", "Q2", "Q3")
DATASETS = ["original"] + [f"shuf{i:02d}" for i in range(1, 10)]
THREADS = (1, 2, 4)


# ---------------------------------------------------------------- loading

def load_trace(path: Path) -> list[dict]:
    return an.load_frames(path)


def phase1_runs(query: str) -> dict[str, list[dict]]:
    """Ten measured canonical-order runs with four workers (warm-up excluded)."""
    runs = {}
    for path in sorted((PHASE1 / "output" / "raw" / query).glob(f"{query}-run-*.jsonl")):
        runs[path.stem] = load_trace(path)
    return runs


def phase2_runs(query: str) -> dict[tuple[str, int], list[dict]]:
    runs = {}
    for ds in DATASETS:
        for t in THREADS:
            path = PHASE2 / "output" / "raw" / query / f"{query}-{ds}-t{t:02d}-run-001.jsonl"
            runs[(ds, t)] = load_trace(path)
    return runs


def permutation_orders() -> dict[str, list[int]]:
    """Row-group order of each configured dataset: position j holds source
    row group order[j]. The canonical file has the identity order."""
    manifest = json.loads((PHASE2 / "config" / CONFIG["permutation_manifest"].split("/")[-1]).read_text())
    by_file = {entry["parquet"]: list(entry["order"]) for entry in manifest["files"]}
    orders = {}
    for dataset in CONFIG["datasets"]:
        if dataset["manifest_file"] is None:
            orders[dataset["id"]] = list(range(manifest["num_row_groups"]))
        else:
            orders[dataset["id"]] = by_file[dataset["manifest_file"]]
    return orders


# ------------------------------------------------- per-row-group contributions

def _read_csv(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return [{k: int(v) for k, v in row.items()} for row in csv.DictReader(f)]


class Blocks:
    """Per-row-group contributions extracted with DuckDB (extract_blocks.sh)."""

    def __init__(self) -> None:
        self.block = {r["rg"]: r for r in _read_csv(BLOCKS / "blocks.csv")}
        bad = [r["rg"] for r in self.block.values() if r["n_uf"] != 1 or r["n_year"] != 1]
        if bad:
            raise ValueError(f"row groups mixing UFs or years: {bad}")
        self.month: dict[int, list[dict]] = {}
        for r in _read_csv(BLOCKS / "blocks_month.csv"):
            self.month.setdefault(r["rg"], []).append(r)
        self.age: dict[int, list[dict]] = {}
        for r in _read_csv(BLOCKS / "blocks_age.csv"):
            self.age.setdefault(r["rg"], []).append(r)
        self.n = len(self.block)

    def uf_sequence(self) -> list[int]:
        """UFs in the order of their first row group in the identity file."""
        seen: list[int] = []
        for rg in range(self.n):
            uf = self.block[rg]["uf"]
            if uf not in seen:
                seen.append(uf)
        return seen

    def year_uf_order(self) -> list[int]:
        """Deterministic reference: year major, UF (identity sequence) minor."""
        pos = {uf: i for i, uf in enumerate(self.uf_sequence())}
        return sorted(range(self.n), key=lambda rg: (self.block[rg]["year"], pos[self.block[rg]["uf"]]))


def simulate(blocks: Blocks, query: str, order: Sequence[int], *, year: int = 2018,
             variant: str = "paper") -> list[dict]:
    """Cumulative frames of a logical one-worker merge over `order`.

    variant "paper" reproduces the executed SQL. Variant "ge500" applies
    PESO >= 500 to Q1/Q2 (numerator and denominator). Variant "known_delivery"
    removes ignored delivery codes (PARTO = 9) from the Q3 denominator.
    """
    frames = []
    if query == "Q3":
        acc: dict[int, list[int]] = {}
        for i, rg in enumerate(order, start=1):
            b = blocks.block[rg]
            total = b["total_births"] - (b["ignored_delivery"] if variant == "known_delivery" else 0)
            cur = acc.setdefault(b["uf"], [0, 0])
            cur[0] += b["cesarean_births"]
            cur[1] += total
            frames.append(_frame(query, i, len(order), [
                {"state": s, "cesarean_births": v[0], "total_births": v[1]} for s, v in sorted(acc.items())
            ]))
        return frames
    if query == "Q1":
        relevant = [rg for rg in order if blocks.block[rg]["year"] == year]
        acc = {}
        for i, rg in enumerate(relevant, start=1):
            for r in blocks.month[rg]:
                cur = acc.setdefault(r["month"], [0, 0])
                if variant == "ge500":
                    cur[0] += r["low_weight_ge500"]
                    cur[1] += r["total_ge500"]
                else:
                    cur[0] += r["low_weight_births"]
                    cur[1] += r["total_births"]
            frames.append(_frame(query, i, len(relevant), [
                {"month": k, "low_weight_births": v[0], "total_births": v[1]} for k, v in sorted(acc.items())
            ]))
        return frames
    if query == "Q2":
        acc = {}
        for i, rg in enumerate(order, start=1):
            for r in blocks.age[rg]:
                cur = acc.setdefault(r["maternal_age"], [0, 0])
                if variant == "ge500":
                    cur[0] += r["low_weight_ge500"]
                    cur[1] += r["total_ge500"]
                else:
                    cur[0] += r["low_weight_births"]
                    cur[1] += r["total_births"]
            frames.append(_frame(query, i, len(order), [
                {"maternal_age": k, "low_weight_births": v[0], "total_births": v[1]}
                for k, v in sorted(acc.items()) if v[1] > 0
            ]))
        return frames
    raise ValueError(query)


def _frame(query: str, i: int, total: int, result: list[dict]) -> dict:
    return {
        "run_id": "simulated", "query_id": query, "frame_index": i, "elapsed_ms": None,
        "completed_fragments": i, "total_fragments": total,
        "fragment_fraction": i / total, "is_final": i == total, "result": result,
    }


def canonical_result(result: list[dict]) -> list[tuple]:
    return sorted(tuple(sorted(r.items())) for r in result)


# --------------------------------------------------------- per-frame metrics

def frame_rows(query: str, frames: list[dict]) -> list[dict]:
    """Official per-frame metrics plus the additional quantities."""
    rows = an.ANALYZERS[query](frames, CONFIG)["frames"]
    extra = {"Q1": _q1_extra, "Q2": _q2_extra, "Q3": _q3_extra}[query](frames)
    for row, e in zip(rows, extra):
        row.update(e)
    return rows


def _q1_extra(frames: list[dict]) -> list[dict]:
    final = {r["month"]: r["low_weight_births"] / r["total_births"] for r in frames[-1]["result"]}
    out = []
    for raw in frames:
        cur = {r["month"]: r["low_weight_births"] / r["total_births"]
               for r in raw["result"] if r["total_births"] > 0}
        diffs = [abs(cur[k] - final[k]) * 100 for k in cur]
        out.append({
            "mae_pp": sum(diffs) / len(diffs) if diffs else None,
            "max_err_pp": max(diffs) if diffs else None,
            "contributing_units": raw["completed_fragments"],
        })
    return out


def _q2_extra(frames: list[dict]) -> list[dict]:
    lo, hi = CONFIG["maternal_age_min"], CONFIG["maternal_age_max"]
    ages = list(range(lo, hi + 1))

    def dist(result):
        counts = {a: 0 for a in ages}
        for r in result:
            if lo <= r["maternal_age"] <= hi:
                counts[r["maternal_age"]] = r["low_weight_births"]
        mass = sum(counts.values())
        return [counts[a] / mass for a in ages] if mass else None, mass

    final, _ = dist(frames[-1]["result"])
    out = []
    for raw in frames:
        p, mass = dist(raw["result"])
        out.append({
            "low_weight_mass": mass,
            "max_bin_err_pp": max(abs(a - b) for a, b in zip(p, final)) * 100 if p else None,
            "tv_distance": 0.5 * sum(abs(a - b) for a, b in zip(p, final)) if p else None,
        })
    return out


def _q3_extra(frames: list[dict]) -> list[dict]:
    final = {r["state"]: r for r in frames[-1]["result"]}
    final_rate = {s: r["cesarean_births"] / r["total_births"] for s, r in final.items()}
    ranked = m.sort_ranked_desc([(s, final_rate[s]) for s in sorted(final)])
    final_top = [s for s, _ in ranked[:TOP_K]]
    out = []
    for raw in frames:
        cur = {r["state"]: r for r in raw["result"] if r["total_births"] > 0}
        present = [s for s in final_top if s in cur]
        support = sorted(cur[s]["total_births"] / final[s]["total_births"] for s in cur)
        rates = sorted((r["cesarean_births"] / r["total_births"] for r in cur.values()), reverse=True)
        cutoff_tie = len(rates) > TOP_K and rates[TOP_K - 1] == rates[TOP_K]
        top_support = [cur[s]["total_births"] / final[s]["total_births"] for s in present]
        out.append({
            "top5_present": len(present) / TOP_K,
            "support_min": support[0] if support else None,
            "support_median": statistics.median(support) if support else None,
            "top5_support_min": min(top_support) if top_support else None,
            "cutoff_tie": cutoff_tie,
        })
    for row in out:
        row["final_top5"] = final_top
    return out


# ------------------------------------------------------------------ events

def event_series(query: str, rows: list[dict]) -> dict[str, tuple[list, float, str]]:
    """(series, threshold, direction) for every event, with the official gating."""
    if query == "Q3":
        ok = [r["eligible_for_fidelity"] for r in rows]
        gate = lambda col: [r[col] if e else None for r, e in zip(rows, ok)]  # noqa: E731
        return {
            "tnc_visible": (gate("numerical_error"), TH["nmae_convergence_theta"], "below"),
            "tvf_rank": (gate("spearman_rho"), TH["visual_fidelity_theta"], "above"),
            "tvf_top5_80": (gate("top_k_overlap"), TH["top_k_overlap_relaxed_theta"], "above"),
            "tvf_top5_100": (gate("top_k_overlap"), TH["top_k_overlap_strict_theta"], "above"),
            "tcov90": ([r["domain_coverage"] for r in rows], TH["domain_coverage_theta"], "above"),
            "tsv": ([r["ranking_stability"] for r in rows], TH["stable_view_theta"], "above"),
        }
    fid = an.FIDELITY_COLUMN[query]
    stab = an.STABILITY_COLUMN[query]
    if an.COVERAGE_GATED[query]:
        ok = [r.get("eligible_for_fidelity", True) for r in rows]
    else:
        ok = [True] * len(rows)
    return {
        "tnc": ([r["numerical_error"] if e else None for r, e in zip(rows, ok)],
                TH["nmae_convergence_theta"], "below"),
        "tvf": ([r[fid] if e else None for r, e in zip(rows, ok)], TH["visual_fidelity_theta"], "above"),
        "tsv": ([r[stab] for r in rows], TH["stable_view_theta"], "above"),
    }


def _ok(v: Optional[float], theta: float, direction: str) -> bool:
    return v is not None and (v >= theta if direction == "above" else v <= theta)


def event_detail(series: Sequence[Optional[float]], theta: float, direction: str, k: int,
                 rows: list[dict]) -> dict:
    """First sustained run and what happens after it.

    start: first frame of the first run of k consecutive satisfying frames.
    confirm: frame at which that run can be recognised (start + k - 1).
    later_violations: frames after confirmation that violate the criterion.
    hold: first frame from which the criterion holds until completion.
    """
    n = len(series)
    flags = [_ok(v, theta, direction) for v in series]
    start = m.first_stable_run(series, theta, k, direction)
    t = n
    while t > 0 and flags[t - 1]:
        t -= 1
    hold = t if t < n else None
    if start < 0:
        return {"reached": False, "start": None, "confirm": None, "later_violations": None,
                "hold": _pos(rows, hold), "first_eligible": _first_defined(series, rows)}
    confirm = start + k - 1
    return {
        "reached": True,
        "start": _pos(rows, start),
        "confirm": _pos(rows, confirm),
        "later_violations": sum(1 for j in range(confirm + 1, n) if not flags[j]),
        "hold": _pos(rows, hold),
        "first_eligible": _first_defined(series, rows),
    }


def _first_defined(series, rows):
    for i, v in enumerate(series):
        if v is not None:
            return _pos(rows, i)
    return None


def _pos(rows: list[dict], idx: Optional[int]) -> Optional[dict]:
    if idx is None:
        return None
    r = rows[idx]
    return {"index": idx, "frame_index": r["frame_index"], "row_fraction": r["processed_row_fraction"],
            "elapsed_ms": r["elapsed_ms"]}


def all_events(query: str, rows: list[dict], k: Optional[int] = None,
               overrides: Optional[dict] = None) -> dict[str, dict]:
    k = TH["persistence_k"] if k is None else k
    out = {}
    for name, (series, theta, direction) in event_series(query, rows).items():
        if overrides and name in overrides:
            theta = overrides[name]
        out[name] = event_detail(series, theta, direction, k, rows)
    return out


def first_at_or_above(rows: list[dict], target: float) -> dict:
    """Milestone rule used throughout: first frame whose processed-row
    fraction is at or above the target."""
    for r in rows:
        if r["processed_row_fraction"] >= target - 1e-12:
            return r
    return rows[-1]


# ----------------------------------------------------------------- summary

def med(values: Iterable[Optional[float]]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return statistics.median(vals) if vals else None


def quantile(values: Sequence[float], q: float) -> float:
    vals = sorted(values)
    if not vals:
        return float("nan")
    pos = (len(vals) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)


def frac(detail: dict, key: str = "start") -> Optional[float]:
    p = detail.get(key)
    return p["row_fraction"] if p else None
