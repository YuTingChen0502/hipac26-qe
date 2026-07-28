# e002-single-node-refinement

Status: launcher smoke passed; QE refinement not yet submitted.

## Question

For `B1-si1000-gamma`, is the single-node latency and efficiency
sweet spot six active GPUs or eight active GPUs?

## Fixed conditions

- Build: `G4X`
- Input: canonical `typeB-si1000-gamma/pw.in`
- Gamma-only: `nk=1`
- OpenMP threads: `12`
- One MPI rank per active GPU
- One allocated H200 node
- Eight allocated GPUs
- Profiler disabled
- Node `25a-hgpn144` excluded

## Candidates

| Candidate | MPI ranks | Active GPUs | Active layout |
|---|---:|---:|---|
| `r6` | 6 | 6 | `6` |
| `r8` | 8 | 8 | `8` |

## Trial design

Five paired, interleaved trials per candidate:

```text
r6, r8,
r8, r6,
r6, r8,
r8, r6,
r6, r8
```

Total: ten complete pw.x executions.

## Decision metrics

- median and mean PWSCF wall time;
- coefficient of variation;
- paired wins and paired differences;
- active GPU-seconds;
- allocated GPU-seconds;
- final energy and SCF iteration consistency.

Before the QE sweep, the launcher smoke must validate the r6 and
r8 explicit host:slots routes and rank-to-GPU mappings.
