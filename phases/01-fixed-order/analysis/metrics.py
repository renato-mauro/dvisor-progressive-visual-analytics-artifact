"""Pure, dependency-light (numpy only) statistics implementing exactly the
equations in anotacoes/draft/paperdraft.tex, section "Numerical, Structural,
and Stability Metrics" and "Derived Convergence Times". Every function takes
plain arrays/numbers and returns a plain float or None — this module knows
nothing about dvisor, JSONL, or the filesystem, so it can be re-run offline
against a saved raw trace at any time, per the paper's own reproducibility
requirement (section "Experimental Protocol and Reproducibility": "Convergence
metrics are recomputed offline from this trace so that alternative
definitions can be evaluated without rerunning the query").

Equation numbers referenced in comments below are the \\label{eq:...} names
used in the paper draft, for direct cross-checking against the LaTeX source.
"""
from __future__ import annotations

import math
from typing import Optional, Sequence

import numpy as np


def nmae(partial: Sequence[float], final: Sequence[float]) -> Optional[float]:
    """Eq. (eq:nmae): sum|partial-final| / sum|final|. None if the final
    vector is all zero (undefined denominator), never inf/nan."""
    final = np.asarray(final, dtype=float)
    partial = np.asarray(partial, dtype=float)
    denom = np.sum(np.abs(final))
    if denom == 0:
        return None
    return float(np.sum(np.abs(partial - final)) / denom)


def pearson(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    """Eq. (eq:pearson). Returns None (not NaN) when either vector has zero
    variance — "no linear relationship is defined" is a distinct case from
    "computed and equals some number"."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) != len(y) or len(x) < 2:
        return None
    xm = x - x.mean()
    ym = y - y.mean()
    dx = float(np.sum(xm * xm))
    dy = float(np.sum(ym * ym))
    if dx == 0 or dy == 0:
        return None
    return float(np.sum(xm * ym) / math.sqrt(dx * dy))


def rank_with_ties(values: Sequence[float]) -> np.ndarray:
    """Average ranks (e.g. [10,20,10] -> [1.5,3,1.5]) — the standard input
    to a tie-correct Spearman correlation (paper: "Ties receive average
    ranks")."""
    values = np.asarray(values, dtype=float)
    n = len(values)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(n, dtype=float)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        ranks[order[i : j + 1]] = avg_rank
        i = j + 1
    return ranks


def spearman(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    """Eq. (eq:spearman): rho_s = pearson(R(x), R(y)) — computed exactly as
    the paper specifies (Pearson correlation of the rank vectors), not the
    tie-free shortcut formula, so average-rank ties fall out correctly."""
    return pearson(rank_with_ties(x), rank_with_ties(y))


def trend_agreement(partial: Sequence[float], final: Sequence[float], epsilon: float) -> Optional[dict]:
    """Eq. (eq:trend). Classifies each consecutive difference as up/down/flat
    (|delta| < epsilon counts as flat) and returns the fraction of matching
    classifications between partial and final, plus the per-pair labels for
    inspection. None when there are fewer than 2 differences to compare."""
    partial = np.asarray(partial, dtype=float)
    final = np.asarray(final, dtype=float)
    n = len(partial)
    if n < 3 or len(final) != n:
        return None

    def sign(delta: float) -> str:
        if abs(delta) < epsilon:
            return "flat"
        return "up" if delta > 0 else "down"

    pairs = []
    agree = 0
    for i in range(n - 1):
        sp = sign(partial[i + 1] - partial[i])
        sf = sign(final[i + 1] - final[i])
        match = sp == sf
        if match:
            agree += 1
        pairs.append({"i": i, "partial": sp, "final": sf, "label": f"{sp}/{sf}" if match else "discordant"})
    return {"value": agree / len(pairs), "pairs": pairs}


def _kl_term(p: float, q: float) -> float:
    """p*log2(p/q), 0 when p==0 (standard convention avoiding log(0))."""
    if p == 0:
        return 0.0
    return p * math.log2(p / q)


def js_divergence(p: Sequence[float], q: Sequence[float]) -> float:
    """D_JS(P,Q), base-2 log (bits), range [0,1] — the convention used by
    Lin (1991), cited in the paper for this exact quantity."""
    p = np.asarray(p, dtype=float)
    q = np.asarray(q, dtype=float)
    m = (p + q) / 2.0
    jsd = 0.0
    for pi, qi, mi in zip(p, q, m):
        jsd += 0.5 * _kl_term(pi, mi) + 0.5 * _kl_term(qi, mi)
    return max(0.0, jsd)


def js_distance(p: Sequence[float], q: Sequence[float]) -> float:
    return math.sqrt(js_divergence(p, q))


def js_similarity(p: Sequence[float], q: Sequence[float]) -> float:
    """Eq. (eq:js-sim): S_JS(P,Q) = 1 - sqrt(D_JS(P,Q))."""
    return 1.0 - js_distance(p, q)


def wasserstein1d(p: Sequence[float], q: Sequence[float], bin_width: float = 1.0) -> float:
    """Eq. (eq:wasserstein): sum_i |F_P(i)-F_Q(i)| * bin_width, over two
    histograms sharing the same ordered, equally-spaced support (maternal
    age, one-year bins), both normalized to sum 1. Implemented directly from
    the paper's own closed form rather than via a library, to guarantee
    exact correspondence with eq:wasserstein regardless of how a library
    might parameterize weighted 1D Wasserstein distance."""
    p = np.asarray(p, dtype=float)
    q = np.asarray(q, dtype=float)
    cum_p = np.cumsum(p)[:-1]
    cum_q = np.cumsum(q)[:-1]
    return float(np.sum(np.abs(cum_p - cum_q)) * bin_width)


def top_k_overlap(partial_ranked: Sequence[tuple], final_ranked: Sequence[tuple], k: int) -> float:
    """Eq. (eq:topk): |T_k^(t) ∩ T_k*| / k, given two lists of (key, value)
    already sorted descending by value."""
    top_partial = {key for key, _ in partial_ranked[:k]}
    top_final = {key for key, _ in final_ranked[:k]}
    return len(top_partial & top_final) / k


def sort_ranked_desc(entries: Sequence[tuple]) -> list:
    return sorted(entries, key=lambda kv: kv[1], reverse=True)


def first_stable_run(values: Sequence[Optional[float]], threshold: float, k: int, direction: str = "above") -> int:
    """Eq. (eq:stable-run): the earliest index i such that values[i..i+k-1]
    all satisfy the threshold condition in `direction` ("above": value >=
    threshold, used for TVF/TSV; "below": value <= threshold, used for TNC,
    since a smaller NMAE is what "converged" means). A None entry always
    breaks the run (an ineligible/undefined frame can't count toward
    persistence). Returns -1 if no such run exists.
    """
    run = 0
    for i, v in enumerate(values):
        ok = v is not None and (v >= threshold if direction == "above" else v <= threshold)
        if ok:
            run += 1
            if run >= k:
                return i - k + 1
        else:
            run = 0
    return -1
