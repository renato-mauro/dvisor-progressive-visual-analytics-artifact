// Translates the three illustrative queries in the paper draft
// (anotacoes/draft/paperdraft.tex, section "Analytical Tasks and Queries")
// into SQL that actually runs against the real, Portuguese-named SINASC
// columns dvisor exposes. The paper's own Table~1 (schema-map) defines this
// exact mapping (birth_date -> DTNASC, birth_weight -> PESO, maternal_age ->
// IDADEMAE, delivery_type -> PARTO, state -> UF, "derived/normalized" from
// CODMUNRES) — this file only performs that substitution and the minimal
// syntactic changes needed to make each query valid dvisor SQL. It does not
// add filters, thresholds, or logic the paper doesn't specify.
//
// Three substitutions were necessary beyond the schema-map renaming:
//
// 1. `yearMonth(...)` (paper's Q1) does not exist in dvisor's api.js (only
//    year/month/dateTruncMonth/...). Since Q1 already restricts
//    `WHERE year(DTNASC) = TARGET_YEAR`, a plain `month(DTNASC)` (1-12) is
//    an unambiguous grouping key with the same meaning within that filtered
//    year — the same substitution already used and documented on the
//    dvisor-site convergencia page.
// 2. `COUNT(*)` is used verbatim — supported as of this project's SQL
//    compiler update (2026-09-19), so no substitution was needed here.
// 3. `GROUP BY <alias>` (paper's Q2 and Q3, e.g. `GROUP BY maternal_age`,
//    `GROUP BY state`) is not valid dvisor SQL: GROUP BY must match the
//    projection's underlying EXPRESSION, not its alias. Q2's grouping key
//    is a bare physical column (`IDADEMAE`), so it's simply repeated. Q3's
//    is a derived expression (`floor(CODMUNRES/10000)`, since SINASC has no
//    standalone UF column — see consultas.md section 3.8) — there,
//    `GROUP BY 1` (the 1-based ordinal-position syntax added alongside
//    COUNT(*) support) is used instead of repeating the expression, exactly
//    the use case that feature was added for.
//
// No PESO>=500 / PARTO<9 data-quality filters are added here even though
// they're used elsewhere on this site (e.g. consultas.md, the SINASC
// Explorer catalog) — the paper's Methods section does not specify them for
// these three queries, and this experiment is built to match that text
// exactly, not to extend it. See README.md's "Deviations from the paper's
// illustrative SQL" section for the full, itemized list of substitutions
// and their justification.

export function buildQ1Sql(fromUrl, targetYear) {
    return `SELECT
    month(DTNASC) AS month,
    SUM(iif(PESO < 2500, 1, 0)) AS low_weight_births,
    COUNT(*) AS total_births
FROM '${fromUrl}'
WHERE year(DTNASC) = ${targetYear}
GROUP BY month(DTNASC)
ORDER BY month`;
}

export function buildQ2Sql(fromUrl) {
    return `SELECT
    IDADEMAE AS maternal_age,
    SUM(iif(PESO < 2500, 1, 0)) AS low_weight_births,
    COUNT(*) AS total_births
FROM '${fromUrl}'
GROUP BY IDADEMAE
ORDER BY maternal_age`;
}

export function buildQ3Sql(fromUrl, cesareanCode) {
    return `SELECT
    floor(CODMUNRES/10000) AS state,
    SUM(iif(PARTO = ${cesareanCode}, 1, 0)) AS cesarean_births,
    COUNT(*) AS total_births
FROM '${fromUrl}'
GROUP BY 1`;
}

export function buildQueries(config) {
    return [
        { query_id: 'Q1', title: 'Monthly low-birth-weight rate', sql: buildQ1Sql(config.dataset_url, config.target_year) },
        { query_id: 'Q2', title: 'Maternal-age distribution among low-birth-weight births', sql: buildQ2Sql(config.dataset_url) },
        { query_id: 'Q3', title: 'Cesarean-delivery rate by state over the full period', sql: buildQ3Sql(config.dataset_url, config.cesarean_code) },
    ];
}
