# Maintainer checklist for the unified Zenodo artifact

This document is for the repository maintainers who assemble and publish the
archival record. Researchers reproducing the experiment should follow the root
[`README.md`](README.md) instead.

## Reserved record

- DOI: [`10.5281/zenodo.22983790`](https://doi.org/10.5281/zenodo.22983790)
- Resource type: **Dataset**
- Version: `1.0.0`
- Visibility: **Public**
- Title: **Intermediate-View Fidelity in Progressive Visual Analytics: Task
  and Order Effects in Public-Health Data — Experimental Data and
  Reproduction Artifact**
- Licenses: **CC BY 4.0** for research data, results, figures, and
  documentation; **Apache-2.0** for the software snapshot.

Use one record for the complete artifact. Do not enable the automatic
GitHub--Zenodo release integration, because that would create a second Zenodo
record and DOI.

## Files for the single record

Upload these small artifact packages:

- `release/experimental-observations-v1.0.0.zip`;
- `release/experimental-observations-v1.0.0.zip.sha256`;
- the GitHub `v1.0.0` release **Source code (zip)** snapshot;
- a SHA-256 sidecar for the GitHub source snapshot;
- `sinasc-parquet-metadata-v1.0.0.zip`, containing the ten metadata sidecars,
  permutation manifest, data README, checksum manifest, attribution, and data
  license.

Upload the ten large Parquet inputs as separate files:

- `SINASC-2012-2021.parquet`;
- `SINASC-2012-2021-shuf01.parquet` through
  `SINASC-2012-2021-shuf09.parquet`.

Do not upload `shuf10`: it was generated but was not used in the fixed
experimental design.

The ten Parquet files plus sidecars total 9,233,985,565 bytes (approximately
8.60 GiB), within Zenodo's standard record limits. Keeping each Parquet as a
separate file lets readers download only the inputs they need and makes failed
uploads easier to resume.

## Experimental-observation package

Run from the repository root:

```bash
python scripts/package_zenodo_results.py
```

This creates `release/experimental-observations-v1.0.0.zip`, its external
`.zip.sha256` sidecar, and an internal `SHA256SUMS` manifest. The archive
contains the 123 query traces, per-run metadata, configurations, validations,
derived metrics, tables, figures, provenance, README, data license, and
DATASUS attribution notice.

Do not omit the three Phase-1 warm-up traces. They are excluded analytically
but form part of the complete collection record.

## Versioned source snapshot from GitHub

1. Incorporate the reserved Zenodo DOI in the repository documentation.
2. Publish the repository on GitHub.
3. Create tag and release `v1.0.0` from the exact commit being archived.
4. On the GitHub release page, download **Source code (zip)**.
5. Compute a SHA-256 checksum for that ZIP and create a matching `.sha256`
   sidecar.
6. Upload both files manually to this same Zenodo record.

Do not use the Zenodo GitHub integration for this release. The manually
uploaded GitHub snapshot preserves the exact source version without creating
a separate software publication.

## Input-data metadata package

Package the following small files as `sinasc-parquet-metadata-v1.0.0.zip`:

- `SINASC-2012-2021.meta.json`;
- `SINASC-2012-2021-shuf01.meta.json` through `-shuf09.meta.json`;
- `SINASC-2012-2021-shuffles.json`;
- `SHA256SUMS` covering the ten uploaded Parquets and the metadata files;
- a data README explaining that only row-group order changes;
- `DATASUS-ATTRIBUTION.md`;
- `LICENSE-DATA.md`.

The checksum list must be computed from the exact local files uploaded to
Zenodo. Do not infer Parquet SHA-256 values solely from GCP HTTP metadata.

## Description and source credit

Begin the Zenodo description with this visible credit:

> **Primary data source:** Sistema de Informações sobre Nascidos Vivos
> (SINASC), 2012--2021, Brazilian Ministry of Health, disseminated by DATASUS
> through the SUS Open Data Portal. The deposited Parquet files and
> experimental outputs are research derivatives, not official DATASUS
> distributions, and do not imply institutional endorsement.

Link “SUS Open Data Portal” to the official SINASC dataset record. Use the
complete unified description prepared for the deposit and retain
`DATASUS-ATTRIBUTION.md` inside the metadata package and experimental archive.

## Final publication sequence

1. Keep the reserved Zenodo record as a draft.
2. Publish the DOI-updated repository on GitHub.
3. Create GitHub release `v1.0.0` and download its source ZIP.
4. Regenerate the experimental-observation ZIP from that same repository
   version.
5. Assemble the input-data metadata ZIP and compute all checksums.
6. Upload the ten Parquets and all small packages to the single Zenodo draft.
7. Wait until every file has completed uploading and no item is pending.
8. Verify the uploaded files against the local checksum manifests.
9. Confirm title, creator order, ORCIDs, affiliations, version, licenses,
   public visibility, description, keywords, and source credit.
10. Preview the record and test every displayed link.
11. Publish the Zenodo record.
12. Confirm that <https://doi.org/10.5281/zenodo.22983790> resolves publicly
    and that individual files download without authentication.
13. When the article DOI becomes available, add it to the Zenodo metadata as
    **Is supplement to** and update the repository citation metadata.

For later file changes, create a new Zenodo version rather than silently
replacing the published artifact. Metadata may be corrected without changing
the archived files.

Official references: [file and quota limits](https://help.zenodo.org/docs/deposit/manage-files/),
[reserving a DOI](https://help.zenodo.org/docs/deposit/describe-records/reserve-doi/),
and [managing versions](https://help.zenodo.org/docs/deposit/manage-versions/).
