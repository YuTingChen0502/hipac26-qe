# HiPAC26 Quantum ESPRESSO Performance Engineering

This repository documents my HiPAC26 work on Quantum ESPRESSO performance engineering for the NCHC Nano4 NVIDIA H200 platform.

The work focused on making performance experiments reproducible and interpretable before tuning: controlled builds, correctness checks, workload registration, run manifests, GPU/MPI placement, profiling, and repeated validation.

## What I worked on

- Built and validated Quantum ESPRESSO GPU execution paths with NVHPC/CUDA on H200.
- Developed a controlled run pipeline around manifests, case registries, rendered Slurm jobs, parsers, and result verification.
- Investigated workload-dependent GPU scaling, MPI rank placement, k-point pools, and node boundaries.
- Added profiling and raw-output checks so timing claims could be traced back to accepted runs.
- Preserved negative results and confirmation runs instead of reporting only the fastest configuration.

## Selected results

Data cutoff: 2026-07-29.

### Au(111), many-k-point workload

The tuning path covered k-point pools, ranks per pool, and topology-aware placement.

- 14 MPI ranks / GPUs across 2 nodes was retained for the workload.
- In the independent placement confirmation, the `8+6` rank layout reached a median of 18.72 s versus 20.81 s for the `7+7` layout.
- The final workload-specific configuration used 7 k-point pools with 2 ranks per pool.

### Si1000, Gamma-only workload

The scaling study showed that more GPUs were not automatically faster.

- Across two independent single-node studies, 8 GPUs reduced median latency from 104.295 s to 83.130 s versus 6 GPUs, a 20.293% reduction with 10/10 paired wins.
- In a separate node-boundary confirmation, 8 GPUs on one node reached 87.45 s median while 16 GPUs across two nodes reached 110.45 s.
- 39 Si1000 Quantum ESPRESSO trials were accepted into the final evidence set.

These are workload-specific results. They are not claims of a universal best configuration or official competition-scale performance.

See [`docs/results.md`](docs/results.md) for the condensed evidence summary and validation boundary.

## Engineering approach

The repository keeps the experiment machinery separate from generated runtime data:

```text
config/    machine, case, and manifest configuration
profiles/  Nano4 runtime profiles
schemas/   manifest and case-registry schemas
scripts/   build, run, sweep, parsing, and verification tools
tests/     controller and convergence tests
docs/      environment, validation, results, and historical evidence notes
```

The main controller is `scripts/qe_runctl.py`. It validates experiment metadata and rendered artifacts before submission, then parses and summarizes results after execution.

Representative supporting tools include:

- `scripts/qe_mapping_validator.py` for rank/GPU placement validation
- `scripts/qe_convergence.py` for convergence checks
- `scripts/verify_g4x_raw.py` for raw-result verification
- `scripts/collect_g4x_sweep.py` for sweep aggregation
- `scripts/run/sweeps/` for workload-specific experiments and retained result summaries

## Reproducibility and evidence

The final reviewed snapshot passed repository-wide checks covering tracked Python compilation, shell/Slurm syntax, sweep validation, Git object integrity, frozen-workload review, raw-result verification, and handoff checksum validation.

Historical handoff material under `docs/handoffs/` is retained as provenance for the experiment campaign, while the README and `docs/results.md` provide the public-facing technical summary.

## Scope

The repository supports claims about the validated Nano4/H200 experiments recorded here. It does not claim:

- a universal Quantum ESPRESSO tuning policy;
- a uniquely proven cause for every scaling result;
- a repeated formal speedup between all build variants;
- official-scale HiPAC performance.
