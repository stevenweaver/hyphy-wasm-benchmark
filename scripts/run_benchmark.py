#!/usr/bin/env python3
"""
Run a single HyPhy benchmark with timing.

Usage:
    python run_benchmark.py --alignment data/bglobin.nex --method fel --cpu 1 --iterations 3 --output results.json
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
import statistics


def run_hyphy(hyphy_bin: str, libpath: str, method: str, alignment: str, cpu: int) -> tuple[float, int]:
    """Run HyPhy and return (runtime_ms, exit_code)."""

    cmd = [hyphy_bin]

    if cpu > 0:
        cmd.append(f"CPU={cpu}")

    if libpath:
        cmd.append(f"LIBPATH={libpath}")

    cmd.extend([method, "--alignment", alignment])

    start_time = time.perf_counter()

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    end_time = time.perf_counter()
    runtime_ms = (end_time - start_time) * 1000

    return runtime_ms, result.returncode


def get_system_info() -> dict:
    """Get system information."""
    import platform

    info = {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
    }

    # Try to get CPU count
    try:
        info["cpu_count"] = os.cpu_count()
    except:
        info["cpu_count"] = None

    # Try to get HyPhy version
    try:
        result = subprocess.run(
            [os.environ.get("HYPHY_BIN", "hyphy"), "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        info["hyphy_version"] = result.stdout.strip().split("\n")[0]
    except:
        info["hyphy_version"] = "unknown"

    return info


def main():
    parser = argparse.ArgumentParser(description="Run HyPhy benchmark")
    parser.add_argument("--alignment", required=True, help="Path to alignment file")
    parser.add_argument("--method", required=True, help="HyPhy method (fel, meme, slac, etc.)")
    parser.add_argument("--cpu", type=int, default=0, help="Number of CPUs (0 = all)")
    parser.add_argument("--iterations", type=int, default=3, help="Number of iterations")
    parser.add_argument("--hyphy-bin", default="hyphy", help="Path to HyPhy binary")
    parser.add_argument("--hyphy-libpath", default="", help="HyPhy LIBPATH")
    parser.add_argument("--sequences", type=int, default=0, help="Number of sequences")
    parser.add_argument("--sites", type=int, default=0, help="Number of sites")
    parser.add_argument("--output", required=True, help="Output JSON file")

    args = parser.parse_args()

    # Validate inputs
    if not Path(args.alignment).exists():
        print(f"Error: Alignment file not found: {args.alignment}", file=sys.stderr)
        sys.exit(1)

    # Get dataset name from alignment path
    dataset = Path(args.alignment).stem

    print(f"Running {args.method} on {dataset} (CPU={args.cpu if args.cpu > 0 else 'all'})")
    print(f"  Alignment: {args.alignment}")
    print(f"  Iterations: {args.iterations}")

    # Run benchmark iterations
    iterations = []
    for i in range(1, args.iterations + 1):
        print(f"  Iteration {i}/{args.iterations}...", end=" ", flush=True)

        runtime_ms, exit_code = run_hyphy(
            args.hyphy_bin,
            args.hyphy_libpath,
            args.method,
            args.alignment,
            args.cpu
        )

        success = exit_code == 0
        print(f"{runtime_ms:.0f}ms {'✓' if success else '✗'}")

        iterations.append({
            "iteration": i,
            "runtimeMs": runtime_ms,
            "success": success,
            "exitCode": exit_code
        })

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
        "dataset": dataset,
        "method": args.method,
        "cpu": args.cpu if args.cpu > 0 else "all",
        "sequences": args.sequences,
        "sites": args.sites,
        "iterations": iterations,
        "statistics": stats,
        "systemInfo": get_system_info(),
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
