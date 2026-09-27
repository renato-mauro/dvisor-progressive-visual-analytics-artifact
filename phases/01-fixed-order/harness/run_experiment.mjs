// Drives the actual data collection for the convergence experiment
// described in anotacoes/draft/paperdraft.tex ("Experimental Protocol and
// Reproducibility"). Every measured execution produces a complete raw trace
// of progressive frames (JSONL, one file per run) plus a per-run metadata
// JSON — metrics are never computed here; see ../analysis for that. Run
// with `node harness/run_experiment.mjs` from the project root, or via
// `npm run experiment`.
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import http from 'node:http';
import { fileURLToPath } from 'node:url';
import { buildQueries } from './queries.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const CONFIG_PATH = path.join(ROOT, 'config', 'experiment.json');
const OUTPUT = path.join(ROOT, 'output');

const CONTENT_TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.wasm': 'application/wasm', '.mjs': 'text/javascript' };

// harness.html must be served over http(s), not file:// — dvisor-web-lib's
// client module does a top-level `await fetch(workerUrl)` to read its own
// worker script as text (see dvisor-web-lib/src/client/index.js), and
// fetch() against a file: document is blocked by Chromium, so that await
// would simply hang forever and window.__runQuery would never be defined.
// A throwaway static server on an ephemeral local port avoids that with no
// extra dependency (matching the same http.server pattern used throughout
// this project's manual testing, just in Node instead of Python).
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
                res.writeHead(200, { 'Content-Type': CONTENT_TYPES[path.extname(filePath)] || 'application/octet-stream' });
                res.end(data);
            });
        });
        server.listen(0, '127.0.0.1', () => resolve(server));
    });
}

function ensureDir(p) {
    fs.mkdirSync(p, { recursive: true });
}

function parseArgs(argv) {
    const args = { query: null, measuredRuns: null, warmupRuns: null };
    for (const a of argv.slice(2)) {
        const [k, v] = a.replace(/^--/, '').split('=');
        if (k === 'query') args.query = v;
        if (k === 'runs') args.measuredRuns = Number(v);
        if (k === 'warmup') args.warmupRuns = Number(v);
    }
    return args;
}

// One-time, cached dataset fingerprint: exact byte size and SHA-256 (both
// explicitly requested by the paper's "Experimental Protocol" section as
// run-level metadata, to let a reader verify which exact dataset version
// produced the reported numbers) and exact row count. Row count is obtained
// with a plain `count()` query rather than full metadata generation — both
// are correct, but count() alone needs to read zero physical columns
// (see anotacoes/achado-count-sem-where.md) and is dramatically cheaper
// than scanning every column to also derive preferred integer widths, which
// this experiment has no use for.
async function computeDatasetInfo(config, harnessUrl) {
    const infoPath = path.join(OUTPUT, 'metadata', 'dataset-info.json');
    if (fs.existsSync(infoPath)) {
        console.log('[dataset-info] using cached', infoPath);
        return JSON.parse(fs.readFileSync(infoPath, 'utf-8'));
    }
    console.log('[dataset-info] downloading and hashing the dataset once (result is cached to disk afterwards)...');
    const res = await fetch(config.dataset_url);
    if (!res.ok || !res.body) {
        throw new Error(`Failed to fetch dataset for hashing: HTTP ${res.status}`);
    }
    const hash = crypto.createHash('sha256');
    let bytes = 0;
    const reader = res.body.getReader();
    for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        hash.update(value);
        bytes += value.length;
    }
    console.log(`[dataset-info] hashed ${bytes.toLocaleString('en-US')} bytes`);

    const rowCount = await countRows(config, harnessUrl);
    console.log(`[dataset-info] row count: ${rowCount?.toLocaleString('en-US')}`);

    const info = {
        dataset_url: config.dataset_url,
        dataset_bytes: bytes,
        dataset_sha256: hash.digest('hex'),
        dataset_rows: rowCount,
        // Stated directly in the paper draft (27 federative units x 10
        // years) — a physical fact of how the file was written, not
        // something this script re-derives.
        row_groups: 270,
        computed_at: new Date().toISOString(),
    };
    ensureDir(path.dirname(infoPath));
    fs.writeFileSync(infoPath, JSON.stringify(info, null, 2));
    return info;
}

