# Supplementary offline analyses

Analyses added in response to peer review. They read the archived traces of
both phases and never execute a query. The per-frame metric definitions are
imported unchanged from `phases/02-order-sensitivity/analysis`, so every
number here uses the same code as the official tables.

## What is computed

| Script | Purpose |
|---|---|
| `extract_blocks.sh` | Extracts, with DuckDB, the contribution of each of the 270 row groups to Q1, Q2 and Q3, the final result of each query, and the value domains of the query columns. Verifies that every row group holds one state and one year. |
| `validate.py` | Checks that the DuckDB final results equal the final frame of every DVISOR execution, and that a logical one-worker merge of the row-group contributions reproduces every frame of the 30 executed one-worker traces. |
| `revision_analyses.py` | Events with confirmation frame, later violations and hold point; dispersion across orders; paired differences between worker counts; presence of the final Top-5 states versus observed Top-5 overlap; the deterministic year-state order; 1,000 simulated row-group permutations; joint threshold and persistence sensitivity; Q1 for every year; weight and delivery-code variants. |
| `make_figures.py` | Figures 1 to 4 of the article. |
| `make_tex_tables.py` | LaTeX table bodies of the article and its supplement. |

## Reproduction

From this directory, with the traces of both phases restored and the
repository requirements installed:

```bash
python validate.py
python revision_analyses.py
python make_figures.py
python make_tex_tables.py /path/to/paper/tables
```

The outputs of `extract_blocks.sh` are stored in `blocks/`, so DuckDB and the
Parquet file are needed only to regenerate them:

```bash
./extract_blocks.sh /path/to/SINASC-2012-2021.parquet
```

Expected SHA-256 of the input:
`11ed73f53fa129c88d72440f8e0250bcbc1b6cba34955ac0de9805763f892327`.
The stored files were produced with DuckDB 1.5.0.

## Outputs

```text
blocks/blocks.csv            one row per row group (state, year, counts)
blocks/blocks_month.csv      monthly contributions per row group
blocks/blocks_age.csv        maternal-age contributions per row group
blocks/duckdb_final_q*.csv   final results computed by DuckDB
blocks/column_profile.csv    nulls and code counts of the query columns
output/validation.json       cross-engine and replay checks
output/summary.json          scalar facts quoted in the article
output/robustness.json       weight and delivery-code variants
output/*.csv                 tables behind the article and supplement
output/figures/              figures in PDF and PNG
```

## Conventions

- Positions are fractions of query-relevant rows.
- A value at a target fraction is taken from the first frame at or above it.
- `start` is the first frame of the first run of `k` consecutive satisfying
  frames, `confirm` the last frame of that run, and `hold` the first frame
  from which the criterion holds until completion.
- The simulated permutations use seed `20261115`.
