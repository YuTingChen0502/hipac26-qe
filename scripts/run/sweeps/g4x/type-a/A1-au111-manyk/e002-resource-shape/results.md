# e002 Resource-Shape Result

## Provenance

- Slurm job: `203455`
- Source: immutable standalone bundle
- QE execution: six of six trials completed normally
- QE exit codes: all zero
- SCF convergence: all six trials converged in 15 iterations
- Post-processing incident: bundled parser omitted `qe_convergence.py`
- Recovery method: direct extraction from preserved `qe.out`
- QE rerun required: no

## Results

| Candidate | Raw wall times | Median | Mean | CV | Median GPU-seconds |
|---|---:|---:|---:|---:|---:|
| r14 | 21.17, 21.22, 20.82 | 21.170 s | 21.070 s | 1.034% | 296.380 |
| r7 | 27.08, 26.77, 26.70 | 26.770 s | 26.850 s | 0.753% | 187.390 |

- `r14 / r7` median ratio: `0.790811`
- r14 latency improvement over r7: `20.919%`
- r14 GPU-seconds increase over r7: `58.162%`
- Median-energy difference: `5.599995347e-07 Ry`
- Numerical tolerance: `1e-6 Ry`

## Decision

`r14` is the latency winner and remains numerically comparable.

Proceed to `e003-pool-placement` to compare 7+7 and 8+6
placement while keeping 14 active ranks and `nk=7` fixed.

The e002 conclusion is about latency. The r7 shape remains more
resource-efficient in GPU-seconds.