async function countRows(config, harnessUrl) {
    const browser = await chromium.launch();
    try {
        const context = await browser.newContext();
        const page = await context.newPage();
        let result = null;
        let errorMessage = null;
        await page.exposeFunction('__onFrame', (_frameIndex, rows) => {
            result = rows;
        });
        await page.exposeFunction('__onDone', () => {});
        await page.exposeFunction('__onError', (msg) => {
            errorMessage = msg;
        });
        await page.goto(harnessUrl);
        await page.waitForFunction(() => typeof window.__runQuery === 'function');
        await page.evaluate(([sql, tc]) => window.__runQuery(sql, tc), [`SELECT count() AS n FROM '${config.dataset_url}'`, 1]);
        if (errorMessage) throw new Error(errorMessage);
        return result && result[0] ? result[0].n : null;
    } finally {
        await browser.close();
    }
}

// Runs one full progressive execution of `queryDef.sql` in a fresh,
// isolated browser context (cold cache/storage — see config's
// runs.cache_policy) and writes its raw JSONL trace plus per-run metadata.
// transferred_bytes/request_count are attributed to each frame from a live
// running total updated by a page.on('requestfinished') listener scoped to
// the dataset's own host — a vantage point only available because this
// harness drives the browser externally via Playwright, unlike the
// dvisor-site convergencia page, which has no way to observe network
// timing from inside the page itself (see that page's own documented gap
// in anotacoes/convergencia-visual-progressiva.md section 5).
async function runOnce(queryDef, runId, isWarmup, config, harnessUrl) {
    const browser = await chromium.launch();
    try {
        const context = await browser.newContext();
        const page = await context.newPage();

        const datasetHost = new URL(config.dataset_url).host;
        let bytesSoFar = 0;
        let requestsSoFar = 0;
        page.on('requestfinished', async (req) => {
            try {
                if (new URL(req.url()).host !== datasetHost) return;
                // dvisor issues exactly one HEAD per worker (js_get_content_length,
                // to learn the file's total size before any range reads) — its
                // Content-Length header describes what a GET of the same URL
                // would return, per HTTP semantics, even though a HEAD response
                // never actually carries that body. Counting it as transferred
                // data would silently add one full file size per worker thread
                // (confirmed empirically: with 4 threads, byte totals came out
                // almost exactly 4x the real dataset size before this check).
                if (req.method() === 'HEAD') return;
                const resp = await req.response();
                if (!resp) return;
                const lenHeader = resp.headers()['content-length'];
                let len = lenHeader ? parseInt(lenHeader, 10) : NaN;
                if (!Number.isFinite(len)) {
                    try {
                        len = (await resp.body()).length;
                    } catch {
                        len = 0;
                    }
                }
                bytesSoFar += len;
                requestsSoFar += 1;
            } catch {
                // A request racing the browser context's teardown at the very
                // end of a run is not worth failing the whole run over.
            }
        });

        const frames = [];
        const t0 = Date.now();
        let errorMessage = null;

        await page.exposeFunction('__onFrame', (frameIndex, rows) => {
            frames.push({
                run_id: runId,
                query_id: queryDef.query_id,
                frame_index: frameIndex,
                elapsed_ms: Date.now() - t0,
                completed_fragments: frameIndex,
                total_fragments: null,
                processed_fraction: null,
                transferred_bytes: bytesSoFar,
                request_count: requestsSoFar,
                is_final: false,
                result: rows,
            });
        });
        await page.exposeFunction('__onDone', () => {});
        await page.exposeFunction('__onError', (msg) => {
            errorMessage = msg;
        });

        await page.goto(harnessUrl);
        await page.waitForFunction(() => typeof window.__runQuery === 'function');
        await page.evaluate(([sql, tc]) => window.__runQuery(sql, tc), [queryDef.sql, config.threads]);

        if (errorMessage) {
            throw new Error(`Run ${runId} failed: ${errorMessage}`);
        }

        // total_fragments/processed_fraction are never known while a run is
        // still in progress — filled in here, once, after the fact, exactly
        // as the paper's protocol requires (raw trace first, metrics/derived
        // fields computed afterwards, never during collection).
        const totalFragments = frames.length;
        for (const f of frames) {
            f.total_fragments = totalFragments;
            f.processed_fraction = totalFragments ? f.frame_index / totalFragments : null;
        }
        if (frames.length) frames[frames.length - 1].is_final = true;

        const totalElapsedMs = frames.length ? frames[frames.length - 1].elapsed_ms : 0;

        const rawDir = path.join(OUTPUT, 'raw', queryDef.query_id);
        ensureDir(rawDir);
        fs.writeFileSync(path.join(rawDir, `${runId}.jsonl`), frames.map((f) => JSON.stringify(f)).join('\n') + '\n');

        const meta = {
            run_id: runId,
            query_id: queryDef.query_id,
            is_warmup: isWarmup,
            experiment_version: config.experiment_version,
            dataset_url: config.dataset_url,
            target_year: config.target_year,
            period_start_year: queryDef.query_id === 'Q1' ? config.target_year : config.dataset_period.start_year,
            period_end_year: queryDef.query_id === 'Q1' ? config.target_year : config.dataset_period.end_year,
            cesarean_code: config.cesarean_code,
            threads: config.threads,
            sql: queryDef.sql,
            browser_name: browser.browserType().name(),
            browser_version: browser.version(),
            operating_system: `${os.platform()} ${os.release()} (${os.arch()})`,
            cpu_model: os.cpus()[0]?.model ?? null,
            cpu_count: os.cpus().length,
            total_memory_bytes: os.totalmem(),
            node_version: process.version,
            total_elapsed_ms: totalElapsedMs,
            total_fragments: totalFragments,
            total_transferred_bytes: bytesSoFar,
            total_request_count: requestsSoFar,
            timestamp: new Date().toISOString(),
        };
        const metaDir = path.join(OUTPUT, 'metadata');
        ensureDir(metaDir);
        fs.writeFileSync(path.join(metaDir, `${runId}.json`), JSON.stringify(meta, null, 2));

        return meta;
    } finally {
        await browser.close();
    }
}

