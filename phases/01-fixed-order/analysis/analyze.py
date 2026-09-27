"""Per-query offline analysis: reads every raw JSONL trace for one query
(one file per run, produced by ../harness/run_experiment.mjs) and computes,
for each run, the per-frame metrics and derived convergence times (TNC, TVF,
TSV) defined in anotacoes/draft/paperdraft.tex. Nothing here re-runs a query
or touches the network — this is exactly the "offline metric computation"
stage the paper's reproducibility section describes as separate from data
collection.

Design decisions not fully pinned down by the paper's prose (documented here
so they're auditable, not just implicit in code):

* A category not yet present in a partial frame's denominator means "unknown",
  not "zero" (paper: "A category that has not yet appeared is not
  automatically interpreted as an observed zero."). For Q1 and Q3, every
  shape/error/derived-time metric is therefore restricted to the subset of
  categories the current frame has already touched ("covered"), compared
  against the FINAL value of that same restricted subset — never padded with
  zeros. For Q2, a not-yet-seen age legitimately contributes zero mass to the
  partial *distribution* (a meaningful partial answer, unlike a rate), so its
  counts are zero-filled instead, matching eq. for p_i^(t) directly.
* "Domain coverage" gates TNC and TVF eligibility for Q1/Q3 (the same
  quantity the paper says will gate "structural-fidelity interpretation") —
  the coverage threshold is config.thresholds.domain_coverage_theta. Q2's
  TNC/TVF are not coverage-gated, matching the point above. TSV is never
  coverage-gated for any task, since it only ever compares two consecutive
  partial states against each other, not against the final result.
* Q3's top-k overlap compares the partial top-k (within the covered subset)
  against the *global* final top-k over the whole domain — a final-top-k
  state that hasn't appeared yet simply can't be in the partial top-k, which
  is exactly the non-convergence signal the metric should show.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import metrics as m


def load_frames(path: Path) -> list[dict]:
    frames = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                frames.append(json.loads(line))
    return frames


def _result_total_rows(result: list[dict]) -> int:
    """Number of query-relevant input rows represented by a cumulative result.

    All three experimental queries retain COUNT(*) AS total_births. Summing
    that field therefore recovers the exact number of qualifying rows already
    incorporated into a frame, independently of row-group size.
    """
    return int(sum(r.get("total_births", 0) or 0 for r in result))


def _period_coverage(query_id: str, config: dict) -> tuple[int, int]:
    if query_id == "Q1":
        year = int(config["target_year"])
        return year, year
    period = config["dataset_period"]
    return int(period["start_year"]), int(period["end_year"])


def _common_fields(raw: dict, period_total_rows: int, config: dict) -> dict:
    processed_rows = _result_total_rows(raw["result"])
    period_start_year, period_end_year = _period_coverage(raw["query_id"], config)
    return {
        k: raw[k]
        for k in (
            "run_id",
            "query_id",
            "frame_index",
            "elapsed_ms",
            "completed_fragments",
            "total_fragments",
            "transferred_bytes",
            "request_count",
            "is_final",
        )
    } | {
        # The historical raw field named processed_fraction is a fragment
        # count ratio. Preserve its value under an unambiguous name.
        "fragment_fraction": raw["processed_fraction"],
        "processed_rows": processed_rows,
        "period_total_rows": period_total_rows,
        "processed_row_fraction": (
            processed_rows / period_total_rows if period_total_rows else None
        ),
        "period_start_year": period_start_year,
        "period_end_year": period_end_year,
    }


# ---- Q1 — Temporal shape (monthly low-birth-weight rate) ----

def analyze_q1_run(frames: list[dict], config: dict) -> dict:
    epsilon = config["thresholds"]["trend_epsilon"]
    theta_cov = config["thresholds"]["domain_coverage_theta"]

    period_total_rows = _result_total_rows(frames[-1]["result"])
    final_by_month = {r["month"]: r for r in frames[-1]["result"]}
    domain = sorted(final_by_month.keys())

    def final_rate(month):
        r = final_by_month[month]
        return r["low_weight_births"] / r["total_births"] if r["total_births"] > 0 else None

    prev_rate_by_month: Optional[dict] = None
    rows = []
    for raw in frames:
        by_month = {r["month"]: r for r in raw["result"]}
        covered = [mo for mo in domain if by_month.get(mo, {}).get("total_births", 0) > 0]
        domain_coverage = len(covered) / len(domain) if domain else None

        def rate(mo):
            r = by_month[mo]
            return r["low_weight_births"] / r["total_births"]

        p = [rate(mo) for mo in covered]
        f = [final_rate(mo) for mo in covered]
        rho_shape = m.pearson(p, f) if len(covered) >= 2 else None
        numerical_error = m.nmae(p, f) if covered else None
        trend = m.trend_agreement(p, f, epsilon) if len(covered) >= 3 else None

        rho_stability = None
        if prev_rate_by_month is not None:
            common = [mo for mo in covered if mo in prev_rate_by_month]
            if len(common) >= 2:
                rho_stability = m.pearson([rate(mo) for mo in common], [prev_rate_by_month[mo] for mo in common])
        prev_rate_by_month = {mo: rate(mo) for mo in covered}

        row = _common_fields(raw, period_total_rows, config)
        row.update(
            domain_coverage=domain_coverage,
            numerical_error=numerical_error,
            rho_shape=rho_shape,
            trend_agreement=trend["value"] if trend else None,
            rho_stability=rho_stability,
            eligible_for_fidelity=(domain_coverage is not None and domain_coverage >= theta_cov),
        )
        rows.append(row)
    return {"frames": rows, "domain": domain}


# ---- Q2 — Distribution shape (maternal age among low-birth-weight births) ----

def analyze_q2_run(frames: list[dict], config: dict) -> dict:
    min_age, max_age = config["maternal_age_min"], config["maternal_age_max"]
    dense_domain = list(range(min_age, max_age + 1))

    def in_range(age):
        return min_age <= age <= max_age

    period_total_rows = _result_total_rows(frames[-1]["result"])
    final_num = {a: 0 for a in dense_domain}
    final_total = {a: 0 for a in dense_domain}
    excluded_age_groups = 0
    excluded_births = 0
    excluded_low_weight = 0
    for r in frames[-1]["result"]:
        if in_range(r["maternal_age"]):
            final_num[r["maternal_age"]] = r["low_weight_births"]
            final_total[r["maternal_age"]] = r["total_births"]
        else:
            excluded_age_groups += 1
            excluded_births += r["total_births"]
            excluded_low_weight += r["low_weight_births"]

    final_counts = [final_num[a] for a in dense_domain]
    final_mass = sum(final_counts) or 1
    final_dist = [c / final_mass for c in final_counts]
    final_covered_ages = sum(1 for a in dense_domain if final_total[a] > 0) or 1

    prev_dist = None
    rows = []
    for raw in frames:
        num = {a: 0 for a in dense_domain}
        total = {a: 0 for a in dense_domain}
        for r in raw["result"]:
            if in_range(r["maternal_age"]):
                num[r["maternal_age"]] = r["low_weight_births"]
                total[r["maternal_age"]] = r["total_births"]

        partial_counts = [num[a] for a in dense_domain]
        partial_mass = sum(partial_counts)
        partial_dist = [c / partial_mass for c in partial_counts] if partial_mass > 0 else [0.0] * len(dense_domain)

        domain_coverage = sum(1 for a in dense_domain if total[a] > 0) / final_covered_ages
        # Raw cumulative-count NMAE is algebraically equal to one minus the
        # fraction of the final low-weight-birth count accumulated so far. It
        # is therefore retained as a completeness diagnostic, not used for
        # Q2 numerical convergence.
        raw_count_completeness_error = m.nmae(partial_counts, final_counts)

        # Q2 is a distributional task. Numerical convergence is evaluated on
        # normalized bin proportions, avoiding the mechanical dependence of
        # raw cumulative counts on scan progress.
        numerical_error = m.nmae(partial_dist, final_dist)

        processed_rows = _result_total_rows(raw["result"])
        processed_row_fraction = (
            processed_rows / period_total_rows if period_total_rows else None
        )
        progress_adjusted_nmae = None
        if processed_row_fraction:
            projected_counts = [c / processed_row_fraction for c in partial_counts]
            progress_adjusted_nmae = m.nmae(projected_counts, final_counts)
        js_dist = m.js_distance(partial_dist, final_dist)
        js_similarity = 1 - js_dist
        wasserstein_distance = m.wasserstein1d(partial_dist, final_dist, 1)
        js_stability = (1 - m.js_distance(partial_dist, prev_dist)) if prev_dist is not None else None
        prev_dist = partial_dist

        row = _common_fields(raw, period_total_rows, config)
        row.update(
            domain_coverage=domain_coverage,
            numerical_error=numerical_error,
            compositional_nmae=numerical_error,
            raw_count_completeness_error=raw_count_completeness_error,
            progress_adjusted_nmae=progress_adjusted_nmae,
            js_distance=js_dist,
            js_similarity=js_similarity,
            wasserstein_distance=wasserstein_distance,
            js_stability=js_stability,
        )
        rows.append(row)

    return {
        "frames": rows,
        "domain": dense_domain,
        "exclusion": {
            "excluded_age_groups": excluded_age_groups,
            "excluded_births": excluded_births,
            "excluded_low_weight_births": excluded_low_weight,
            "reason": f"maternal_age outside [{min_age}, {max_age}] (implausible or missing/sentinel code)",
        },
    }


# ---- Q3 — Ranking (cesarean rate by state) ----

def analyze_q3_run(frames: list[dict], config: dict) -> dict:
    top_k = config["top_k"]
    theta_cov = config["thresholds"]["domain_coverage_theta"]

    period_total_rows = _result_total_rows(frames[-1]["result"])
    final_by_state = {r["state"]: r for r in frames[-1]["result"]}
    domain = sorted(final_by_state.keys())

    def final_rate(s):
        r = final_by_state[s]
        return r["cesarean_births"] / r["total_births"] if r["total_births"] > 0 else 0.0

    final_ranked = m.sort_ranked_desc([(s, final_rate(s)) for s in domain])
    final_top = {s for s, _ in final_ranked[:top_k]}

    prev_rate_by_state: Optional[dict] = None
    rows = []
    for raw in frames:
        by_state = {r["state"]: r for r in raw["result"]}
        covered = [s for s in domain if by_state.get(s, {}).get("total_births", 0) > 0]
        domain_coverage = len(covered) / len(domain) if domain else None
        eligible = domain_coverage is not None and domain_coverage >= theta_cov

        def rate(s):
            r = by_state[s]
            return r["cesarean_births"] / r["total_births"]

        spearman_rho = None
        top_k_overlap = None
        numerical_error = None
        if len(covered) >= 1:
            p = [rate(s) for s in covered]
            f = [final_rate(s) for s in covered]
            numerical_error = m.nmae(p, f)
        if len(covered) >= 2:
            p = [rate(s) for s in covered]
            f = [final_rate(s) for s in covered]
            spearman_rho = m.spearman(p, f)
            partial_top = {s for s, _ in m.sort_ranked_desc([(s, rate(s)) for s in covered])[:top_k]}
            top_k_overlap = len(partial_top & final_top) / top_k

        ranking_stability = None
        if prev_rate_by_state is not None:
            common = [s for s in covered if s in prev_rate_by_state]
            if len(common) >= 2:
                ranking_stability = m.spearman([rate(s) for s in common], [prev_rate_by_state[s] for s in common])
        prev_rate_by_state = {s: rate(s) for s in covered}

        row = _common_fields(raw, period_total_rows, config)
        row.update(
            domain_coverage=domain_coverage,
            eligible_for_fidelity=eligible,
            numerical_error=numerical_error,
            spearman_rho=spearman_rho,
            top_k_overlap=top_k_overlap,
            ranking_stability=ranking_stability,
        )
        rows.append(row)
    return {"frames": rows, "domain": domain, "final_ranked": final_ranked}


ANALYZERS = {"Q1": analyze_q1_run, "Q2": analyze_q2_run, "Q3": analyze_q3_run}

# Which per-frame column is the task-specific "structural fidelity" series
# (used for TVF) and "progressive stability" series (used for TSV), per
# Table~\ref{tab:metric-map} in the paper.
FIDELITY_COLUMN = {"Q1": "rho_shape", "Q2": "js_similarity", "Q3": "spearman_rho"}
STABILITY_COLUMN = {"Q1": "rho_stability", "Q2": "js_stability", "Q3": "ranking_stability"}
COVERAGE_GATED = {"Q1": True, "Q2": False, "Q3": True}


def compute_derived_times(frame_rows: list[dict], query_id: str, config: dict) -> dict:
    """TNC, TVF, TSV (eq:stable-run) for a single run's already-computed
    per-frame metric rows."""
    th = config["thresholds"]
    k = th["persistence_k"]
    gated = COVERAGE_GATED[query_id]

    def gate(row):
        return row.get("eligible_for_fidelity", True) if gated else True

    nmae_series = [r["numerical_error"] if gate(r) else None for r in frame_rows]
    fidelity_series = [r[FIDELITY_COLUMN[query_id]] if gate(r) else None for r in frame_rows]
    stability_series = [r[STABILITY_COLUMN[query_id]] for r in frame_rows]

    tnc_idx = m.first_stable_run(nmae_series, th["nmae_convergence_theta"], k, "below")
    tvf_idx = m.first_stable_run(fidelity_series, th["visual_fidelity_theta"], k, "above")
    tsv_idx = m.first_stable_run(stability_series, th["stable_view_theta"], k, "above")

    def describe(idx):
        if idx < 0:
            return None
        r = frame_rows[idx]
        return {
            "frame_index": r["frame_index"],
            "elapsed_ms": r["elapsed_ms"],
            "fragment_fraction": r["fragment_fraction"],
            "processed_rows": r["processed_rows"],
            "processed_row_fraction": r["processed_row_fraction"],
            "transferred_bytes": r["transferred_bytes"],
        }

    return {"tnc": describe(tnc_idx), "tvf": describe(tvf_idx), "tsv": describe(tsv_idx)}
