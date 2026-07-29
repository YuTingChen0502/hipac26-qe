# HiPAC 2026 QE — Optimization Mainline

Data cutoff: 2026-07-29

Scientific evidence source HEAD:

    71edc1780c145a1b0642848794914689ea146eb5

## Evidence ladder

    correct build
    -> reproducible artifact
    -> validated runtime
    -> workload-aware profiling
    -> case-specific tuning
    -> transferable policy
    -> official-scale confirmation

## Build roles

| Build | NVTX | Role |
|---|---:|---|
| G1 | OFF | reference runtime baseline |
| G1p | ON | G1 profiling twin |
| G4X | OFF | H200/SM90 runtime and tuning candidate |
| G4Xp | ON | G4X profiling twin |

## Type A tuning path

    k-point pools
    -> ranks per pool
    -> topology and placement

### Type A resource-shape result

| Candidate | Median | CV |
|---|---:|---:|
| r7 | 26.77 s | 0.753% |
| r14 | 21.17 s | 1.034% |

### Type A placement confirmation

| Experiment | Candidate | Median | CV |
|---|---|---:|---:|
| e003 | map7x7 | 21.07 s | 2.426% |
| e003 | map8x6 | 19.61 s | 1.507% |
| e004 | map7x7 | 20.81 s | 0.181% |
| e004 | map8x6 | 18.72 s | 2.444% |

Frozen A1:

    G4X, nk=7, 14 ranks/GPUs, 2 nodes,
    OMP=12, 2 ranks/pool, layout 8,6, map8x6

## Type B tuning path

    intra-node GPU scaling
    -> independent node-boundary regime

### e001 — coarse scaling

| Candidate | Median | CV | Active GPU-s |
|---|---:|---:|---:|
| r4 | 134.19 s | 0.292% | 536.76 |
| r8 | 82.98 s | 0.424% | 663.84 |
| r16 | 106.06 s | 1.274% | 1696.96 |

Latency winner: `r8`.

Active-GPU-seconds winner: `r4`.

Job 200733 was recovered without QE rerun. Its Slurm `FAILED` state
came from an overly strict collector tolerance, not invalid QE runs.

### e002 — single-node refinement

| Candidate | Median | Mean | CV | Active GPU-s |
|---|---:|---:|---:|---:|
| r6 | 111.27 s | 108.766 s | 4.013% | 667.62 |
| r8 | 83.26 s | 84.738 s | 3.187% | 666.08 |

    r8 latency reduction = 25.173%
    paired wins = r8 5/5
    valid trials = 10/10

### e003 — independent single-node confirmation

| Candidate | Median | Mean | CV | Active GPU-s |
|---|---:|---:|---:|---:|
| r6 | 104.03 s | 105.530 s | 4.045% | 624.18 |
| r8 | 82.71 s | 84.524 s | 5.406% | 661.68 |

    r8 latency reduction = 20.494%
    latency winner = r8
    active-GPU-seconds winner = r6
    paired wins = r8 5/5
    valid trials = 10/10

Combined e002 + e003:

    r6 median = 104.295 s
    r8 median = 83.130 s
    r8 latency reduction = 20.293%
    paired wins = r8 10/10
    decision = CONFIRMED_R8

### e004 — node-boundary confirmation

| Candidate | Active nodes | Median | Mean | CV | Active GPU-s |
|---|---:|---:|---:|---:|---:|
| r8 | 1 | 87.45 s | 86.700 s | 1.830% | 699.60 |
| r16 | 2 | 110.45 s | 110.416 s | 1.963% | 1767.20 |

    r16/r8 ratio = 1.263007433
    r8 latency reduction = 20.824%
    paired wins = r8 5/5
    valid trials = 10/10

Combined e001 + e004:

    r8 median = 85.300 s
    r16 median = 108.505 s
    r16/r8 ratio = 1.272039859

Frozen B1:

    FROZEN_R8_ONE_NODE
    G4X, nk=1, 8 ranks/GPUs, 1 node, OMP=12

Accepted B1 QE trials:

    39

## Next scientific mainline

1. repeated and interleaved G1-versus-G4X runtime confirmation;
2. official-scale transfer screening;
3. profiling only when a new scaling decision needs diagnosis;
4. remaining workload coverage;
5. final competition packaging.

No fixed B1 e005 is required.

## Claim boundary

Supported:

- A1 and B1 case-specific freezes;
- B1 r8 latency confirmation across e002 and e003;
- B1 cross-node negative scaling across e001 and e004;
- 39 accepted B1 QE trials.

Not supported:

- universal Type A or Gamma-only parameters;
- universal node crossover;
- uniquely proven cause of cross-node negative scaling;
- repeated formal G1-to-G4X speedup;
- official-scale competition performance.
