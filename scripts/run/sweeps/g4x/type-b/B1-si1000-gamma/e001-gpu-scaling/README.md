# e001-gpu-scaling

Status: complete

Research question:

For the current Type B Si1000 Gamma-only case, which tested GPU count
provides the shortest wall time?

Recovered results:

| GPUs | Nodes | Raw PWSCF wall times | Median | Median GPU-s |
|---:|---:|---|---:|---:|
| 4 | 1 | 133.93, 134.70, 134.19 s | 134.19 s | 536.76 |
| 8 | 1 | 82.76, 82.98, 83.45 s | 82.98 s | 663.84 |
| 16 | 2 | 103.99, 106.06, 106.51 s | 106.06 s | 1696.96 |

Decision:

    8 GPUs is the tested wall-time optimum.
    4 GPUs has the lowest tested GPU-second cost.
    16 GPUs is beyond the effective strong-scaling point for this case.

Historical result directory:

    /work/$USER/hipac26-qe-runs/g4x-sweeps/type_b_gpu_scaling/job-200733

The historical directory remains in place. It is not moved or regenerated
by the source-tree refactor.
