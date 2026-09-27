# DATASUS / SINASC source attribution

## Authoritative source

The underlying records used in this research originate from:

> **Sistema de Informações sobre Nascidos Vivos (SINASC), 2012--2021.**  
> Brazilian Ministry of Health; responsible area identified in the official
> record as CGIAE/DASNT/SVS; disseminated by DATASUS through the SUS Open
> Data Portal.  
> <https://dadosabertos.saude.gov.br/dataset/sistema-de-informacao-sobre-nascidos-vivos-sinasc>

The structured metadata embedded in the official dataset record (checked on
2026-09-26) describes nationwide coverage and declares the dataset license as
**Creative Commons Attribution**, identifier `cc-by`. The portal-wide footer
separately labels the editorial content of the website as CC BY-ND 3.0; that
site-content notice is not the dataset-specific license field. If the source
publisher later corrects or replaces the dataset terms, the then-applicable
upstream terms prevail for the source records.

## Transformations performed by the research team

The authors converted and integrated the public annual records into an
analytical Parquet representation covering 2012--2021. The experimental
family contains one identity-order file and nine files in which only the
order of the same 270 state-by-year row groups was permuted. No record was
reordered within a row group for the order-sensitivity intervention.

These Parquet files are research derivatives, not official DATASUS
distributions. DATASUS and the Brazilian Ministry of Health did not produce,
validate, or endorse the conversions, row-group permutations, metrics,
figures, or interpretations.

## Suggested attribution for reuse

When reusing the Parquet inputs or any data-derived artifact, retain both
credits:

> Source data: Sistema de Informações sobre Nascidos Vivos (SINASC),
> Brazilian Ministry of Health/DATASUS, 2012--2021, licensed as Creative
> Commons Attribution (`cc-by`). Research transformations and experimental
> packaging: Mauro, Ogasawara, and Esperança (2026), *Progressive
> Intermediate-View Fidelity Experiments with DVISOR*, CC BY 4.0,
> <https://doi.org/10.5281/zenodo.22983790>.

Once assigned, also append the DOI of the associated article.
