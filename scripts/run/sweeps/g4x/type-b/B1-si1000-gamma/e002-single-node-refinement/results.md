# B1 e002 single-node refinement results

Status: complete; independent confirmation pending.

## Identity

- Case: `B1-si1000-gamma`
- Build: `G4X`
- Experiment: `e002-single-node-refinement`
- Slurm job: `218992`
- Scheduler state: `COMPLETED`
- Scheduler exit: `0:0`
- Source commit: `c855d8c`
- Standalone bundle: `/work/austinhpc25/hipac26-qe-bundles/B1-e002-refine-c855d8c-20260729_044514`
- Submission receipt: `/work/austinhpc25/hipac26-qe-runs/submission-receipts/B1-e002-refinement-job-218992.txt`
- Run directory: `/work/austinhpc25/hipac26-qe-runs/sweeps/g4x/type-b/B1-si1000-gamma/e002-single-node-refinement/job-218992`
- Fixed `nk`: `1`
- OpenMP threads: `12`
- One MPI rank per active GPU
- One allocated node and eight allocated GPUs

## Validation

- Expected QE trials: 10
- Valid QE trials: 10
- Failed QE trials: 0
- Raw verification: PASS
- All trials used the canonical B1 input
- All trials completed 20 SCF iterations
- All rank counts and single-node layouts matched their candidates
- Energy tolerance: `1e-7 Ry`

## Candidate results

| Candidate | Active GPUs | Raw wall times (s) | Median (s) | Mean (s) | CV | Median active GPU-s | Median allocated GPU-s |
|---|---:|---|---:|---:|---:|---:|---:|
| `r6` | 6 | 112.59,111.27,104.21,111.94,103.82 | 111.27 | 108.766 | 4.013% | 667.62 | 890.16 |
| `r8` | 8 | 85.65,83.26,83.00,89.09,82.69 | 83.26 | 84.738 | 3.187% | 666.08 | 666.08 |

Derived:

- `r8/r6` median ratio: `0.748269974`
- `r8` latency reduction relative to `r6`: `25.173%`
- Preliminary latency winner: `r8`
- Active-GPU-seconds winner: `r8`
- Practical-tie threshold: `±2%`
- Practical tie: `NO`

## Paired results

The delta is `r8 - r6`; a negative value favors `r8`.

| Pair | r6 wall (s) | r8 wall (s) | Delta (s) | Winner |
|---:|---:|---:|---:|---|
| 1 | 112.59 | 85.65 | -26.94 | `r8` |
| 2 | 111.27 | 83.26 | -28.01 | `r8` |
| 3 | 104.21 | 83.00 | -21.21 | `r8` |
| 4 | 111.94 | 89.09 | -22.85 | `r8` |
| 5 | 103.82 | 82.69 | -21.13 | `r8` |

Paired summary:

- `r6` wins: 0/5
- `r8` wins: 5/5
- exact ties: 0/5
- mean paired delta: -24.028 s

## Decision

`r8` is the preliminary latency winner in e002. This remains a single-allocation result and must be independently confirmed by e003 before B1 is frozen.

This result is specific to `B1-si1000-gamma` under the tested G4X
and Nano4 H200 environment. It does not establish a universal
Gamma-only GPU count.
