# B1 e003 single-node confirmation results

Status: complete.

## Identity

- Case: `B1-si1000-gamma`
- Build: `G4X`
- Experiment: `e003-single-node-confirmation`
- Slurm job: `219031`
- Scheduler state: `COMPLETED`
- Scheduler exit: `0:0`
- Source commit: `62d1a0e8f92cc25e400b4a58e828498248643bb6`
- Standalone bundle: `/work/austinhpc25/hipac26-qe-bundles/B1-e003-confirm-62d1a0e-20260729_053053`
- Submission receipt: `/work/austinhpc25/hipac26-qe-runs/submission-receipts/B1-e003-confirmation-job-219031.txt`
- Run directory: `/work/austinhpc25/hipac26-qe-runs/sweeps/g4x/type-b/B1-si1000-gamma/e003-single-node-confirmation/job-219031`
- `nk=1`, `OMP=12`
- one MPI rank per active GPU
- one allocated H200 node with eight allocated GPUs

## e003 candidate results

| Candidate | Active GPUs | Raw wall times (s) | Median (s) | Mean (s) | CV | Median active GPU-s |
|---|---:|---|---:|---:|---:|---:|
| `r6` | 6 | 102.36,104.38,103.84,113.04,104.03 | 104.03 | 105.530 | 4.045% | 624.18 |
| `r8` | 8 | 82.15,92.62,81.73,82.71,83.41 | 82.71 | 84.524 | 5.406% | 661.68 |

Derived e003 result:

- `r8/r6` median ratio: `0.795059118`
- r8 latency reduction: `20.494%`
- latency winner: `r8`
- active-GPU-seconds winner: `r6`
- r6 active-GPU-seconds reduction relative to r8: `5.667%`

## e003 paired results

| Pair | r6 wall (s) | r8 wall (s) | r8-r6 (s) | Winner |
|---:|---:|---:|---:|---|
| 1 | 102.36 | 82.15 | -20.21 | `r8` |
| 2 | 104.38 | 92.62 | -11.76 | `r8` |
| 3 | 103.84 | 81.73 | -22.11 | `r8` |
| 4 | 113.04 | 82.71 | -30.33 | `r8` |
| 5 | 104.03 | 83.41 | -20.62 | `r8` |

- e003 r8 wins: `5/5`
- e003 r6 wins: `0/5`
- e003 ties: `0/5`
- e003 mean paired delta: `-21.006 s`

## Combined e002 + e003

| Candidate | Trials | Median (s) | Mean (s) | CV | Median active GPU-s | Median allocated GPU-s |
|---|---:|---:|---:|---:|---:|---:|
| `r6` | 10 | 104.295 | 107.148 | 4.118% | 625.77 | 834.36 |
| `r8` | 10 | 83.130 | 84.631 | 4.183% | 665.04 | 665.04 |

Combined evidence:

- e002 `r8/r6` ratio: `0.748269974`
- e003 `r8/r6` ratio: `0.795059118`
- combined `r8/r6` ratio: `0.797066015`
- combined r8 latency reduction: `20.293%`
- combined active-GPU-seconds winner: `r6`
- combined allocated-GPU-seconds winner: `r8`
- total r8 paired wins: `10/10`
- total r6 paired wins: `0/10`
- total ties: `0/10`

## Decision

Single-node latency decision: `CONFIRMED_R8`.

`r8` is confirmed as the B1 latency configuration. `r6` consumes
fewer active GPU-seconds in the combined evidence, while `r8`
consumes fewer allocated GPU-seconds because both candidates reserve
the same eight-GPU node and `r8` finishes substantially earlier.

The next experiment is `e004-node-boundary-confirmation`, comparing
the confirmed latency configuration `r8` against `r16` across two
nodes.

This conclusion is specific to `B1-si1000-gamma`.
