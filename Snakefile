"""
HyPhy WASM Benchmark Suite - Snakemake Workflow

Run benchmarks across multiple datasets, methods, and CPU configurations.
Includes both native CLI and browser-based WASM benchmarks.

Usage:
    # Run all benchmarks (CLI + WASM)
    snakemake --cores 4

    # Run only CLI benchmarks
    snakemake --cores 4 cli_all

    # Run only WASM benchmarks
    snakemake --cores 1 wasm_all

    # SLURM cluster execution
    snakemake --profile slurm

    # Dry run
    snakemake -n
"""

import os
from datetime import datetime

configfile: "config.yaml"

# Extract configuration
DATASETS = list(config["datasets"].keys())
METHODS = config["methods"]
ITERATIONS = config["iterations"]
CPU_CONFIGS = config["cpu_configs"]
OUTPUT_DIR = config["output_dir"]
BROWSERS = config.get("browsers", ["chromium"])

# Timestamp for this run
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# Default target: run everything
rule all:
    input:
        rules.cli_all.input,
        rules.wasm_all.input,
        f"{OUTPUT_DIR}/summary_{TIMESTAMP}.md"


# CLI-only target
rule cli_all:
    input:
        expand(
            f"{OUTPUT_DIR}/cli/{{dataset}}_{{method}}_cpu{{cpu}}.json",
            dataset=DATASETS,
            method=METHODS,
            cpu=CPU_CONFIGS
        )


# WASM-only target
rule wasm_all:
    input:
        expand(
            f"{OUTPUT_DIR}/wasm/{{dataset}}_{{method}}_{{browser}}.json",
            dataset=DATASETS,
            method=METHODS,
            browser=BROWSERS
        )


rule run_cli_benchmark:
    """Run a single native HyPhy CLI benchmark."""
    input:
        alignment=lambda wc: config["datasets"][wc.dataset]["file"]
    output:
        json=f"{OUTPUT_DIR}/cli/{{dataset}}_{{method}}_cpu{{cpu}}.json",
        log=f"{OUTPUT_DIR}/cli/{{dataset}}_{{method}}_cpu{{cpu}}.log"
    params:
        hyphy_bin=os.environ.get("HYPHY_BIN", config.get("hyphy_bin", "hyphy")),
        hyphy_libpath=os.environ.get("HYPHY_LIBPATH", config.get("hyphy_libpath", "")),
        iterations=ITERATIONS,
        sequences=lambda wc: config["datasets"][wc.dataset]["sequences"],
        sites=lambda wc: config["datasets"][wc.dataset]["sites"]
    threads: lambda wc: int(wc.cpu) if int(wc.cpu) > 0 else workflow.cores
    resources:
        mem_mb=lambda wc: 4000 if int(wc.cpu) <= 4 else 8000,
        runtime=lambda wc: 120 if wc.dataset != "camelid" else 360
    log:
        f"{OUTPUT_DIR}/logs/cli_{{dataset}}_{{method}}_cpu{{cpu}}.log"
    shell:
        """
        python scripts/run_benchmark.py \
            --alignment {input.alignment} \
            --method {wildcards.method} \
            --cpu {wildcards.cpu} \
            --iterations {params.iterations} \
            --hyphy-bin "{params.hyphy_bin}" \
            --hyphy-libpath "{params.hyphy_libpath}" \
            --sequences {params.sequences} \
            --sites {params.sites} \
            --output {output.json} \
            2>&1 | tee {output.log}
        """


rule run_wasm_benchmark:
    """Run a single HyPhy WASM benchmark via Playwright."""
    input:
        alignment=lambda wc: config["datasets"][wc.dataset]["file"]
    output:
        json=f"{OUTPUT_DIR}/wasm/{{dataset}}_{{method}}_{{browser}}.json",
        log=f"{OUTPUT_DIR}/wasm/{{dataset}}_{{method}}_{{browser}}.log"
    params:
        iterations=ITERATIONS,
        sequences=lambda wc: config["datasets"][wc.dataset]["sequences"],
        sites=lambda wc: config["datasets"][wc.dataset]["sites"]
    threads: 1  # WASM runs single-threaded in browser
    resources:
        mem_mb=8000,
        runtime=lambda wc: 180 if wc.dataset != "camelid" else 480
    log:
        f"{OUTPUT_DIR}/logs/wasm_{{dataset}}_{{method}}_{{browser}}.log"
    shell:
        """
        python scripts/run_wasm_benchmark.py \
            --alignment {input.alignment} \
            --method {wildcards.method} \
            --browser {wildcards.browser} \
            --iterations {params.iterations} \
            --sequences {params.sequences} \
            --sites {params.sites} \
            --output {output.json} \
            2>&1 | tee {output.log}
        """


rule aggregate_results:
    """Aggregate all benchmark results into a summary."""
    input:
        cli=expand(
            f"{OUTPUT_DIR}/cli/{{dataset}}_{{method}}_cpu{{cpu}}.json",
            dataset=DATASETS,
            method=METHODS,
            cpu=CPU_CONFIGS
        ),
        wasm=expand(
            f"{OUTPUT_DIR}/wasm/{{dataset}}_{{method}}_{{browser}}.json",
            dataset=DATASETS,
            method=METHODS,
            browser=BROWSERS
        )
    output:
        summary=f"{OUTPUT_DIR}/summary_{TIMESTAMP}.md",
        csv=f"{OUTPUT_DIR}/summary_{TIMESTAMP}.csv",
        json=f"{OUTPUT_DIR}/summary_{TIMESTAMP}.json"
    shell:
        """
        python scripts/aggregate_results.py \
            --cli-dir {OUTPUT_DIR}/cli \
            --wasm-dir {OUTPUT_DIR}/wasm \
            --output-md {output.summary} \
            --output-csv {output.csv} \
            --output-json {output.json}
        """


rule clean:
    """Remove all generated files."""
    shell:
        "rm -rf {OUTPUT_DIR}/*"
