# B1 e001 GPU scaling results

Status: recovered from retained raw outputs; no QE rerun.

## Identity

- Case ID: `B1-si1000-gamma`
- Historical input directory: `typeB-si1000-gamma`
- Build: `G4X`
- Experiment ID: `e001-gpu-scaling`
- Historical Slurm job: `200733`
- Fixed `nk`: `1`
- OpenMP threads: `12`
- Rank/GPU model: one MPI rank per active GPU

## Validation

The authoritative offline raw verifier reports:

- expected trials: 9
- valid trials: 9
- failed trials: 0
- all QE exit codes: zero
- all trials contain `JOB DONE.`
- all trials used one Gamma k-point
- all trials completed 20 SCF iterations
- all copied inputs matched the canonical B1 input SHA-256
- all rank counts and node layouts matched their candidates
- energy tolerance: `1e-7 Ry`

The historical Slurm `FAILED` state is classified as a
collector-policy false failure, not a QE execution failure.

## Results

| Candidate | Nodes | Active GPUs | Raw wall times (s) | Median (s) | Mean (s) | CV | Median active GPU-s |
|---|---:|---:|---|---:|---:|---:|---:|
| `r4` | 1 | 4 | 133.93,134.70,134.19 | 134.19 | 134.273 | 0.292% | 536.76 |
| `r8` | 1 | 8 | 82.76,83.45,82.98 | 82.98 | 83.063 | 0.424% | 663.84 |
| `r16` | 2 | 16 | 106.51,103.99,106.06 | 106.06 | 105.520 | 1.274% | 1696.96 |

Derived results:

- `r8` reduces median latency by 38.162% relative to `r4`.
- `r8` reduces median latency by 21.761% relative to `r16`.
- `r16` uses 2.556x the median active
  GPU-seconds of `r8`.

## Decision

- Tested latency winner: `r8`.
- Tested active-GPU-seconds winner: `r4`.
- The tested two-node `r16` candidate loses to `r8` in both
  latency and active GPU-seconds.

The next experiment is a controlled single-node `r6` versus `r8`
refinement. This result is specific to `B1-si1000-gamma`; it is not
a universal Gamma-only optimum.
