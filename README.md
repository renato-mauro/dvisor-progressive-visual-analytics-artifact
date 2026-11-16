[![DOI](https://zenodo.org/badge/1459909832.svg)](https://doi.org/10.5281/zenodo.24279709)

# Progressive intermediate-view experiments with DVISOR

## TL;DR

- Explore the [DVISOR website](https://dvisor.io/) and the
  [progressive convergence visualization demo](https://dvisor.io/convergencia/).
- Rebuild both phase analyses from the archived browser traces with
  `python scripts/validate_artifact.py` and `python scripts/build_all.py`.
- Run the browser experiments against the DVISOR-hosted Parquets by following
  [Recollecting browser traces](#recollecting-browser-traces).

The offline rebuild uses Python and the original traces. If the traces are
missing, use the original observation ZIP. Place
`experimental-observations-v1.0.0.zip` under `release/` before extracting
its raw traces and metadata from the repository root.

```bash
unzip -n release/experimental-observations-v1.0.0.zip 'phases/*/output/raw/*' 'phases/*/output/metadata/*'
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/validate_artifact.py
python scripts/build_all.py
```

Validation checks 33 Phase-1 traces, 90 Phase-2 traces, and the final result
hashes across both phases. The offline rebuild requires no Parquet downloads.

This repository is the computational artifact for the study
*Intermediate-View Fidelity in Progressive Visual Analytics: Task and Order
Effects in Public-Health Data*. The independent full-period Q3 check is
documented in [diagnostics](diagnostics/q3-full-period-2026-11-15/README.md).

## Primary data source: Brazilian Ministry of Health / DATASUS / SINASC

This research is built on public microdata from the **Sistema de Informações
sobre Nascidos Vivos (SINASC)**, produced by the **Brazilian Ministry of
Health** and disseminated by **DATASUS** through the
[SUS Open Data Portal](https://dadosabertos.saude.gov.br/dataset/sistema-de-informacao-sobre-nascidos-vivos-sinasc).
The official dataset record declares the source license as **Creative Commons
Attribution (`cc-by`)**.

DATASUS and the Ministry of Health are the authoritative sources of the
underlying records. The Parquet organization, row-group permutations,
experimental traces, metrics, and interpretations in this artifact were
produced by the research authors and do not imply endorsement by DATASUS or
the Ministry of Health. See [`DATASUS-ATTRIBUTION.md`](DATASUS-ATTRIBUTION.md)
for the required provenance statement and suggested citation text.

## Experimental design

| Phase | Purpose | Datasets | Threads | Executions |
|---|---|---:|---:|---:|
| `01-fixed-order` | Repeated characterization of three progressive tasks | identity order | 4 | 3 warm-ups + 30 measured |
| `02-order-sensitivity` | Controlled test of physical row-group order and concurrency | identity + 9 permutations | 1, 2, 4 | 90 measured |

Both phases use the same serialization-controlled identity-order Parquet file
as their canonical input. Phase 1 was recollected after that file was
published, while retaining its original query definitions, four-worker
policy, one warm-up, and ten measured runs per query. Phase 2 changes only
row-group order across the nine permutations; rows are unchanged within each
row group.

The shared identity dataset contains 28,789,402 rows in 270 row groups and is
917,760,169 bytes. Its SHA-256 digest is:

```text
11ed73f53fa129c88d72440f8e0250bcbc1b6cba34955ac0de9805763f892327
```

The final result of every execution is identical within each query and across
both phases. See [`PROVENANCE.md`](PROVENANCE.md) for the exact result hashes.

## Repository layout

```text
phases/
  01-fixed-order/          repeated identity-order characterization
  02-order-sensitivity/    identity-versus-permutation experiment
scripts/
  build_all.py             rebuild both offline analyses
  validate_artifact.py     validate both collections and cross-phase identity
```

Each phase contains its own `config/`, browser `harness/`, Python `analysis/`,
and `output/` tree. The phase-specific READMEs document the metric definitions,
collection protocol, output schema, and scoped reproduction commands.

## Rebuilding the analysis

The raw traces are immutable observations. All metrics, tables, and figures
are derived offline and can be rebuilt without rerunning a query. If the
`output/raw/` directories are absent from a fresh Git clone, restore them from
`experimental-observations-v1.0.0.zip` as described in the [TL;DR](#tldr).

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/validate_artifact.py
python scripts/build_all.py
```

The validator checks the 33 Phase-1 traces, the complete 90-run Phase-2
matrix, monotonic progress, final-frame completeness, and cross-phase final
result hashes.

## Recollecting browser traces

Run a fresh collection in a checkout with empty `output/raw/` and
`output/metadata/` directories for both phases. Recollection requires Node.js,
Playwright, Chromium, and access to the Parquets and sidecars on
`data.dvisor.io`.

```bash
npm ci
npx playwright install chromium
npm run collect:phase1
npm run plan:phase2
npm run preflight:phase2
npm run collect:phase2
```

Phase 2 can resume an interrupted collection by skipping complete runs.
Recollection can change elapsed times and concurrent completion order.
The archived traces are the evidence for the results reported in the article.

## Data availability and archival organization

The [versioned source release on GitHub](https://github.com/renato-mauro/dvisor-progressive-visual-analytics-artifact/releases/tag/v1.0.0)
provides the experiment code. The observation archive can be distributed as
a release asset. See [ZENODO.md](ZENODO.md) for archiving the source release
and obtaining its DOI.

DVISOR hosts the ten experimental Parquets and their sidecars under
`https://data.dvisor.io/data/datasus/`. Start with the
[canonical Parquet](https://data.dvisor.io/data/datasus/SINASC-2012-2021.parquet) or its
[metadata](https://data.dvisor.io/data/datasus/SINASC-2012-2021.meta.json).
The [Phase-2 configuration](phases/02-order-sensitivity/config/experiment.json)
lists the direct addresses for all nine permutations (`shuf01` through `shuf09`).
File fingerprints and row-group provenance are documented in
[PROVENANCE.md](PROVENANCE.md) and the
[original upload audit](phases/02-order-sensitivity/PROVENANCE_AUDIT.md).

## Licensing and citation

This is a deliberately permissive, attribution-preserving release:

- software source code and executable instrumentation: **Apache License 2.0**
  ([`LICENSE`](LICENSE) and [`NOTICE`](NOTICE));
- research-authored observations, metadata, tables, figures, reports, and
  documentation: **Creative Commons Attribution 4.0 International**
  ([`LICENSE-DATA.md`](LICENSE-DATA.md));
- the underlying SINASC records retain the original **Creative Commons
  Attribution (`cc-by`)** terms declared by the Ministry of Health/DATASUS.
  The authors' transformations and arrangements are offered under CC BY 4.0
  to the extent that the authors hold rights in them.

Both licenses permit commercial and non-commercial reuse, modification, and
redistribution. Attribution and preservation of the applicable notices are
required. Citation metadata are provided in [`CITATION.cff`](CITATION.cff).
Cite the [versioned GitHub release](https://github.com/renato-mauro/dvisor-progressive-visual-analytics-artifact/releases/tag/v1.0.0).
