"""The one-command reproducibility entry point for everything downstream of
data collection: raw logs -> derived metrics -> summary tables -> figures.
Mirrors the pipeline diagram in the paper draft (Figure "analysis-pipeline").
Run with `python analysis/build_all.py` (venv active) after
`node harness/run_experiment.mjs` has produced output/raw/.
"""
import run_analysis
import build_tables
import make_figures
import resolve_paper_placeholders

if __name__ == "__main__":
    print("=== Stage 1/4: raw traces -> derived per-frame/per-run CSVs ===")
    run_analysis.main()
    print("\n=== Stage 2/4: derived CSVs -> summary tables ===")
    build_tables.main()
    print("\n=== Stage 3/4: derived CSVs + raw traces -> figures ===")
    make_figures.main()
    print("\n=== Stage 4/4: resolve paper placeholder macros from collected data ===")
    resolve_paper_placeholders.main()
    print("\nAll done.")
