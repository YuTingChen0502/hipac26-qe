# Type A Launch Configuration Freeze

## Scope

This freeze applies to the exact controlled tuning case
`A1-au111-manyk` under the tested G4X environment.
It is not a universal rule for every many-k QE input.

## Frozen configuration

| Field | Value |
|---|---|
| Build | G4X |
| QE | 7.5 |
| NVHPC | 25.9 |
| k-points | 7 |
| k-point pools (`nk`) | 7 |
| MPI ranks | 14 |
| Active GPUs | 14 |
| Allocated nodes | 2 |
| OpenMP threads | 12 |
| Ranks per pool | 2 |
| Active rank layout | 8,6 |
| Placement | map8x6 |

## Evidence chain

- e001 selected `nk=7` as the strongest tested direction.
- e002 job `203455` selected r14 over r7.
- e003 job `203897` selected map8x6 over map7x7.
- e004 job `203925` independently confirmed map8x6.
- e004 improvement: `10.043%`.
- combined e003 and e004 improvement: `7.506%`.
- matched-repeat wins: `5/5`.

## Claim boundary

Supported:

    For A1-au111-manyk under the tested G4X environment,
    nk=7, 14 ranks and an 8+6 active-rank placement were
    the lowest-latency tested configuration.

Not supported:

    Every Type A or every many-k QE input should use this
    configuration without transfer screening.
