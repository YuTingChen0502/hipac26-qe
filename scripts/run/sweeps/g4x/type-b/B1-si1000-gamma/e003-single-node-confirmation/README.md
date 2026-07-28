# e003-single-node-confirmation

Status: complete; latency decision `CONFIRMED_R8`.

## Purpose

Independently confirm the `r6` versus `r8` result from
`e002-single-node-refinement` using a new Slurm allocation and a new
immutable bundle.

## Fixed conditions

- Case: `B1-si1000-gamma`
- Build: `G4X`
- Canonical B1 input unchanged
- Gamma-only: `nk=1`
- OpenMP threads: `12`
- One MPI rank per active GPU
- One H200 node
- Eight allocated GPUs
- Profiler disabled
- Node `25a-hgpn144` excluded

## Candidates

| Candidate | MPI ranks | Active GPUs | Layout |
|---|---:|---:|---|
| `r6` | 6 | 6 | `6` |
| `r8` | 8 | 8 | `8` |

## Trial order

The initial order is reversed relative to e002:

```text
r8, r6,
r6, r8,
r8, r6,
r6, r8,
r8, r6
```

Total: ten complete `pw.x` executions.

## Confirmation rule

The single-node candidate is confirmed only if:

1. e002 and e003 identify the same latency winner;
2. both experiment ratios exceed the 2% practical-tie threshold;
3. the combined e002+e003 result remains outside that threshold;
4. the winner takes at least 8 of 10 paired comparisons;
5. all 20 e002+e003 trials pass raw verification.
