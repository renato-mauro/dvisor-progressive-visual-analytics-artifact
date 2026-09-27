# Progressive intermediate-view experiments with DVISOR

**Primary public-data source:** [Sistema de Informações sobre Nascidos Vivos
(SINASC), Brazilian Ministry of Health / DATASUS](https://dadosabertos.saude.gov.br/dataset/sistema-de-informacao-sobre-nascidos-vivos-sinasc).

**Archived artifact:** [https://doi.org/10.5281/zenodo.22983790](https://doi.org/10.5281/zenodo.22983790)

This repository is the integrated computational artifact for the study
*Intermediate-View Fidelity in Progressive Visual Analytics: Task and Order
Effects in Public-Health Data*. It preserves the two phases of the study in a
single versioned repository while keeping their protocols and outputs
separate.

## TL;DR: reproduce the reported analysis

The shortest reproduction path rebuilds every metric, table, and figure from
the archived raw traces. It does **not** rerun DVISOR and does not download the
8.60 GiB Parquet inputs.

1. Obtain this repository and download `experimental-observations-v1.0.0.zip`
   from the [complete artifact record on Zenodo](https://doi.org/10.5281/zenodo.22983790).
2. Extract that archive at the repository root. The archive restores the
   ignored `output/raw/` and `output/metadata/` trees for both phases.
3. From the repository root, run:

```bash
unzip -o /path/to/experimental-observations-v1.0.0.zip -d .
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/validate_artifact.py
python scripts/build_all.py
```

A successful validation finds 33 Phase-1 traces, all 90 Phase-2 measured
runs, identical final query results across phases, and the expected identity
dataset fingerprint. Rebuilt products are written below each phase's
`output/{derived,tables,figures}/` directories.

Full recollection is optional and substantially more expensive. It requires
Node.js, Playwright/Chromium, network access, and the hosted Parquet inputs;
see [Recollecting browser traces](#recollecting-browser-traces).

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
the matching Zenodo artifact archive as described in the
[TL;DR](#tldr-reproduce-the-reported-analysis).

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

Recollection requires Node.js, Playwright, Chromium, and network access to the
hosted Parquet files.

```bash
npm install
npx playwright install chromium
npm run collect:phase1
npm run plan:phase2
npm run preflight:phase2
npm run collect:phase2
```

Collectors are resumable and never silently replace a half-written run.
Recollection can change elapsed times and concurrent completion order; the
archived raw traces remain the canonical evidence for the published results.

## Data availability and archival organization

The complete artifact is preserved in a single
[Zenodo record](https://doi.org/10.5281/zenodo.22983790). It contains the
versioned source snapshot, canonical query traces, per-run metadata, derived
outputs, and the ten exact Parquet inputs: the identity order plus `shuf01`
through `shuf09`. The unused `shuf10` is not part of the experiment.

Zenodo permits individual file downloads. Readers who only want to rebuild
the offline analysis can therefore download the source snapshot and
`experimental-observations-v1.0.0.zip` without downloading the approximately
8.60 GiB of Parquet inputs. Exact object identities, hashes, row counts, and
row-group provenance are recorded in [`PROVENANCE.md`](PROVENANCE.md) and
[`phases/02-order-sensitivity/PROVENANCE_AUDIT.md`](phases/02-order-sensitivity/PROVENANCE_AUDIT.md).

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
The complete artifact is citable as
[doi:10.5281/zenodo.22983790](https://doi.org/10.5281/zenodo.22983790).
