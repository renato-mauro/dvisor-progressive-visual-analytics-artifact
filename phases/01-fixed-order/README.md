# Phase 1: fixed-order characterization

Automated, reproducible data collection and analysis for the repeated
fixed-order characterization of Q1--Q3. This phase uses the same
serialization-controlled identity-order Parquet file that serves as the
control in Phase 2. It retains the original Phase-1 protocol: four workers,
one discarded warm-up, and ten measured runs per query.

This is the *instrumentation*: a Node/Playwright harness that runs the three
queries many times against the real, hosted SINASC parquet and saves every
progressive frame, plus a Python pipeline that turns those raw traces into
the metrics, tables, and figures the paper reports. Nothing here modifies the
manuscript.

## Two stages, two runtimes

1. **Data collection** (Node + Playwright, `harness/`) — drives a real
   Chromium browser, executes each query progressively `N_RUNS` times (plus
   discarded warm-up runs) in a fresh, isolated browser context per run
   (cold cache), and writes one raw JSONL trace and one metadata JSON per
   run. Nothing here computes a metric — this stage only records what
   happened.
2. **Offline analysis** (Python, `analysis/`) — reads the raw traces and
   computes every metric in the paper, entirely after the fact. Re-running
   this stage with a different threshold or epsilon never requires
   re-collecting data.

## Setup

```bash
# Node side (harness)
npm install
npx playwright install chromium   # only needed once per machine

# Python side (analysis) — a local venv keeps this self-contained
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running

```bash
# 1. Collect raw data (see config/experiment.json for N_RUNS, target year, etc.)
node harness/run_experiment.mjs

# during development: a fast, single-run smoke test for one query
node harness/run_experiment.mjs --query=Q1 --warmup=0 --runs=1

