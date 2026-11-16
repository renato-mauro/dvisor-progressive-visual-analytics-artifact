#!/usr/bin/env bash
# Extracts per-row-group contributions for Q1, Q2 and Q3 from the identity-order
# Parquet with DuckDB, independently of DVISOR. Each of the 270 row groups holds
# one federative unit (UF of residence) and one birth year.
#
# Usage: ./extract_blocks.sh /path/to/SINASC-2012-2021.parquet
# Expected SHA-256 of the input:
#   11ed73f53fa129c88d72440f8e0250bcbc1b6cba34955ac0de9805763f892327
set -euo pipefail
P="${1:?path to SINASC-2012-2021.parquet}"
OUT="$(cd "$(dirname "$0")" && pwd)/blocks"
mkdir -p "$OUT"
duckdb <<SQL
CREATE TEMP TABLE rg AS
  WITH g AS (SELECT row_group_id AS rg, min(row_group_num_rows) AS n
             FROM parquet_metadata('$P') GROUP BY 1)
  SELECT rg, n, sum(n) OVER (ORDER BY rg) - n AS start_row FROM g;
CREATE TEMP TABLE r AS
  SELECT g.rg, floor(CODMUNRES/10000)::int AS uf, year(DTNASC) AS y, month(DTNASC) AS m,
         PESO, IDADEMAE, PARTO
  FROM read_parquet('$P', file_row_number=true) t
  ASOF JOIN rg g ON t.file_row_number >= g.start_row;

-- One row per row group. Fails the homogeneity check if a row group mixes UFs or years.
COPY (SELECT rg, min(uf) AS uf, min(y) AS "year",
             count(DISTINCT uf) AS n_uf, count(DISTINCT y) AS n_year,
             count(*) AS total_births,
             sum((PARTO=2)::int) AS cesarean_births,
             sum((PARTO=9)::int) AS ignored_delivery,
             sum((PESO<2500)::int) AS low_weight_births,
             sum((PESO<500)::int) AS weight_lt500,
             sum((PESO=0)::int) AS weight_zero,
             sum((PESO>=9000)::int) AS weight_ge9000
      FROM r GROUP BY rg ORDER BY rg) TO '$OUT/blocks.csv' (HEADER);
COPY (SELECT rg, y AS "year", m AS "month", count(*) AS total_births,
             sum((PESO<2500)::int) AS low_weight_births,
             sum((PESO>=500)::int) AS total_ge500,
             sum((PESO>=500 AND PESO<2500)::int) AS low_weight_ge500
      FROM r GROUP BY rg, y, m ORDER BY rg, y, m) TO '$OUT/blocks_month.csv' (HEADER);
COPY (SELECT rg, IDADEMAE AS maternal_age, count(*) AS total_births,
             sum((PESO<2500)::int) AS low_weight_births,
             sum((PESO>=500)::int) AS total_ge500,
             sum((PESO>=500 AND PESO<2500)::int) AS low_weight_ge500
      FROM r GROUP BY rg, IDADEMAE ORDER BY rg, IDADEMAE) TO '$OUT/blocks_age.csv' (HEADER);

-- Independent final results of the three queries (same SQL semantics as the paper).
COPY (SELECT month(DTNASC) AS "month", SUM(CASE WHEN PESO < 2500 THEN 1 ELSE 0 END) AS low_weight_births,
             COUNT(*) AS total_births
      FROM '$P' WHERE year(DTNASC) = 2018 GROUP BY 1 ORDER BY 1) TO '$OUT/duckdb_final_q1.csv' (HEADER);
COPY (SELECT IDADEMAE AS maternal_age, SUM(CASE WHEN PESO < 2500 THEN 1 ELSE 0 END) AS low_weight_births,
             COUNT(*) AS total_births
      FROM '$P' GROUP BY 1 ORDER BY 1) TO '$OUT/duckdb_final_q2.csv' (HEADER);
COPY (SELECT floor(CODMUNRES/10000)::int AS state, SUM(CASE WHEN PARTO = 2 THEN 1 ELSE 0 END) AS cesarean_births,
             COUNT(*) AS total_births
      FROM '$P' GROUP BY 1 ORDER BY 1) TO '$OUT/duckdb_final_q3.csv' (HEADER);
-- Value-domain profile of the columns used by the queries.
COPY (SELECT count(*) AS n_rows,
             count(*) - count(DTNASC) AS null_dtnasc, count(*) - count(PESO) AS null_peso,
             count(*) - count(IDADEMAE) AS null_idademae, count(*) - count(PARTO) AS null_parto,
             count(*) - count(CODMUNRES) AS null_codmunres,
             sum((PESO=0)::int) AS weight_zero, sum((PESO<500)::int) AS weight_lt500,
             sum((PESO<2500)::int) AS weight_lt2500, sum((PESO>=9000)::int) AS weight_ge9000,
             sum((PARTO=1)::int) AS parto_1, sum((PARTO=2)::int) AS parto_2, sum((PARTO=9)::int) AS parto_9,
             sum((PARTO NOT IN (1,2,9))::int) AS parto_other,
             sum((IDADEMAE<10)::int) AS age_lt10, sum((IDADEMAE>55)::int) AS age_gt55
      FROM '$P') TO '$OUT/column_profile.csv' (HEADER);
SQL
duckdb --version > "$OUT/duckdb_version.txt"
echo "wrote $OUT"
