#!/usr/bin/env python3
"""
Run a single HyPhy WASM benchmark using Playwright.

Usage:
    python run_wasm_benchmark.py --alignment data/bglobin.nex --method fel --browser chromium --iterations 3 --output results.json
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
import statistics

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Error: playwright not installed. Run: pip install playwright && playwright install", file=sys.stderr)
    sys.exit(1)


# HTML page that loads HyPhy WASM
BENCHMARK_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>HyPhy WASM Benchmark</title>
    <script src="https://cdn.jsdelivr.net/npm/@biowasm/aioli@3.2.1/dist/aioli.js"></script>
</head>
<body>
    <h1>HyPhy WASM Benchmark</h1>
    <div id="status">Loading...</div>
    <script>
        window.benchmarkReady = false;
        window.hyphyCli = null;

        async function initHyPhy() {
            document.getElementById('status').textContent = 'Initializing HyPhy WASM...';

            window.hyphyCli = await new Aioli({
                tool: 'hyphy',
                version: '2.5.63',
                urlPrefix: 'https://data.hyphy.org/web/biowasm'
            }, { printInterleaved: false });

            const versionResult = await window.hyphyCli.exec('hyphy --version');
            window.hyphyVersion = versionResult.stdout.trim().split('\\n')[0];

            document.getElementById('status').textContent = 'Ready: ' + window.hyphyVersion;
            window.benchmarkReady = true;
        }

        async function runBenchmark(alignmentData, method) {
            if (!window.hyphyCli) throw new Error('HyPhy not initialized');

            // Mount alignment file
            const inputFiles = await window.hyphyCli.mount([
                { name: 'input.nex', data: alignmentData }
            ]);

            // Run analysis
            const command = `hyphy LIBPATH=/shared/hyphy/ ${method} ${inputFiles[0]}`;
            const startTime = performance.now();
            const result = await window.hyphyCli.exec(command);
            await result.stdout;
            const endTime = performance.now();

            return {
                runtimeMs: endTime - startTime,
                success: true
            };
        }

        initHyPhy().catch(err => {
            document.getElementById('status').textContent = 'Error: ' + err.message;
            console.error(err);
        });
    </script>
</body>
</html>
"""


async def run_wasm_benchmark(browser_type: str, alignment_path: Path, method: str, iterations: int) -> list[dict]:
    """Run WASM benchmark using Playwright."""

    # Read alignment data
    alignment_data = alignment_path.read_text()

    async with async_playwright() as p:
        # Launch browser
        if browser_type == "chromium":
            browser = await p.chromium.launch(headless=True)
        elif browser_type == "firefox":
            browser = await p.firefox.launch(headless=True)
        elif browser_type == "webkit":
            browser = await p.webkit.launch(headless=True)
        else:
            raise ValueError(f"Unknown browser: {browser_type}")

        # Create context with SharedArrayBuffer support
        context = await browser.new_context()
        page = await context.new_page()

        # Set up the page with our HTML
        await page.set_content(BENCHMARK_HTML)

        # Wait for HyPhy to initialize (up to 2 minutes)
        print("  Initializing HyPhy WASM...", flush=True)
        await page.wait_for_function("window.benchmarkReady === true", timeout=120000)

        # Get HyPhy version
        hyphy_version = await page.evaluate("window.hyphyVersion")
        print(f"  HyPhy WASM version: {hyphy_version}", flush=True)

        # Run benchmark iterations
        results = []
        for i in range(1, iterations + 1):
            print(f"  Iteration {i}/{iterations}...", end=" ", flush=True)

            try:
                result = await page.evaluate(
                    f"runBenchmark({json.dumps(alignment_data)}, {json.dumps(method)})"
                )
                print(f"{result['runtimeMs']:.0f}ms ✓")
                results.append({
                    "iteration": i,
                    "runtimeMs": result["runtimeMs"],
                    "success": True
                })
            except Exception as e:
                print(f"failed: {e}")
                results.append({
                    "iteration": i,
                    "runtimeMs": 0,
                    "success": False,
                    "error": str(e)
                })

        await browser.close()

        return results, hyphy_version


def main():
    parser = argparse.ArgumentParser(description="Run HyPhy WASM benchmark")
    parser.add_argument("--alignment", required=True, help="Path to alignment file")
    parser.add_argument("--method", required=True, help="HyPhy method")
    parser.add_argument("--browser", default="chromium", help="Browser (chromium, firefox, webkit)")
    parser.add_argument("--iterations", type=int, default=3, help="Number of iterations")
    parser.add_argument("--sequences", type=int, default=0, help="Number of sequences")
    parser.add_argument("--sites", type=int, default=0, help="Number of sites")
    parser.add_argument("--output", required=True, help="Output JSON file")

    args = parser.parse_args()

    alignment_path = Path(args.alignment)
    if not alignment_path.exists():
        print(f"Error: Alignment file not found: {args.alignment}", file=sys.stderr)
        sys.exit(1)

    dataset = alignment_path.stem

    print(f"Running WASM benchmark: {args.method} on {dataset} ({args.browser})")
    print(f"  Alignment: {args.alignment}")
    print(f"  Iterations: {args.iterations}")

    # Run async benchmark
    iterations, hyphy_version = asyncio.run(
        run_wasm_benchmark(args.browser, alignment_path, args.method, args.iterations)
    )

    # Calculate statistics
    successful_times = [it["runtimeMs"] for it in iterations if it["success"]]

    if successful_times:
        stats = {
            "n": len(successful_times),
            "mean": statistics.mean(successful_times),
            "stdDev": statistics.stdev(successful_times) if len(successful_times) > 1 else 0,
            "min": min(successful_times),
            "max": max(successful_times),
            "median": statistics.median(successful_times),
        }
        stats["standardError"] = stats["stdDev"] / (stats["n"] ** 0.5) if stats["n"] > 0 else 0
        stats["cv"] = (stats["stdDev"] / stats["mean"] * 100) if stats["mean"] > 0 else 0
    else:
        stats = {"n": 0, "mean": None, "error": "All iterations failed"}

    # Build result
    result = {
        "platform": "wasm",
        "browser": args.browser,
        "dataset": dataset,
        "method": args.method,
        "sequences": args.sequences,
        "sites": args.sites,
        "iterations": iterations,
        "statistics": stats,
        "hyphyVersion": hyphy_version,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nResults saved to: {args.output}")

    if stats.get("mean"):
        print(f"Mean: {stats['mean']:.0f}ms ± {stats['standardError']:.0f}ms")


if __name__ == "__main__":
    main()
