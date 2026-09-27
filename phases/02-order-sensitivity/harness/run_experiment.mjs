// Collects the order-sensitivity experiment without touching the repeated
// fixed-order phase in ../01-fixed-order. The default matrix is:
//
//   10 datasets (original + shuf01..shuf09)
//   x 3 queries (Q1..Q3)
//   x 3 worker counts (1, 2, 4)
//   x 1 measured execution = 90 measured executions
//
// No warm-up is performed by default. The primary outcomes are fidelity,
// error, stability, and coverage over processed-row fraction; elapsed time is
// retained as contextual metadata rather than used for performance claims.
//
// The collector is resumable: a run with both its raw trace and metadata
// already present is skipped. A half-written run (only one artifact present)
// is treated as an error and must be inspected instead of silently replaced.

import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import http from 'node:http';
import { fileURLToPath } from 'node:url';
import { buildQueries } from './queries.mjs';

let chromium = null;

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const CONFIG_PATH = path.join(ROOT, 'config', 'experiment.json');
const OUTPUT = path.join(ROOT, 'output');

const CONTENT_TYPES = {
    '.html': 'text/html',
    '.js': 'text/javascript',
    '.wasm': 'application/wasm',
    '.mjs': 'text/javascript',
};

function startStaticServer(rootDir) {
    return new Promise((resolve) => {
        const server = http.createServer((req, res) => {
            const urlPath = decodeURIComponent(req.url.split('?')[0]);
            const filePath = path.join(rootDir, urlPath === '/' ? 'harness.html' : urlPath);
            if (!filePath.startsWith(rootDir)) {
                res.writeHead(403);
                res.end();
                return;
            }
            fs.readFile(filePath, (err, data) => {
                if (err) {
                    res.writeHead(404);
                    res.end();
                    return;
                }
                res.writeHead(200, {
                    'Content-Type': CONTENT_TYPES[path.extname(filePath)] || 'application/octet-stream',
                });
                res.end(data);
            });
        });
        server.listen(0, '127.0.0.1', () => resolve(server));
    });
}

function ensureDir(p) {
    fs.mkdirSync(p, { recursive: true });
}

function csvStrings(value) {
    return value.split(',').map((x) => x.trim()).filter(Boolean);
}

function csvIntegers(value, flag) {
    const values = csvStrings(value).map(Number);
    if (!values.length || values.some((x) => !Number.isInteger(x) || x <= 0)) {
        throw new Error(`${flag} expects a comma-separated list of positive integers`);
    }
    return values;
}

function parseArgs(argv) {
    const args = {
        queryIds: null,
        datasetIds: null,
        threadCounts: null,
        measuredRuns: null,
        warmupRuns: null,
        preflightOnly: false,
        listPlan: false,
    };
    for (const raw of argv.slice(2)) {
        if (raw === '--preflight-only') {
            args.preflightOnly = true;
            continue;
        }
        if (raw === '--list-plan') {
            args.listPlan = true;
            continue;
        }
        const arg = raw.replace(/^--/, '');
        const eq = arg.indexOf('=');
        const key = eq >= 0 ? arg.slice(0, eq) : arg;
        const value = eq >= 0 ? arg.slice(eq + 1) : '';
        if (key === 'query') args.queryIds = csvStrings(value);
        else if (key === 'dataset') args.datasetIds = csvStrings(value);
        else if (key === 'threads') args.threadCounts = csvIntegers(value, '--threads');
        else if (key === 'runs') args.measuredRuns = Number(value);
        else if (key === 'warmup') args.warmupRuns = Number(value);
        else throw new Error(`Unknown argument: ${raw}`);
    }
    for (const [flag, value] of [['--runs', args.measuredRuns], ['--warmup', args.warmupRuns]]) {
        if (value !== null && (!Number.isInteger(value) || value < 0)) {
            throw new Error(`${flag} expects a non-negative integer`);
        }
    }
    return args;
}

