# Provenance and integrity record

Archived artifact DOI: <https://doi.org/10.5281/zenodo.22983790>

## Authoritative upstream source

The underlying records originate from the **Sistema de Informações sobre
Nascidos Vivos (SINASC)**, Brazilian Ministry of Health, and are disseminated
by **DATASUS** through the
[SUS Open Data Portal](https://dadosabertos.saude.gov.br/dataset/sistema-de-informacao-sobre-nascidos-vivos-sinasc).
The official dataset record declares the upstream license as Creative Commons
Attribution (`cc-by`). The Parquet files, permutations, and experimental
outputs are research derivatives and are not official DATASUS distributions.
See [`DATASUS-ATTRIBUTION.md`](DATASUS-ATTRIBUTION.md) for the full credit and
no-endorsement statement.

## Shared identity-order dataset

- URL: `https://storage.googleapis.com/dvisor/SINASC-2012-2021.parquet`
- rows: `28,789,402`
- row groups: `270`
- bytes: `917,760,169`
- SHA-256: `11ed73f53fa129c88d72440f8e0250bcbc1b6cba34955ac0de9805763f892327`
- GCS generation observed by Phase 2: `1790437729065157`
- GCS MD5 (base64): `a6A3MWK9OvA42vgCXRLpAA==`

Phase 1 computed the SHA-256 digest over the complete object before
collection. Phase 2 recorded the GCS object identity and validated its sidecar
metadata before running. The byte length is identical in both records.

## Cross-phase final-result identity

Final rows are canonicalized by sorting object keys, sorting rows by their
canonical JSON representation, and hashing the resulting JSON with SHA-256.
All Phase-1 measured runs and all 90 Phase-2 runs produce these hashes:

| Query | SHA-256 |
|---|---|
| Q1 | `2146ca26628b052ddd0aa172dd2fce394b10bda7289457f6f0b3db00fcbfd565` |
| Q2 | `aae1a5399786972f0d16ffe85281d589dc9700ee396412648946cd2e62e863a4` |
| Q3 | `0b55b588d9c52c6ba40f1306a603dd827171684d711b77c30fe025a7eaf94c02` |

This validates that the order and thread-count interventions change only the
trajectory of intermediate results, not the final answer.

## Permutation provenance

Phase 2 uses the identity order plus `shuf01` through `shuf09`. The generated
`shuf10` is deliberately excluded from the fixed design. Seeds, complete
row-group sequences, and sequence digests are recorded in
`phases/02-order-sensitivity/config/SINASC-2012-2021-shuffles.json` and the
phase configuration. The remote-object audit is retained in
`phases/02-order-sensitivity/PROVENANCE_AUDIT.md`.
