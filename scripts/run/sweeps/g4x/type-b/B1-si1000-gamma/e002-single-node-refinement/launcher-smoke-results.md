# B1 e002 launcher-smoke result

Status: passed.

## Identity

- Slurm job: `218990`
- Scheduler state: `COMPLETED`
- Exit code: `0:0`
- Source commit: `c855d8c9c6d02a274702956e689323ab8aec175b`
- Standalone bundle: `/work/austinhpc25/hipac26-qe-bundles/B1-e002-smoke-c855d8c-20260729_044514`
- Submission receipt: `/work/austinhpc25/hipac26-qe-runs/submission-receipts/B1-e002-launcher-smoke-job-218990.txt`
- Run directory: `/work/austinhpc25/hipac26-qe-runs/sweeps/g4x/type-b/B1-si1000-gamma/e002-single-node-refinement/launcher-smoke/job-218990`
- Allocated node: `25a-hgpn005`

## Shapes validated

| Shape | Expected ranks | Mapping files | Unique hosts | Unique GPUs | Result |
|---|---:|---:|---:|---:|---|
| `r6` | 6 | 6 | 1 | 6 | PASS |
| `r8` | 8 | 8 | 1 | 8 | PASS |

Both routes used explicit `host:slots` placement on one allocated
H200 node. The smoke validated MPI launch and one-rank-per-GPU mapping.

No Quantum ESPRESSO calculation was executed. The result authorizes
submission preparation for the ten-trial `r6` versus `r8`
single-node refinement; it is not scientific runtime evidence.
