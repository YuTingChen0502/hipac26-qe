# Experimental Results

Data cutoff: 2026-07-29.

This document condenses the validated performance evidence retained in the repository into a public-facing technical summary. The original experiment handoffs and raw-evidence references remain in Git history and under `docs/handoffs/`.

## Au(111), many-k-point workload

The experiment sequence tested k-point pools, resource shape, and topology-aware rank placement.

| Configuration | Median runtime | CV |
|---|---:|---:|
| 7+7 rank layout | 20.81 s | 0.181% |
| 8+6 rank layout | 18.72 s | 2.444% |

Retained workload-specific configuration:

```text
14 MPI ranks / GPUs
2 nodes
7 k-point pools
2 ranks per pool
8+6 rank placement
OMP_NUM_THREADS=12
```

This freeze is specific to the tested Au(111) workload and Nano4 environment.

## Si1000, Gamma-only workload

### Single-node refinement and confirmation

Two independent studies compared 6 and 8 active GPUs.

Combined result:

| Configuration | Combined median |
|---|---:|
| 6 GPUs | 104.295 s |
| 8 GPUs | 83.130 s |

The 8-GPU configuration reduced median latency by 20.293%, with 10/10 paired wins across the two studies.

### Node-boundary confirmation

| Configuration | Active nodes | Median runtime | CV |
|---|---:|---:|---:|
| 8 GPUs | 1 | 87.45 s | 1.830% |
| 16 GPUs | 2 | 110.45 s | 1.963% |

For this workload, moving from 8 GPUs on one node to 16 GPUs across two nodes produced negative scaling. The result is evidence for this tested configuration, not a universal node-count rule.

The retained Si1000 evidence set contains 39 accepted Quantum ESPRESSO trials.

## Validation

The reviewed repository snapshot recorded passing checks for:

- sweep-source validation;
- tracked Python compilation;
- tracked shell and Slurm syntax;
- Git object integrity;
- frozen-configuration review;
- raw-result verification for the retained Au(111) and Si1000 studies;
- experiment workbook and checksum validation.

## Claim boundary

Supported by the retained evidence:

- workload-specific Au(111) and Si1000 configuration freezes;
- the confirmed 6-GPU versus 8-GPU Si1000 latency result;
- negative 8-GPU-to-16-GPU scaling for the tested Si1000 node-boundary experiment;
- the accepted-trial counts and medians reported above.

Not established by this evidence:

- a universal Quantum ESPRESSO tuning policy;
- a universal GPU or node crossover point;
- a uniquely proven cause of the cross-node slowdown;
- a repeated formal speedup between every build variant;
- official-scale HiPAC competition performance.
