"""
HyPhy WASM Benchmark Suite - Snakemake Workflow

Run benchmarks across multiple datasets, methods, and CPU configurations.

Usage:
    # Local execution
    snakemake --cores 4

    # SLURM cluster execution
    snakemake --profile slurm

    # Dry run
    snakemake -n

    # Generate report
    snakemake --report report.html
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

# Timestamp for this run
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# All benchmark targets
rule all:
    input:
        # Individual benchmark results
        expand(
            f"{OUTPUT_DIR}/cli/{{dataset}}_{{method}}_cpu{{cpu}}.json",
            dataset=DATASETS,
            method=METHODS,
            cpu=CPU_CONFIGS
        ),
        # Aggregated summary
        f"{OUTPUT_DIR}/summary_{TIMESTAMP}.md"


rule run_benchmark:
    """Run a single HyPhy benchmark."""
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
        f"{OUTPUT_DIR}/logs/{{dataset}}_{{method}}_cpu{{cpu}}.log"
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


rule aggregate_results:
    """Aggregate all benchmark results into a summary."""
    input:
        expand(
            f"{OUTPUT_DIR}/cli/{{dataset}}_{{method}}_cpu{{cpu}}.json",
            dataset=DATASETS,
            method=METHODS,
            cpu=CPU_CONFIGS
        )
    output:
        summary=f"{OUTPUT_DIR}/summary_{TIMESTAMP}.md",
        csv=f"{OUTPUT_DIR}/summary_{TIMESTAMP}.csv",
        json=f"{OUTPUT_DIR}/summary_{TIMESTAMP}.json"
    shell:
        """
        python scripts/aggregate_results.py \
            --input-dir {OUTPUT_DIR}/cli \
            --output-md {output.summary} \
            --output-csv {output.csv} \
            --output-json {output.json}
        """


rule clean:
    """Remove all generated files."""
    shell:
        "rm -rf {OUTPUT_DIR}/*"