function loadAndValidateConfig() {
    const config = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf-8'));
    const manifestPath = path.resolve(ROOT, config.permutation_manifest);
    const manifestBytes = fs.readFileSync(manifestPath);
    const manifest = JSON.parse(manifestBytes.toString('utf-8'));

    if (!Array.isArray(config.datasets) || config.datasets.length !== 10) {
        throw new Error('The order-sensitivity configuration must contain exactly 10 datasets');
    }
    const ids = config.datasets.map((d) => d.id);
    if (new Set(ids).size !== ids.length) throw new Error('Dataset ids must be unique');
    const expectedIds = ['original', ...Array.from({ length: 9 }, (_, i) => `shuf${String(i + 1).padStart(2, '0')}`)];
    if (ids.length !== expectedIds.length || ids.some((id, index) => id !== expectedIds[index])) {
        throw new Error('Expected original + shuf01..shuf09; shuf10 must remain excluded');
    }
    if (JSON.stringify(config.thread_counts) !== JSON.stringify([1, 2, 4])) {
        throw new Error('The configured thread counts must be exactly [1, 2, 4]');
    }
    if (config.runs?.warmup_runs !== 0 || config.runs?.measured_runs !== 1) {
        throw new Error('The configured run policy must be zero warm-ups and one measured run per combination');
    }
    if (!Number.isInteger(config.execution_order_seed)) {
        throw new Error('execution_order_seed must be an integer');
    }
    if (manifest.num_row_groups !== config.expected_row_groups) {
        throw new Error('Manifest/config row-group count mismatch');
    }

    const manifestByFile = new Map(manifest.files.map((item) => [item.parquet, item]));
    const configuredManifestFiles = new Set();
    const orderHashes = new Set();
    for (const dataset of config.datasets) {
        const parquetUrl = new URL(dataset.url);
        const expectedMetadataPath = parquetUrl.pathname.replace(/\.parquet$/i, '.meta.json');
        if (expectedMetadataPath === parquetUrl.pathname) {
            throw new Error(`${dataset.id} URL does not end in .parquet`);
        }
        const expectedMetadataUrl = new URL(parquetUrl.href);
        expectedMetadataUrl.pathname = expectedMetadataPath;
        if (dataset.metadata_url !== expectedMetadataUrl.href) {
            throw new Error(
                `${dataset.id} metadata URL must match DVISOR's derived sidecar URL: ${expectedMetadataUrl.href}`,
            );
        }
        if (dataset.kind === 'canonical') continue;
        const item = manifestByFile.get(dataset.manifest_file);
        if (!item) throw new Error(`No manifest entry for ${dataset.id}`);
        if (item.seed !== dataset.seed) throw new Error(`Seed mismatch for ${dataset.id}`);
        if (configuredManifestFiles.has(dataset.manifest_file)) {
            throw new Error(`Manifest entry reused by ${dataset.id}`);
        }
        configuredManifestFiles.add(dataset.manifest_file);
        if (path.basename(parquetUrl.pathname) !== item.parquet) {
            throw new Error(`Parquet filename mismatch for ${dataset.id}`);
        }
        if (path.basename(expectedMetadataUrl.pathname) !== item.metadata) {
            throw new Error(`Metadata filename mismatch for ${dataset.id}`);
        }
        if (!Array.isArray(item.order) || item.order.length !== config.expected_row_groups) {
            throw new Error(`Invalid permutation length for ${dataset.id}`);
        }
        const expected = Array.from({ length: config.expected_row_groups }, (_, i) => i);
        const actual = [...item.order].sort((a, b) => a - b);
        if (actual.some((value, i) => value !== expected[i])) {
            throw new Error(`${dataset.id} is not a permutation of 0..${config.expected_row_groups - 1}`);
        }
        dataset.order_sha256 = crypto.createHash('sha256').update(JSON.stringify(item.order)).digest('hex');
        if (orderHashes.has(dataset.order_sha256)) throw new Error(`Duplicate permutation for ${dataset.id}`);
        orderHashes.add(dataset.order_sha256);
    }
    config.manifest_path = manifestPath;
    config.manifest_sha256 = crypto.createHash('sha256').update(manifestBytes).digest('hex');
    return config;
}

