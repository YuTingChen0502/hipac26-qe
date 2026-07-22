# e003 Pool-Placement Result

## Purpose

Compare two rank placements while holding the computational
configuration fixed:

- 14 active MPI ranks
- 14 active GPUs
- 2 allocated nodes
- `nk=7`
- 2 ranks per k-point pool
- three repeats per candidate

## Candidates

- `map7x7`: 7 ranks on each node
- `map8x6`: 8 ranks on one node and 6 ranks on the other

## Results

| Candidate | Valid trials | Raw wall times | Median | Mean | CV |
|---|---:|---:|---:|---:|---:|
| map7x7 | 3 | 21.88,20.92,21.07 | 21.070 s | 21.290 s | 2.426% |
| map8x6 | 3 | 19.47,20.04,19.61 | 19.610 s | 19.707 s | 1.507% |

- `map8x6 / map7x7` median ratio: `0.930707167`
- Latency winner: `map8x6`
- Raw verification: `PASS`

## Provenance

- Slurm job: `203897`
- Bundle: `/work/austinhpc25/hipac26-qe-bundles/A1-e003-raw-e15da77-20260722_205002`
- Verification source: raw QE output, QE exit codes and rank mappings
- Parser gate: disabled
- Collector gate: disabled
