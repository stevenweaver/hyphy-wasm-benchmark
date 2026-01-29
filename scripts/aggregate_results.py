#!/usr/bin/env python3
"""
Aggregate benchmark results into summary files.
Handles both CLI and WASM benchmark results.
"""

import argparse
import json
import csv
from pathlib import Path
from datetime import datetime


def load_results(input_dir: Path) -> list[dict]:
    """Load all JSON result files from a directory."""
    results = []
    if input_dir.exists():
        for json_file in input_dir.glob("*.json"):
            try:
                with open(json_file) as f:
                    results.append(json.load(f))
            except Exception as e:
                print(f"Warning: Could not load {json_file}: {e}")
    return results


def generate_summary(cli_results: list[dict], wasm_results: list[dict]) -> dict:
    """Generate summary statistics."""
    all_results = cli_results + wasm_results

    summary = {
        "generated": datetime.utcnow().isoformat() + "Z",
        "total_benchmarks": len(all_results),
        "cli_benchmarks": len(cli_results),
        "wasm_benchmarks": len(wasm_results),
        "datasets": sorted(set(r.get("dataset", "") for r in all_results)),
        "methods": sorted(set(r.get("method", "") for r in all_results)),
        "cli_results": cli_results,
        "wasm_results": wasm_results
    }
    return summary


def write_markdown(cli_results: list[dict], wasm_results: list[dict], output_path: Path):
    """Write markdown summary with CLI vs WASM comparison."""

    with open(output_path, "w") as f:
        f.write("# HyPhy Benchmark Results\n\n")
        f.write(f"**Generated:** {datetime.utcnow().isoformat()}Z\n\n")
        f.write(f"- CLI benchmarks: {len(cli_results)}\n")
        f.write(f"- WASM benchmarks: {len(wasm_results)}\n\n")

        # Get all datasets and methods
        datasets = sorted(set(r.get("dataset", "") for r in cli_results + wasm_results))
        methods = sorted(set(r.get("method", "") for r in cli_results + wasm_results))

        # Build lookup tables
        cli_lookup = {}
        for r in cli_results:
            key = (r.get("dataset"), r.get("method"), str(r.get("cpu", "")))
            if r.get("statistics", {}).get("mean"):
                cli_lookup[key] = r["statistics"]["mean"]

        wasm_lookup = {}
        for r in wasm_results:
            key = (r.get("dataset"), r.get("method"), r.get("browser", ""))
            if r.get("statistics", {}).get("mean"):
                wasm_lookup[key] = r["statistics"]["mean"]

        # Write comparison table for each method
        for method in methods:
            f.write(f"## {method.upper()}\n\n")
            f.write("| Dataset | Seq×Sites | CPU=1 | CPU=all | WASM | WASM vs CPU=1 |\n")
            f.write("|---------|-----------|-------|---------|------|---------------|\n")

            for ds in datasets:
                # Find seq×sites
                seq_sites = ""
                for r in cli_results + wasm_results:
                    if r.get("dataset") == ds:
                        seq_sites = f"{r.get('sequences', '?')}×{r.get('sites', '?')}"
                        break

                cpu1 = cli_lookup.get((ds, method, "1"))
                cpu_all = cli_lookup.get((ds, method, "0")) or cli_lookup.get((ds, method, "all"))
                wasm = wasm_lookup.get((ds, method, "chromium"))

                cpu1_str = f"{cpu1:.0f}ms" if cpu1 else "-"
                cpu_all_str = f"{cpu_all:.0f}ms" if cpu_all else "-"
                wasm_str = f"{wasm:.0f}ms" if wasm else "-"

                # Calculate overhead
                if cpu1 and wasm:
                    overhead = ((wasm - cpu1) / cpu1) * 100
                    overhead_str = f"+{overhead:.0f}%" if overhead > 0 else f"{overhead:.0f}%"
                else:
                    overhead_str = "-"

                f.write(f"| {ds} | {seq_sites} | {cpu1_str} | {cpu_all_str} | {wasm_str} | {overhead_str} |\n")

            f.write("\n")

        # Summary statistics
        f.write("## Summary\n\n")

        if wasm_lookup and cli_lookup:
            overheads = []
            for (ds, method, browser), wasm_time in wasm_lookup.items():
                cpu1_time = cli_lookup.get((ds, method, "1"))
                if cpu1_time and wasm_time:
                    overheads.append(((wasm_time - cpu1_time) / cpu1_time) * 100)

            if overheads:
                avg_overhead = sum(overheads) / len(overheads)
                f.write(f"- **Average WASM overhead vs single-threaded:** {avg_overhead:+.0f}%\n")
                f.write(f"- **Min overhead:** {min(overheads):+.0f}%\n")
                f.write(f"- **Max overhead:** {max(overheads):+.0f}%\n")


def write_csv(cli_results: list[dict], wasm_results: list[dict], output_path: Path):
    """Write CSV summary."""
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "platform", "dataset", "method", "cpu_or_browser", "sequences", "sites",
            "mean_ms", "std_ms", "se_ms", "min_ms", "max_ms", "n"
        ])

        for r in cli_results:
            stats = r.get("statistics", {})
            writer.writerow([
                "cli",
                r.get("dataset", ""),
                r.get("method", ""),
                r.get("cpu", ""),
                r.get("sequences", ""),
                r.get("sites", ""),
                stats.get("mean", ""),
                stats.get("stdDev", ""),
                stats.get("standardError", ""),
                stats.get("min", ""),
                stats.get("max", ""),
                stats.get("n", 0)
            ])

        for r in wasm_results:
            stats = r.get("statistics", {})
            writer.writerow([
                "wasm",
                r.get("dataset", ""),
                r.get("method", ""),
                r.get("browser", ""),
                r.get("sequences", ""),
                r.get("sites", ""),
                stats.get("mean", ""),
                stats.get("stdDev", ""),
                stats.get("standardError", ""),
                stats.get("min", ""),
                stats.get("max", ""),
                stats.get("n", 0)
            ])


def main():
    parser = argparse.ArgumentParser(description="Aggregate benchmark results")
    parser.add_argument("--cli-dir", help="Directory with CLI JSON results")
    parser.add_argument("--wasm-dir", help="Directory with WASM JSON results")
    parser.add_argument("--input-dir", help="Legacy: single input directory")
    parser.add_argument("--output-md", required=True, help="Output markdown file")
    parser.add_argument("--output-csv", required=True, help="Output CSV file")
    parser.add_argument("--output-json", required=True, help="Output JSON file")

    args = parser.parse_args()

    # Load results
    cli_results = []
    wasm_results = []

    if args.cli_dir:
        cli_results = load_results(Path(args.cli_dir))
    if args.wasm_dir:
        wasm_results = load_results(Path(args.wasm_dir))
    if args.input_dir:
        # Legacy mode: load all from single dir
        all_results = load_results(Path(args.input_dir))
        for r in all_results:
            if r.get("platform") == "wasm":
                wasm_results.append(r)
            else:
                cli_results.append(r)

    print(f"Loaded {len(cli_results)} CLI results, {len(wasm_results)} WASM results")

    # Write outputs
    write_markdown(cli_results, wasm_results, Path(args.output_md))
    write_csv(cli_results, wasm_results, Path(args.output_csv))

    summary = generate_summary(cli_results, wasm_results)
    with open(args.output_json, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Saved: {args.output_md}, {args.output_csv}, {args.output_json}")


if __name__ == "__main__":
    main()
