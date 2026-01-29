#!/usr/bin/env python3
"""
Aggregate benchmark results into summary files.
"""

import argparse
import json
import csv
from pathlib import Path
from datetime import datetime


def load_results(input_dir: Path) -> list[dict]:
    """Load all JSON result files."""
    results = []
    for json_file in input_dir.glob("*.json"):
        with open(json_file) as f:
            results.append(json.load(f))
    return results


def generate_summary(results: list[dict]) -> dict:
    """Generate summary statistics."""
    summary = {
        "generated": datetime.utcnow().isoformat() + "Z",
        "total_benchmarks": len(results),
        "datasets": sorted(set(r["dataset"] for r in results)),
        "methods": sorted(set(r["method"] for r in results)),
        "cpu_configs": sorted(set(str(r["cpu"]) for r in results)),
        "results": results
    }
    return summary


def write_markdown(results: list[dict], output_path: Path):
    """Write markdown summary."""
    # Group by method
    by_method = {}
    for r in results:
        method = r["method"]
        if method not in by_method:
            by_method[method] = []
        by_method[method].append(r)

    with open(output_path, "w") as f:
        f.write("# HyPhy Benchmark Results\n\n")
        f.write(f"**Generated:** {datetime.utcnow().isoformat()}Z\n\n")

        for method in sorted(by_method.keys()):
            f.write(f"## {method.upper()}\n\n")
            f.write("| Dataset | Seq×Sites | CPU=1 | CPU=4 | CPU=8 | CPU=all |\n")
            f.write("|---------|-----------|-------|-------|-------|----------|\n")

            # Group by dataset
            by_dataset = {}
            for r in by_method[method]:
                ds = r["dataset"]
                if ds not in by_dataset:
                    by_dataset[ds] = {}
                cpu = str(r["cpu"])
                if r["statistics"].get("mean"):
                    by_dataset[ds][cpu] = f"{r['statistics']['mean']:.0f}ms"
                else:
                    by_dataset[ds][cpu] = "failed"

            for ds in sorted(by_dataset.keys()):
                # Find sequences/sites from any result for this dataset
                seq_sites = ""
                for r in by_method[method]:
                    if r["dataset"] == ds:
                        seq_sites = f"{r['sequences']}×{r['sites']}"
                        break

                row = by_dataset[ds]
                f.write(f"| {ds} | {seq_sites} | {row.get('1', '-')} | {row.get('4', '-')} | {row.get('8', '-')} | {row.get('all', '-')} |\n")

            f.write("\n")


def write_csv(results: list[dict], output_path: Path):
    """Write CSV summary."""
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "dataset", "method", "cpu", "sequences", "sites",
            "mean_ms", "std_ms", "se_ms", "min_ms", "max_ms", "n"
        ])

        for r in results:
            stats = r["statistics"]
            writer.writerow([
                r["dataset"],
                r["method"],
                r["cpu"],
                r["sequences"],
                r["sites"],
                stats.get("mean", ""),
                stats.get("stdDev", ""),
                stats.get("standardError", ""),
                stats.get("min", ""),
                stats.get("max", ""),
                stats.get("n", 0)
            ])


def main():
    parser = argparse.ArgumentParser(description="Aggregate benchmark results")
    parser.add_argument("--input-dir", required=True, help="Directory with JSON results")
    parser.add_argument("--output-md", required=True, help="Output markdown file")
    parser.add_argument("--output-csv", required=True, help="Output CSV file")
    parser.add_argument("--output-json", required=True, help="Output JSON file")

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    results = load_results(input_dir)

    print(f"Loaded {len(results)} benchmark results")

    # Write outputs
    write_markdown(results, Path(args.output_md))
    write_csv(results, Path(args.output_csv))

    summary = generate_summary(results)
    with open(args.output_json, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Saved: {args.output_md}, {args.output_csv}, {args.output_json}")


if __name__ == "__main__":
    main()
