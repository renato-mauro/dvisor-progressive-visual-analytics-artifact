# Recollection and reprocessing checklist

## Before collection

1. Run `node harness/run_experiment.mjs --list-plan` and confirm 90 measured
   executions and zero warm-ups.
2. Run `node harness/run_experiment.mjs --preflight-only` after uploads finish.
3. Confirm that `shuf10` is absent from `config/experiment.json`.
4. Preserve the vendored DVISOR files and configuration used for collection.

## During collection

Run `node harness/run_experiment.mjs`. It is safe to stop between runs and
invoke the same command again; completed raw/metadata pairs are skipped.

Never delete or overwrite a single member of a raw/metadata pair without
first determining why it is incomplete.

## After collection

Run:

```bash
python analysis/build_all.py
```

The validator requires:

- exactly 90 configured measured runs;
- monotonic processed-row fractions ending at 1;
- 28,789,402 period rows for Q2 and Q3;
- consistent dataset/thread/query identities in trace and metadata;
- identical final-result hashes across physical orders and thread counts.

Threshold, persistence, table, or figure changes require only another
offline `build_all.py` run. A new browser collection is required only if the
dataset set, queries, DVISOR build, worker configurations, or raw trace schema
changes.