function filterSelected(items, selected, getter, label) {
    if (!selected) return items;
    const wanted = new Set(selected);
    const filtered = items.filter((item) => wanted.has(String(getter(item))));
    const found = new Set(filtered.map((item) => String(getter(item))));
    const missing = [...wanted].filter((value) => !found.has(value));
    if (missing.length) throw new Error(`Unknown ${label}: ${missing.join(', ')}`);
    return filtered;
}

function seededRandom(seed) {
    let state = seed >>> 0;
    return () => {
        state += 0x6D2B79F5;
        let value = state;
        value = Math.imul(value ^ (value >>> 15), value | 1);
        value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
        return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
    };
}

function shuffledCombinations(datasets, queryIds, threadCounts, seed) {
    const combinations = [];
    for (const dataset of datasets) {
        for (const threadCount of threadCounts) {
            for (const queryId of queryIds) combinations.push({ dataset, threadCount, queryId });
        }
    }
    const random = seededRandom(seed);
    for (let i = combinations.length - 1; i > 0; i--) {
        const j = Math.floor(random() * (i + 1));
        [combinations[i], combinations[j]] = [combinations[j], combinations[i]];
    }
    return combinations;
}

function responseHeaders(headers) {
    const names = [
        'content-length',
        'content-type',
        'etag',
        'last-modified',
        'accept-ranges',
        'x-goog-generation',
        'x-goog-hash',
        'x-goog-stored-content-length',
    ];
    return Object.fromEntries(names.map((name) => [name, headers.get(name)]).filter(([, value]) => value !== null));
}

async function probeUrl(url, label) {
    const response = await fetch(url, { method: 'HEAD', cache: 'no-store' });
    if (!response.ok) throw new Error(`${label} unavailable: HTTP ${response.status} ${url}`);
    return responseHeaders(response.headers);
}

async function validateRemoteMetadata(url, dataset, config) {
    const response = await fetch(url, { cache: 'no-store' });
    if (!response.ok) throw new Error(`${dataset.id} metadata unavailable: HTTP ${response.status} ${url}`);
    let metadata;
    try {
        metadata = await response.json();
    } catch (error) {
        throw new Error(`${dataset.id} metadata is not valid JSON: ${error.message ?? error}`);
    }
    if (Number(metadata.num_rows) !== config.expected_dataset_rows) {
        throw new Error(
            `${dataset.id} metadata num_rows=${metadata.num_rows}, expected ${config.expected_dataset_rows}`,
        );
    }
    if (!Array.isArray(metadata.row_groups) || metadata.row_groups.length !== config.expected_row_groups) {
        throw new Error(
            `${dataset.id} metadata row_groups=${metadata.row_groups?.length}, expected ${config.expected_row_groups}`,
        );
    }
    const rowGroupRows = metadata.row_groups.reduce((sum, group) => sum + Number(group.num_rows ?? 0), 0);
    if (rowGroupRows !== config.expected_dataset_rows) {
        throw new Error(
            `${dataset.id} row-group rows=${rowGroupRows}, expected ${config.expected_dataset_rows}`,
        );
    }
    return {
        num_rows: Number(metadata.num_rows),
        row_groups: metadata.row_groups.length,
        row_group_rows: rowGroupRows,
    };
}

async function preflightDataset(dataset, config) {
    const parquetHeaders = await probeUrl(dataset.url, `${dataset.id} Parquet`);
    const metadataHeaders = await probeUrl(dataset.metadata_url, `${dataset.id} metadata`);
    const metadataValidation = await validateRemoteMetadata(dataset.metadata_url, dataset, config);
    const info = {
        dataset_id: dataset.id,
        dataset_kind: dataset.kind,
        dataset_url: dataset.url,
        metadata_url: dataset.metadata_url,
        permutation_seed: dataset.seed,
        order_sha256: dataset.order_sha256 ?? null,
        permutation_manifest_sha256: config.manifest_sha256,
        expected_rows: config.expected_dataset_rows,
        expected_row_groups: config.expected_row_groups,
        parquet_headers: parquetHeaders,
        metadata_headers: metadataHeaders,
        metadata_validation: metadataValidation,
        checked_at: new Date().toISOString(),
    };
    const outDir = path.join(OUTPUT, 'datasets');
    ensureDir(outDir);
    fs.writeFileSync(path.join(outDir, `${dataset.id}.json`), JSON.stringify(info, null, 2));
    return info;
}

