# HiPAC 2026 QE — Exact Evidence Manifest

Data cutoff:

    2026-07-29

Scientific evidence source HEAD:

    71edc1780c145a1b0642848794914689ea146eb5

## Identity

G4X executable SHA-256:

    64968da5119d9e33b8639ad4e60e449b379f4f254ae9d09df2de1e0974d5a473

Type A input SHA-256:

    7c9354016502431300025747b73aebe9ae2b3a6766c811fe0bf0e8a8066b03d2

Type B input SHA-256:

    3efd3830a380a185e76124e8d7beba2111ea6c1333d8e946bbac199c1c06a340

## Type A job ledger

| Experiment | Job | Scheduler | Scientific classification |
|---|---:|---|---|
| e002 initial | 203322 | FAILED | infrastructure invalid; QE count 0 |
| e002 retry | 203455 | FAILED | six valid QE runs; parser package invalid |
| e003 | 203897 | COMPLETED 0:0 | six valid trials |
| e004 | 203925 | COMPLETED 0:0 | ten valid trials |

## Type B job ledger

| Experiment | Job | Scheduler | Scientific classification |
|---|---:|---|---|
| e001 | 200733 | FAILED | nine valid QE runs; collector tolerance invalid |
| e002 launcher smoke | 218990 | COMPLETED 0:0 | mapping only; QE count 0 |
| e002 | 218992 | COMPLETED 0:0 | ten valid trials |
| e003 | 219031 | COMPLETED 0:0 | ten valid trials |
| e004 | 219063 | COMPLETED 0:0 | ten valid trials |

## Authoritative raw verification

### Type A

    /work/austinhpc25/hipac26-qe-runs/sweeps/g4x/type-a/A1-au111-manyk/e002-resource-shape/job-203455/raw-verification-v2
    /work/austinhpc25/hipac26-qe-runs/sweeps/g4x/type-a/A1-au111-manyk/e003-pool-placement/job-203897/raw-verification-v2
    /work/austinhpc25/hipac26-qe-runs/sweeps/g4x/type-a/A1-au111-manyk/e004-placement-confirmation/job-203925/raw-verification-v2

### Type B

    /work/austinhpc25/hipac26-qe-runs/g4x-sweeps/type_b_gpu_scaling/job-200733/raw-verification-v2
    /work/austinhpc25/hipac26-qe-runs/sweeps/g4x/type-b/B1-si1000-gamma/e002-single-node-refinement/job-218992/raw-verification-v2
    /work/austinhpc25/hipac26-qe-runs/sweeps/g4x/type-b/B1-si1000-gamma/e003-single-node-confirmation/job-219031/raw-verification-v2
    /work/austinhpc25/hipac26-qe-runs/sweeps/g4x/type-b/B1-si1000-gamma/e004-node-boundary-confirmation/job-219063/raw-verification-v2

Each authoritative directory contains:

    raw-trial-results.csv
    raw-candidate-summary.csv
    raw-verification-summary.txt

## Exact B1 results

### e001

    r4 median = 134.19 s
    r8 median = 82.98 s
    r16 median = 106.06 s
    latency winner = r8
    active-GPU-seconds winner = r4
    valid trials = 9/9

### e002

    r6 median = 111.27 s
    r8 median = 83.26 s
    r8 reduction = 25.173%
    paired wins = 5/5
    valid trials = 10/10

### e003

    r6 median = 104.03 s
    r8 median = 82.71 s
    r8 reduction = 20.494%
    latency winner = r8
    active-GPU-seconds winner = r6
    paired wins = 5/5
    valid trials = 10/10

### e004

    r8 median = 87.45 s
    r16 median = 110.45 s
    r16/r8 ratio = 1.263007433
    r8 reduction = 20.824%
    paired wins = 5/5
    valid trials = 10/10

Accepted B1 QE trials:

    39

## Frozen configurations

A1:

    G4X, nk=7, 14 ranks/GPUs, 2 nodes,
    OMP=12, layout 8,6, map8x6

B1:

    G4X, nk=1, 8 ranks/GPUs, 1 node,
    OMP=12, layout 8

B1 freeze commit:

    71edc1780c145a1b0642848794914689ea146eb5
