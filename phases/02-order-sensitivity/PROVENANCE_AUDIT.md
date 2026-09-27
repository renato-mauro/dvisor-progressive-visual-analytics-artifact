# Parquet provenance and integrity audit

Audit completed on 2026-09-26 before experimental collection. No analytical
query was executed during this audit.

## Serialization controls

The updated identity-order file and every shuffled file have:

- 28,789,402 rows;
- 270 row groups;
- writer `parquet-cpp-arrow 25.0.1`;
- Parquet format version 2;
- `SNAPPY` compression;
- reported encodings `PLAIN, RLE, RLE_DICTIONARY`;
- 916,012,356 aggregate compressed-column bytes;
- 986,962,294 aggregate uncompressed-column bytes.

For every `shuf01` through `shuf10`, each output row group's metadata is
identical to the row group selected by the supplied permutation vector after
excluding only its physical byte offset. This comparison includes row count,
column names, internal/preferred types, and encoded lengths. Thus the new
identity-order file is a serialization-controlled baseline for the shuffled
family.

The superseded historical Parquet, produced by `parquet-rs`, is preserved
locally as `SINASC-2012-2021.old.parquet` and is not used by this experiment.

## GCP upload integrity

The configured ten-dataset matrix (`original` plus `shuf01` through
`shuf09`) passed the collector's remote preflight:

- every Parquet and `.meta.json` sidecar returned HTTP 200;
- every sidecar parsed successfully and reported 270 row groups and
  28,789,402 rows;
- the CRC32C of every remote Parquet matched its local source file;
- the MD5 of every remote sidecar matched its local source file.

For the updated identity-order objects specifically:

| object | bytes | checksum |
|---|---:|---|
| `SINASC-2012-2021.parquet` | 917,760,169 | MD5 `6ba0373162bd3af038daf8025d12e900` |
| `SINASC-2012-2021.meta.json` | 5,634,490 | MD5 `41ae8ae4ed13ab9153a3fca6ea4fdd81` |

The remote identity-order objects match the newly generated local files and
are safe to use in the configured experiment.
