# HiPAC 2026 QE — Exact Evidence Manifest

Generated branch:

    refactor/simple-runtime

Generated HEAD:

    fd46334bc3a11f5ab0a922238017237ad8a1f317

## Repository and build identity

Repository:

    /work/$USER/hipac26-qe

G4X executable:

    /work/$USER/hipac26-qe-builds/
    G4X-qe75-nvhpc259-h200-sm90-noelpa/install/bin/pw.x

G4X executable SHA-256:

    64968da5119d9e33b8639ad4e60e449b379f4f254ae9d09df2de1e0974d5a473

Type A input:

    /work/$USER/hipac26-qe-cases/typeA-au111-manyk/pw.in

Type A input SHA-256:

    7c9354016502431300025747b73aebe9ae2b3a6766c811fe0bf0e8a8066b03d2

## Relevant repository source

    scripts/verify_g4x_raw.py
    scripts/run/sweeps/render_standalone_bundle.py
    scripts/run/sweeps/lib/g4x_sweep_common.sh

    scripts/run/sweeps/g4x/type-a/A1-au111-manyk/
      e002-resource-shape/
      e003-pool-placement/
      e004-placement-confirmation/
      type-a-freeze.md
      frozen-launch.env

## Jobs

| Experiment | Job ID | Scheduler state | Scientific classification |
|---|---:|---|---|
| e002 initial | 203322 | FAILED | infrastructure invalid; QE count 0 |
| e002 retry | 203455 | FAILED | six valid QE runs; parser package failed |
| e003 | 203897 | COMPLETED 0:0 | execution and raw verification valid |
| e004 | 203925 | COMPLETED 0:0 | execution valid; verifier recovered offline |

## Run directories

    /work/austinhpc25/hipac26-qe-runs/sweeps/g4x/type-a/A1-au111-manyk/
      e002-resource-shape/job-203455
      e003-pool-placement/job-203897
      e004-placement-confirmation/job-203925

## Authoritative raw-verification directories

    /work/austinhpc25/hipac26-qe-runs/sweeps/g4x/type-a/A1-au111-manyk/
      e002-resource-shape/job-203455/raw-verification-v2
      e003-pool-placement/job-203897/raw-verification-v2
      e004-placement-confirmation/job-203925/raw-verification-v2

Each directory contains:

    raw-trial-results.csv
    raw-candidate-summary.csv
    raw-verification-summary.txt

## Receipts

    /work/austinhpc25/hipac26-qe-runs/submission-receipts/
      A1-e002-standalone-job-203455.txt
      A1-e003-raw-job-203897.txt
      A1-e004-raw-job-203925.txt

## Slurm logs

    /work/austinhpc25/hipac26-qe-runs/slurm/
      A1-e003-place-203897.out
      A1-e003-place-203897.err
      A1-e004-confirm-203925.out
      A1-e004-confirm-203925.err

## Submitted standalone bundles

    /work/$USER/hipac26-qe-bundles/
      A1-e003-raw-e15da77-20260722_205002
      A1-e004-confirm-7a5a04c-20260722_212148

Submitted bundles are immutable historical evidence.

The e004 bundled verifier contains the original six-trial condition.
The corrected authoritative verifier is:

    scripts/verify_g4x_raw.py

## Repository checkpoint

    fd46334 (HEAD -> refactor/simple-runtime) Recover e004 and freeze A1 Type A placement
    7a5a04c Add A1 placement confirmation experiment
    4994dfc Record A1 e003 pool-placement result
    e15da77 Add raw QE sweep verifier
    0be9c95 Record A1 e002 and bundle parser dependency
    d6cede2 Add standalone sweep bundle renderer
    361ba11 Fix sweep helper path under Slurm
    175ddd1 Prepare A1 resource-shape sweep
    846bba0 Add G1 reference runtime scripts for Types A B D E F
    ea44c40 Exclude unstable Nano4 node 25a-hgpn144
    9c52ba5 Revert "Pin runtime jobs to canonical nodes and reserve Type A GPUs"
    fd4555c Pin runtime jobs to canonical nodes and reserve Type A GPUs
    9335b5d Add G4X and G4Xp runtime scripts for Types A B D E F
    e5369b5 Revert "Add simple two-node QE runtime"
    c87f72a Add simple two-node QE runtime