function resultTotalRows(result) {
    return result.reduce((sum, row) => sum + Number(row.total_births ?? 0), 0);
}

function canonicalResultHash(rows) {
    const normalized = rows.map((row) => {
        const obj = {};
        for (const key of Object.keys(row).sort()) obj[key] = row[key];
        return obj;
    });
    normalized.sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b)));
    return crypto.createHash('sha256').update(JSON.stringify(normalized)).digest('hex');
}

function runPaths(queryId, runId) {
    return {
        raw: path.join(OUTPUT, 'raw', queryId, `${runId}.jsonl`),
        metadata: path.join(OUTPUT, 'metadata', `${runId}.json`),
    };
}

function existingRunState(queryId, runId) {
    const paths = runPaths(queryId, runId);
    const rawExists = fs.existsSync(paths.raw);
    const metadataExists = fs.existsSync(paths.metadata);
    if (rawExists !== metadataExists) {
        throw new Error(`Incomplete existing run ${runId}: inspect ${paths.raw} and ${paths.metadata}`);
    }
    return rawExists && metadataExists;
}

async function runOnce(
    queryDef,
    dataset,
    threadCount,
    runId,
    isWarmup,
    executionSequence,
    config,
    harnessUrl,
) {
    const browser = await chromium.launch();
    try {
        const context = await browser.newContext();
        const page = await context.newPage();
        const datasetHost = new URL(dataset.url).host;
        let bytesSoFar = 0;
        let requestsSoFar = 0;

        page.on('requestfinished', async (req) => {
            try {
                if (new URL(req.url()).host !== datasetHost || req.method() === 'HEAD') return;
                const response = await req.response();
                if (!response) return;
                const header = response.headers()['content-length'];
                let length = header ? Number.parseInt(header, 10) : Number.NaN;
                if (!Number.isFinite(length)) {
                    try {
                        length = (await response.body()).length;
                    } catch {
                        length = 0;
                    }
                }
                bytesSoFar += length;
                requestsSoFar += 1;
            } catch {
                // A request may race browser teardown after the final frame.
            }
        });

        const frames = [];
        const t0 = Date.now();
        let errorMessage = null;

        await page.exposeFunction('__onFrame', (frameIndex, rows) => {
            const processedRows = resultTotalRows(rows);
            frames.push({
                run_id: runId,
                query_id: queryDef.query_id,
                dataset_id: dataset.id,
                dataset_kind: dataset.kind,
                permutation_seed: dataset.seed,
                threads: threadCount,
                execution_sequence: executionSequence,
                is_warmup: isWarmup,
                frame_index: frameIndex,
                elapsed_ms: Date.now() - t0,
                completed_fragments: frameIndex,
                total_fragments: null,
                fragment_fraction: null,
                processed_rows: processedRows,
                period_total_rows: null,
                processed_row_fraction: null,
                transferred_bytes: bytesSoFar,
                request_count: requestsSoFar,
                is_final: false,
                result: rows,
            });
        });
        await page.exposeFunction('__onDone', () => {});
        await page.exposeFunction('__onError', (message) => {
            errorMessage = message;
        });

        await page.goto(harnessUrl);
        await page.waitForFunction(() => typeof window.__runQuery === 'function');
        await page.evaluate(([sql, tc]) => window.__runQuery(sql, tc), [queryDef.sql, threadCount]);

        if (errorMessage) throw new Error(`Run ${runId} failed: ${errorMessage}`);
        if (!frames.length) throw new Error(`Run ${runId} emitted no frames`);

        const totalFragments = frames.length;
        const periodTotalRows = frames.at(-1).processed_rows;
        if (!periodTotalRows) throw new Error(`Run ${runId} has an empty final result`);
        if (queryDef.query_id !== 'Q1' && periodTotalRows !== config.expected_dataset_rows) {
            throw new Error(
                `Run ${runId} final row count ${periodTotalRows} != expected ${config.expected_dataset_rows}`,
            );
        }
        let previousRows = -1;
        for (const frame of frames) {
            if (frame.processed_rows < previousRows) {
                throw new Error(`Run ${runId} processed_rows is not monotonic at frame ${frame.frame_index}`);
            }
            previousRows = frame.processed_rows;
            frame.total_fragments = totalFragments;
            frame.fragment_fraction = frame.frame_index / totalFragments;
            frame.period_total_rows = periodTotalRows;
            frame.processed_row_fraction = frame.processed_rows / periodTotalRows;
        }
        frames.at(-1).is_final = true;

        const paths = runPaths(queryDef.query_id, runId);
        ensureDir(path.dirname(paths.raw));
        ensureDir(path.dirname(paths.metadata));
        fs.writeFileSync(paths.raw, `${frames.map((frame) => JSON.stringify(frame)).join('\n')}\n`);

        const metadata = {
            run_id: runId,
            query_id: queryDef.query_id,
            is_warmup: isWarmup,
            experiment_version: config.experiment_version,
            dataset_id: dataset.id,
            dataset_kind: dataset.kind,
            dataset_url: dataset.url,
            dataset_metadata_url: dataset.metadata_url,
            permutation_seed: dataset.seed,
            permutation_order_sha256: dataset.order_sha256 ?? null,
            permutation_manifest_sha256: config.manifest_sha256,
            target_year: config.target_year,
            period_start_year: queryDef.query_id === 'Q1'
                ? config.target_year
                : config.dataset_period.start_year,
            period_end_year: queryDef.query_id === 'Q1'
                ? config.target_year
                : config.dataset_period.end_year,
            cesarean_code: config.cesarean_code,
            threads: threadCount,
            execution_sequence: executionSequence,
            execution_order_seed: config.execution_order_seed,
            sql: queryDef.sql,
            browser_name: browser.browserType().name(),
            browser_version: browser.version(),
            operating_system: `${os.platform()} ${os.release()} (${os.arch()})`,
            cpu_model: os.cpus()[0]?.model ?? null,
            cpu_count: os.cpus().length,
            total_memory_bytes: os.totalmem(),
            node_version: process.version,
            cache_policy: config.runs.cache_policy,
            warmup_policy: config.runs.warmup_rationale,
            total_elapsed_ms: frames.at(-1).elapsed_ms,
            total_fragments: totalFragments,
            period_total_rows: periodTotalRows,
            total_transferred_bytes: bytesSoFar,
            total_request_count: requestsSoFar,
            final_result_sha256: canonicalResultHash(frames.at(-1).result),
            timestamp: new Date().toISOString(),
        };
        fs.writeFileSync(paths.metadata, JSON.stringify(metadata, null, 2));
        return metadata;
    } finally {
        await browser.close();
    }
}

