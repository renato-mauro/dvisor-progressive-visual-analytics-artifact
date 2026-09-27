# Reprocessing and recollection guide

## Current canonical traces

Q1 covers 2018. Q2 and Q3 cover the complete 2012--2021 dataset. The current
Q3 formulation replaced the pilot single-year query so that every state can
be updated by successive annual fragments. The released Phase-1 collection
contains the reported full-period Q3 traces.

For changes limited to thresholds, metrics, tables, figures, or prose, reuse
the existing canonical traces. Every query contains `COUNT(*) AS
total_births`, and every retained frame contains the complete cumulative
result. The analysis can therefore recover exact row progress without
changing `output/raw/`.

1. Confirm the query periods in `config/experiment.json`:

   - Q1 uses `target_year` as both period endpoints.
   - Q2 and Q3 use `dataset_period.start_year` through
     `dataset_period.end_year`.

2. Keep `output/raw/` and `output/metadata/` unchanged.

3. Activate the experiment environment and rebuild all derived artifacts:

   ```bash
   source .venv/bin/activate
   python analysis/build_all.py
   ```

4. Check the regenerated files:

   - `output/derived/Q1_frames.csv`
   - `output/derived/Q2_frames.csv`
   - `output/derived/Q3_frames.csv`
   - `output/derived/*_summary.csv`
   - `output/tables/main_results.csv`
   - `output/tables/milestones.csv`
   - `output/tables/fidelity_sensitivity.csv`
   - `output/tables/q2_nmae_sensitivity.csv`
   - `output/figures/`

5. Validate the following invariants for every run:

   - `processed_row_fraction` is monotonic.
   - The final `processed_row_fraction` equals 1.
   - Q1 uses 2,944,932 rows from 2018.
   - Q2 and Q3 use 28,789,402 rows from 2012 through 2021.
   - Intermediate Q3 aggregates differ from their final values before the
     last annual contribution for each state.
   - `fragment_fraction` retains the historical fragment-count ratio.
   - Q2 `numerical_error` equals `compositional_nmae`.
   - Q2 raw-count error is reported only as a completeness diagnostic.

## When a new browser collection is necessary

Collect again only if the dataset, SQL, data-cleaning rules, DVISOR execution
logic, or available fields in the raw frames change. A new collection is not
needed for threshold changes or alternative offline metrics.

Before collecting again, update `harness/run_experiment.mjs` so that new logs
do not use an ambiguous progress name:

1. Record the completed-fragment ratio as `fragment_fraction`.
2. For each frame, sum `total_births` in the cumulative result and record it as
   `processed_rows`.
3. After the final frame, record `period_total_rows` and backfill
   `processed_row_fraction = processed_rows / period_total_rows`.
4. Record `period_start_year` and `period_end_year` in run metadata.
5. If a future query does not expose `COUNT(*)`, instrument the engine to log
   the row-group identifier and qualifying row count for each completed
   fragment. Do not infer row progress from fragment count or transferred
   bytes.
6. Write the new collection to a versioned output directory or archive the
   existing `output/raw/` and `output/metadata/` first. Never overwrite the
   canonical traces without retaining a recoverable copy.

Then run:

```bash
node harness/run_experiment.mjs
source .venv/bin/activate
python analysis/build_all.py
```

Finally, repeat the invariant checks above and update every number, table,
figure, and statement in the manuscript from the regenerated outputs.
