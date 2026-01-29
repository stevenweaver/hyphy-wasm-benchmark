# HyPhy WASM Benchmark Suite

Benchmarking suite for comparing HyPhy performance across different configurations, designed for execution on SLURM clusters.

## Quick Start

### Local Execution

```bash
# Install dependencies
pip install snakemake

# Run all benchmarks locally (4 cores)
snakemake --cores 4

# Dry run (see what will be executed)
snakemake -n
```

### SLURM Cluster Execution

```bash
# Run on cluster using SLURM profile
snakemake --profile slurm

# Submit with specific partition
snakemake --profile slurm --default-resources slurm_partition=gpu
```

## Configuration

Edit `config.yaml` to customize:

- **datasets**: Alignment files to benchmark
- **methods**: HyPhy methods (fel, slac, meme, absrel, busted, relax)
- **iterations**: Number of timing iterations per benchmark
- **cpu_configs**: CPU counts to test (1, 4, 8, 0=all)

## Environment Variables

```bash
# Path to HyPhy binary
export HYPHY_BIN=/path/to/hyphy

# HyPhy library path (optional)
export HYPHY_LIBPATH=/path/to/hyphy/res
```

## Directory Structure

```
hyphy-wasm-benchmark/
├── Snakefile           # Main workflow
├── config.yaml         # Configuration
├── slurm/
│   └── config.yaml     # SLURM profile
├── scripts/
│   ├── run_benchmark.py      # Single benchmark runner
│   └── aggregate_results.py  # Results aggregation
├── data/               # Alignment files
│   ├── bglobin.nex
│   ├── lysozyme.nex
│   └── ...
└── results/            # Output directory
    ├── cli/            # Individual benchmark results
    └── summary_*.md    # Aggregated summaries
```

## Datasets

| Dataset | Sequences | Sites | Description |
|---------|-----------|-------|-------------|
| bglobin | 17 | 432 | Beta-globin |
| lysozyme | 19 | 390 | Lysozyme |
| adh | 23 | 762 | Alcohol dehydrogenase |
| HIVvif | 29 | 576 | HIV Vif protein |
| HepatitisD | 33 | 588 | Hepatitis D virus |
| camelid | 212 | 288 | Camelid antibodies |

## Methods

- **FEL**: Fixed Effects Likelihood
- **SLAC**: Single-Likelihood Ancestor Counting
- **MEME**: Mixed Effects Model of Evolution
- **aBSREL**: Adaptive Branch-Site REL
- **BUSTED**: Branch-Site Unrestricted Statistical Test
- **RELAX**: Test for relaxed/intensified selection

## Output

Results are saved as JSON files with timing statistics:

```json
{
  "dataset": "bglobin",
  "method": "fel",
  "cpu": 4,
  "statistics": {
    "mean": 12345.6,
    "stdDev": 123.4,
    "standardError": 71.3,
    "n": 3
  }
}
```

## Running Specific Benchmarks

```bash
# Run only FEL benchmarks
snakemake --cores 4 results/cli/bglobin_fel_cpu1.json

# Run all benchmarks for one dataset
snakemake --cores 4 $(snakemake --list | grep bglobin)
```

## License

MIT