function makeRunId(queryId, datasetId, threadCount, kind, index) {
    const suffix = kind === 'warmup' ? 'warmup' : 'run';
    return `${queryId}-${datasetId}-t${String(threadCount).padStart(2, '0')}-${suffix}-${String(index).padStart(3, '0')}`;
}

function printPlan(datasets, queryIds, threadCounts, warmupRuns, measuredRuns, executionOrderSeed) {
    const measured = datasets.length * queryIds.length * threadCounts.length * measuredRuns;
    const warmups = datasets.length * queryIds.length * threadCounts.length * warmupRuns;
    console.log('Order-sensitivity collection plan');
    console.log(`  datasets: ${datasets.map((d) => d.id).join(', ')}`);
    console.log(`  queries: ${queryIds.join(', ')}`);
    console.log(`  threads: ${threadCounts.join(', ')}`);
    console.log(`  warm-ups per combination: ${warmupRuns}`);
    console.log(`  measured runs per combination: ${measuredRuns}`);
    console.log(`  randomized combination-order seed: ${executionOrderSeed}`);
    console.log(`  total warm-ups: ${warmups}`);
    console.log(`  total measured runs: ${measured}`);
}

async function main() {
    const args = parseArgs(process.argv);
    const config = loadAndValidateConfig();
    const datasets = filterSelected(config.datasets, args.datasetIds, (d) => d.id, 'dataset id');
    const threadCounts = filterSelected(
        config.thread_counts,
        args.threadCounts?.map(String) ?? null,
        (value) => value,
        'thread count',
    );
    const queryIds = filterSelected(['Q1', 'Q2', 'Q3'], args.queryIds, (value) => value, 'query id');
    const warmupRuns = args.warmupRuns ?? config.runs.warmup_runs;
    const measuredRuns = args.measuredRuns ?? config.runs.measured_runs;

    printPlan(
        datasets,
        queryIds,
        threadCounts,
        warmupRuns,
        measuredRuns,
        config.execution_order_seed,
    );
    if (args.listPlan) return;

    console.log('\nPreflight: checking every selected Parquet and sidecar metadata object ...');
    const failures = [];
    for (const dataset of datasets) {
        try {
            const info = await preflightDataset(dataset, config);
            const size = info.parquet_headers['content-length']
                ?? info.parquet_headers['x-goog-stored-content-length']
                ?? '?';
            console.log(`  [ok] ${dataset.id}: ${size} bytes`);
        } catch (error) {
            failures.push(String(error.message ?? error));
            console.error(`  [missing] ${dataset.id}: ${error.message ?? error}`);
        }
    }
    if (failures.length) {
        throw new Error(`Preflight failed for ${failures.length} dataset(s); no query was started`);
    }
    if (args.preflightOnly) return;

    ({ chromium } = await import('playwright'));

    const server = await startStaticServer(__dirname);
    const { port } = server.address();
    const harnessUrl = `http://127.0.0.1:${port}/harness.html`;
    let completed = 0;
    let skipped = 0;
    const selectedDatasetIds = new Set(datasets.map((dataset) => dataset.id));
    const selectedQueryIds = new Set(queryIds);
    const selectedThreadCounts = new Set(threadCounts);
    const combinations = shuffledCombinations(
        config.datasets,
        ['Q1', 'Q2', 'Q3'],
        config.thread_counts,
        config.execution_order_seed,
    )
        .map((combination, index) => ({ ...combination, executionSequence: index + 1 }))
        .filter(({ dataset, queryId, threadCount }) => (
            selectedDatasetIds.has(dataset.id)
            && selectedQueryIds.has(queryId)
            && selectedThreadCounts.has(threadCount)
        ));
    try {
        for (const [selectedIndex, combination] of combinations.entries()) {
            const { dataset, threadCount, queryId, executionSequence } = combination;
            const queryMap = new Map(buildQueries(config, dataset.url).map((query) => [query.query_id, query]));
            const query = queryMap.get(queryId);
            console.log(
                `\n=== selected ${selectedIndex + 1}/${combinations.length}; `
                + `global sequence ${executionSequence}/90 | ${dataset.id} | ${queryId} | `
                + `${threadCount} thread(s) ===`,
            );
            for (const [kind, count] of [['warmup', warmupRuns], ['measured', measuredRuns]]) {
                for (let index = 1; index <= count; index++) {
                    const runId = makeRunId(queryId, dataset.id, threadCount, kind, index);
                    if (existingRunState(queryId, runId)) {
                        console.log(`  [skip] ${runId}`);
                        skipped += 1;
                        continue;
                    }
                    process.stdout.write(`  [${kind}] ${runId} ... `);
                    const metadata = await runOnce(
                        query,
                        dataset,
                        threadCount,
                        runId,
                        kind === 'warmup',
                        executionSequence,
                        config,
                        harnessUrl,
                    );
                    console.log(
                        `${metadata.total_elapsed_ms} ms, ${metadata.total_fragments} fragments, `
                        + `${metadata.total_transferred_bytes.toLocaleString('en-US')} bytes`,
                    );
                    completed += 1;
                }
            }
        }
    } finally {
        server.close();
    }
    console.log(`\nCollection finished: ${completed} completed, ${skipped} resumed/skipped.`);
    console.log('Raw traces:', path.join(OUTPUT, 'raw'));
    console.log('Run metadata:', path.join(OUTPUT, 'metadata'));
}

main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});
