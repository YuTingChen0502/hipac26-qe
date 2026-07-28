# B1 e004 node-boundary confirmation results

Status: complete.

## Identity

- Case: `B1-si1000-gamma`
- Build: `G4X`
- Experiment: `e004-node-boundary-confirmation`
- Slurm job: `219063`
- Scheduler state: `COMPLETED`
- Scheduler exit: `0:0`
- Source commit: `cbea249124ff799efe012bc73506ed936224ce13`
- Standalone bundle: `/work/austinhpc25/hipac26-qe-bundles/B1-e004-boundary-cbea249-20260729_060740`
- Submission receipt: `/work/austinhpc25/hipac26-qe-runs/submission-receipts/B1-e004-boundary-job-219063.txt`
- Run directory: `/work/austinhpc25/hipac26-qe-runs/sweeps/g4x/type-b/B1-si1000-gamma/e004-node-boundary-confirmation/job-219063`
- `nk=1`, `OMP=12`
- one MPI rank per active GPU

## Results

| Candidate | Nodes | Active GPUs | Raw wall times (s) | Median (s) | Mean (s) | CV | Active GPU-s |
|---|---:|---:|---|---:|---:|---:|---:|
| `r8` | 1 | 8 | 87.73,87.72,87.45,86.62,83.98 | 87.45 | 86.700 | 1.830% | 699.60 |
| `r16` | 2 | 16 | 107.45,113.33,111.29,110.45,109.56 | 110.45 | 110.416 | 1.963% | 1767.20 |

- `r16/r8` median ratio: `1.263007433`
- r8 latency reduction relative to r16: `20.824%`
- latency winner: `r8`
- active-GPU-seconds winner: `r8`

## Paired results

| Pair | r8 wall (s) | r16 wall (s) | r16-r8 (s) | Winner |
|---:|---:|---:|---:|---|
| 1 | 87.73 | 107.45 | +19.72 | `r8` |
| 2 | 87.72 | 113.33 | +25.61 | `r8` |
| 3 | 87.45 | 111.29 | +23.84 | `r8` |
| 4 | 86.62 | 110.45 | +23.83 | `r8` |
| 5 | 83.98 | 109.56 | +25.58 | `r8` |

- r8 wins: `5/5`
- r16 wins: `0/5`
- ties: `0/5`

## Combined e001 + e004

- combined r8 trials: `8`
- combined r16 trials: `8`
- combined r8 median: `85.30 s`
- combined r16 median: `108.50 s`
- combined `r16/r8` ratio: `1.272039859`

## Decision

Node-boundary decision: `FROZEN_R8_ONE_NODE`.

For the tested B1 workload, crossing from one node and eight GPUs to
two nodes and sixteen GPUs does not improve latency and substantially
increases active GPU-seconds.