# 2. Turn raw traces into metrics, tables, and figures (needs the venv active)
python analysis/build_all.py
```

`build_all.py` runs, in order: `run_analysis.py` (raw JSONL → derived CSVs),
`build_tables.py` (derived CSVs → summary, milestone, and sensitivity tables),
`make_figures.py` (→ every PDF/PNG figure), and
`resolve_paper_placeholders.py` (→ a JSON resolving every `\newcommand`
placeholder macro in the paper draft to the value this run actually
measured — for copying into the paper by hand, never written there
automatically).

The full collection run (1 warm-up + 10 measured executions × 3 queries,
with the default config) takes roughly 15–20 minutes on a normal broadband
connection. Q2 and Q3 both scan the full unfiltered 10-year period across 270
fragments and account for most of that time.

## Configuration

[`config/experiment.json`](config/experiment.json) fixes every symbol the
paper draft leaves as a placeholder macro (`\TargetYear`, `\CesareanCode`,
`\NumRuns`, and the TVF/TSV/TNC thresholds and persistence length in
eq:stable-run) to one concrete, documented value:

| Field | Value | Why |
|---|---|---|
| `target_year` | 2018 | Mid-range year, avoids edge effects at the dataset's 2012/2021 boundaries. |
| `dataset_period.start_year` / `end_year` | 2012 / 2021 | Defines the full-period denominator used by Q2 and Q3. Q1 uses `target_year` as both endpoints. |
| `cesarean_code` | 2 | `PARTO = 2`, empirically validated earlier in this project (see `consultas.md` §3.8) — matches known Brazilian cesarean-rate epidemiology by state. |
| `runs.warmup_runs` / `measured_runs` | 1 / 10 | Matches the paper's own protocol language ("after [warm-up policy]... median and IQR"). |
| `runs.cache_policy` | cold | A fresh, isolated Playwright browser context per run — no shared HTTP cache or storage between runs, chosen for reproducibility over raw speed. |
| `thresholds.persistence_k` | 3 | K in eq:stable-run — a single lucky frame never counts as convergence. |
| `thresholds.visual_fidelity_theta` / `stable_view_theta` | 0.90 / 0.99 | Adopted TVF/TSV thresholds. TVF sensitivity is recomputed for 0.85, 0.90, 0.925, and 0.95. |
| `thresholds.nmae_convergence_theta` | 0.05 | TNC threshold — 5% normalized error. |
| `thresholds.domain_coverage_theta` | 0.90 | Minimum fraction of categories that must already be represented before a frame is eligible for TNC/TVF (Q1/Q3 only — see `analysis/analyze.py`'s module docstring). |

## Deviations from the paper's illustrative SQL

The paper's Q1–Q3 listings are written against an idealized English-named
schema (Table "Subset of the SINASC schema used in the experiments") and
occasionally against syntax the current dvisor SQL dialect doesn't (or
didn't) support. [`harness/queries.mjs`](harness/queries.mjs) documents
every substitution inline; summarized here:

1. **Column names** — the real hosted file has the original Portuguese
   SINASC field names, not the paper's English ones. Substituted exactly
   per the paper's own schema-map table: `birth_date`→`DTNASC`,
   `birth_weight`→`PESO`, `maternal_age`→`IDADEMAE`, `delivery_type`→`PARTO`,
   `state`→`floor(CODMUNRES/10000)` (SINASC has no standalone UF column —
   see `consultas.md` §3.8).
2. **`yearMonth(...)`** (paper's Q1) does not exist in dvisor's `api.js`.
   Since Q1 already filters `WHERE year(DTNASC) = TARGET_YEAR`, a plain
   `month(DTNASC)` is an unambiguous grouping key within that filtered year.
3. **`COUNT(*)`** is used verbatim — supported by the SQL compiler as of
   2026-09-19, no substitution needed.
4. **`GROUP BY <alias>`** (paper's Q2, Q3) isn't valid dvisor SQL — GROUP BY
   must match the projection's underlying *expression*, not its alias. Q2's
   key is a bare column, so it's simply repeated (`GROUP BY IDADEMAE`). Q3's
   key is a derived expression, so `GROUP BY 1` (the 1-based ordinal-position
   syntax added alongside `COUNT(*)`) is used instead of repeating it.

**No additional filters were introduced.** In particular, `PESO >= 500` and
`PARTO < 9` (data-quality filters used elsewhere on this site, e.g. the
SINASC Explorer catalog and `consultas.md`) are deliberately **not** applied
here, because the paper's Methods text doesn't specify them for these three
queries — this experiment matches the paper's stated scope exactly rather
than silently extending it. If this turns out to matter (e.g. `PARTO`'s
"ignored" sentinel values inflating `total_births` in Q3), that's a Methods
decision for the paper's authors to make explicitly, not one to bake into
the code unannounced.

## Metric and derived-time design decisions

`analysis/metrics.py` and `analysis/analyze.py` implement every equation in
the paper's "Numerical, Structural, and Stability Metrics" and "Derived
Convergence Times" sections directly (see their module docstrings for
equation-by-equation correspondence). Where the paper's prose leaves a
choice open, the docstring in `analyze.py` documents the decision made and
why — notably:

* A category that hasn't appeared yet is "unknown", never an observed zero
  (stated directly in the paper) — enforced by restricting Q1/Q3 metrics to
  the covered-category subset, compared against the *same restricted
  subset* of the final result.
* Q2 is the one exception: an unseen maternal age legitimately contributes
  zero mass to a partial *distribution* (unlike a rate), so its counts are
  zero-filled instead of excluded.
* The raw trace field `processed_fraction` is a fraction of completed
  fragments. Offline analysis preserves it as `fragment_fraction` and derives
  `processed_row_fraction` from cumulative `COUNT(*)` values. The denominator
  is tied to the query period: 2018 for Q1 and 2012–2021 for Q2 and Q3.
* Q2 numerical convergence uses NMAE on normalized age proportions. Raw-count
  NMAE is retained as `raw_count_completeness_error` because it is exactly one
  minus the fraction of final low-weight-birth counts accumulated. A
  progress-adjusted count NMAE is retained as a robustness check.
* TNC and TVF are coverage-gated for Q1/Q3 (a frame below
  `domain_coverage_theta` can't start or extend a convergence run) but not
  for Q2; TSV is never coverage-gated for any task, since it only ever
  compares two consecutive partial frames to each other.
* Q3's Top-*k* overlap compares the partial top-*k* (within whatever states
  are already covered) against the *global* final top-*k* — a final top-*k*
  state that hasn't appeared yet simply can't be in the partial top-*k*,
  which is the non-convergence signal the metric is meant to surface.

## Output layout

```
output/
    raw/{Q1,Q2,Q3}/<run_id>.jsonl   raw per-frame traces (canonical record)
    metadata/<run_id>.json           per-run metadata (SQL, browser, OS, ...)
    metadata/dataset-info.json       one-time dataset fingerprint (sha256, exact row count, exact byte size)
    derived/{Q1,Q2,Q3}_frames.csv    per-frame metrics, every run
    derived/{Q1,Q2,Q3}_summary.csv   per-run TNC/TVF/TSV + totals
    tables/main_results.{csv,tex}    median Final Time / TNC / TVF / TSV and processed-row fractions
    tables/milestones.{csv,tex}      NMAE and visual fidelity at processed-row milestones
    tables/fidelity_sensitivity.csv  TVF sensitivity for four thresholds
    tables/q2_nmae_sensitivity.csv   Q2 numerical-error definitions and thresholds
    tables/paper_placeholders.json   every paper \newcommand macro resolved from real collected data
    figures/*.pdf, *.png             every figure, vector PDF + PNG twin for quick viewing
```

Every raw frame keeps its full aggregated `result`, not just its metrics
(the paper: "the raw trace is the canonical experimental record... All
frames produced by valid runs are retained"). Warm-up runs are collected and
kept on disk like any other run (their JSONL/metadata files just have
`warmup` in the run id / `is_warmup: true`) but are excluded from the
medians and IQR in `build_tables.py` and `resolve_paper_placeholders.py`.

See [`REPROCESSING.md`](REPROCESSING.md) for the offline rebuild procedure,
validation checklist, and the additional instrumentation required only if a
new browser collection becomes necessary.

## Known limitations

* This is a single-machine, single-browser (Chromium) collection. The
  paper's `\BrowserDescription`/`\HardwareDescription` placeholders should
  be filled from whichever run actually backs the numbers reported, via
  `output/tables/paper_placeholders.json`.