async function main() {
    const args = parseArgs(process.argv);
    const config = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf-8'));
    console.log('Loaded config from', CONFIG_PATH);

    const server = await startStaticServer(__dirname);
    const { port } = server.address();
    const harnessUrl = `http://127.0.0.1:${port}/harness.html`;

    try {
        await computeDatasetInfo(config, harnessUrl);

        let queries = buildQueries(config);
        if (args.query) {
            queries = queries.filter((q) => q.query_id === args.query);
            if (!queries.length) throw new Error(`Unknown --query=${args.query}`);
        }
        const warmupRuns = args.warmupRuns ?? config.runs.warmup_runs;
        const measuredRuns = args.measuredRuns ?? config.runs.measured_runs;

        for (const q of queries) {
            console.log(`\n=== ${q.query_id}: ${q.title} ===`);
            console.log(q.sql);
            for (let i = 1; i <= warmupRuns; i++) {
                const runId = `${q.query_id}-warmup-${String(i).padStart(3, '0')}`;
                process.stdout.write(`  [warmup]   ${runId} ... `);
                const meta = await runOnce(q, runId, true, config, harnessUrl);
                console.log(`${meta.total_elapsed_ms} ms, ${meta.total_fragments} fragments, ${meta.total_transferred_bytes.toLocaleString('en-US')} bytes`);
            }
            for (let i = 1; i <= measuredRuns; i++) {
                const runId = `${q.query_id}-run-${String(i).padStart(3, '0')}`;
                process.stdout.write(`  [measured] ${runId} ... `);
                const meta = await runOnce(q, runId, false, config, harnessUrl);
                console.log(`${meta.total_elapsed_ms} ms, ${meta.total_fragments} fragments, ${meta.total_transferred_bytes.toLocaleString('en-US')} bytes`);
            }
        }
        console.log('\nAll runs complete. Raw traces in output/raw/, metadata in output/metadata/.');
    } finally {
        server.close();
    }
}

main().catch((err) => {
    console.error(err);
    process.exitCode = 1;
});
