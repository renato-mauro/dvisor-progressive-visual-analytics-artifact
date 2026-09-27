"""Validate and rebuild every artifact for the order-sensitivity study."""
import build_order_tables
import make_order_figures
import run_analysis
import validate_collection


if __name__ == "__main__":
    print("=== Stage 1/4: validate the complete 90-run collection ===")
    validate_collection.validate()
    print("\n=== Stage 2/4: raw traces -> derived metrics ===")
    run_analysis.main()
    print("\n=== Stage 3/4: derived metrics -> order-sensitivity tables ===")
    build_order_tables.main()
    print("\n=== Stage 4/4: order-sensitivity figures ===")
    make_order_figures.main()
    print("\nAll order-sensitivity artifacts are up to date.")
