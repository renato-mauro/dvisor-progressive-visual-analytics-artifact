# Physical-order sensitivity experiment

Independent instrumentation for evaluating how the physical order of SINASC
Parquet row groups and the number of concurrent DVISOR workers affect the
quality trajectories of progressive visual results.

The repeated identity-order characterization is preserved in
`../01-fixed-order/` and is not read, changed, or overwritten by this phase.
This directory has its own DVISOR build, configuration, raw traces, derived
data, tables, and figures.

## Experimental matrix

The configured datasets are:

- `original`: canonical chronological/state order;
- `shuf01` through `shuf09`: nine seeded permutations of the same 270 row
  groups;
- `shuf10` exists in the supplied manifest but is deliberately excluded.

The identity-order file and the ten shuffled files have the same schema,
dimensions, serialization provenance, codec/encoding families, and aggregate
compressed-column size. Their experimental difference is row-group order.
The verification evidence is recorded in `PROVENANCE_AUDIT.md`.

Every dataset is evaluated with:

- Q1 temporal, Q2 distribution, and Q3 ranking;
- 1, 2, and 4 worker threads;
- one measured execution per combination;
- no warm-up runs.

This yields `10 datasets x 3 queries x 3 thread counts = 90` measured
executions. The 90 combinations are executed in a reproducible randomized
order (`execution_order_seed` in the configuration), so dataset, query, and
thread-count blocks are not confounded with a long-running temporal drift.

## Why there is no warm-up

The primary outcomes are numerical error, task-specific visual fidelity,
view stability, and domain coverage as functions of the fraction of
query-relevant rows processed. This experiment is not a performance or
scalability benchmark. Elapsed time, transferred bytes, and request counts
remain in the canonical trace as contextual metadata, but no inferential
claim should be based on them here.

Phase 1 retains its own warm-up policy and timing analysis in
`../01-fixed-order/`, preserving the methodological distinction between the
two phases.

## Inputs and provenance

Configuration is in `config/experiment.json`. The author-provided permutation
manifest is copied unchanged to:

```text
config/SINASC-2012-2021-shuffles.json
```

At startup the collector validates that every configured shuffled order is a
complete permutation of indices `0..269`, checks its configured seed, and
computes a SHA-256 digest of the order vector. Before any query begins, it
also performs a remote preflight against every selected Parquet and sidecar
metadata object. The sidecar JSON itself is parsed to confirm 270 row groups
and 28,789,402 rows before collection is allowed to start.

Remote dataset identities and HTTP object headers are saved once per dataset
under `output/datasets/`.

## Setup

From this directory:

```bash
npm install
npx playwright install chromium

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Collection

First inspect the plan without network access:

```bash
node harness/run_experiment.mjs --list-plan
```

Check whether every upload is publicly available without starting a query:

```bash
node harness/run_experiment.mjs --preflight-only
```

Run the complete 90-execution matrix:

```bash
node harness/run_experiment.mjs
```

Useful scoped invocations:

```bash
# Collect one selected combination (it retains its global planned sequence)
node harness/run_experiment.mjs --dataset=shuf01 --query=Q1 --threads=1

# Multiple selected values
node harness/run_experiment.mjs --dataset=original,shuf01 --query=Q1,Q3 --threads=1,4
```

Run identifiers encode every experimental factor:

```text
Q2-original-t01-run-001
Q2-shuf03-t04-run-001
```

Collection is resumable. If both the raw JSONL trace and metadata JSON for a
run already exist, that run is skipped. If only one exists, execution stops
and reports the incomplete pair rather than overwriting evidence.

## Raw trace schema

Every progressive frame records:

- run, query, dataset, permutation seed, and thread count;
- elapsed time and frame index;
- completed fragments and `fragment_fraction`;
- exact cumulative `processed_rows`, period denominator, and
  `processed_row_fraction`;
- transferred bytes and request count;
- the complete cumulative aggregate result.

Unlike the historical collector, the new trace never uses the ambiguous name
`processed_fraction` for fragment progress.

Per-run metadata additionally records the exact SQL, runtime environment,
permutation-order digest, final-result digest, and collection policy.

## Validation and offline analysis

After all 90 runs finish:

```bash
python analysis/build_all.py
```

This performs four stages:

1. verifies that all 90 expected traces exist, row progress is monotonic,
   full-period row totals are correct, and final results are identical across
   datasets and thread counts;
2. recomputes every per-frame convergence metric offline;
3. creates per-run, convergence-event, and milestone tables;
4. generates order-sensitivity figures using processed-row fraction as the
   horizontal coordinate.

To inspect a partial collection without accepting it as complete:

```bash
python analysis/validate_collection.py --allow-incomplete
```

## Output layout

```text
output/
    datasets/<dataset_id>.json
    raw/{Q1,Q2,Q3}/<run_id>.jsonl
    metadata/<run_id>.json
    validation/collection_validation.json
    derived/{Q1,Q2,Q3}_frames.csv
    derived/{Q1,Q2,Q3}_summary.csv
    tables/run_results.csv
    tables/event_summary.csv
    tables/order_effects.csv
    tables/q3_event_results.csv
    tables/milestones_by_run.csv
    tables/milestone_summary.csv
    figures/q1_q2_order_sensitivity_events.{pdf,png}
    figures/q1_q2_fidelity_trajectories.{pdf,png}
    figures/q3_fidelity_events.{pdf,png}
    figures/q3_quality_dimensions.{pdf,png}
```

## Intended interpretation

Thread count is used as a controlled factor that changes concurrent fragment
completion, not as a performance variable. The primary analysis asks whether
the locations and shapes of convergence trajectories remain stable across
physical orders, and whether that order sensitivity changes at 1, 2, or 4
workers. Timing is descriptive only. The configured identity-order file and
the nine selected permutations form a serialization-controlled comparison.
For Q3, rank fidelity among visible states, recovery of the final top five,
and state-domain coverage are reported separately rather than collapsed into
a single visual-fidelity time.
