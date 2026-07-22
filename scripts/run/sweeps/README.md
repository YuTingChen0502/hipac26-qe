# G4X Type A/B Controlled Sweeps

These scripts use the tracked simple-runtime G4X launcher as the execution model:

- binary: `G4X-qe75-nvhpc259-h200-sm90-noelpa`
- one MPI rank per selected GPU;
- explicit local-rank to GPU mapping;
- isolated run directory and `out/` for every trial;
- `--exclude=25a-hgpn144`;
- full converged Type A/B inputs;
- no Nsight profiler in timing sweeps;
- no `-ntg`, `-nd`, or `-ndiag` sweep in this stage.

## Why the plan changed after the all-rank MPI profiles

### Type A, job 200508

- strict-converged wall: **21.53 s**;
- 14 ranks, 7 pools, 2 ranks per pool;
- non-init/finalize MPI time: mean **8.16 s/rank**, about **37.9%** of wall;
- `MPI_Barrier`: mean **3.96 s/rank**;
- rank 6 and rank 7 form the only contiguous two-rank pool split across nodes:
  - rank 6: node `25a-hgpn069`;
  - rank 7: node `25a-hgpn070`;
  - their `MPI_Waitall` times are **4.61 s** and **4.64 s**, while the all-rank median is **1.17 s**;
- per-rank point-to-point volume is about **76.7–77.1 GB** in each direction;
- QE reports `proc/nbgrp/npool/nimage = 2` and a serial diagonalization algorithm.

This supports three distinct questions:

1. Is `nk=7` better than `nk=1` at fixed 14 ranks?
2. Is one rank/GPU per k-point (7 ranks, one node) better than two ranks/GPUs per k-point (14 ranks, two nodes)?
3. If 14 ranks remain useful, can an `8+6` placement keep all contiguous two-rank pools node-local and beat the current `7+7` placement?

### Type B, job 200510

- strict-converged wall: **109.62 s**;
- 16 ranks, one Gamma-only pool;
- non-init/finalize MPI time: mean **63.80 s/rank**, about **58.2%** of wall;
- `MPI_Waitall`: mean **48.36 s/rank**, about **44.1%** of wall;
- every rank reports about **248.9 GB** point-to-point send and receive volume;
- every rank reports about **505.0 GB** `MPI_Allreduce` send and receive volume;
- QE reports `proc/nbgrp/npool/nimage = 16` and a serial diagonalization algorithm.

This makes 4/8/16-rank GPU strong scaling the first Type B experiment. `nk` remains fixed at 1.

## Files

- `g4x/type-a/A1-au111-manyk/e001-npool-screen/run.sbatch`
  - fixed 14 ranks / 14 GPUs;
  - `nk=7` baseline, `nk=1` primary, `nk=2` diagnostic;
  - three interleaved repeats each.

- `g4x/type-a/A1-au111-manyk/e002-resource-shape/run.sbatch`
  - fixed two-node allocation;
  - compares 7 ranks on one node with 14 ranks on two nodes;
  - default `TYPE_A_SCALE_NK=7`;
  - may be submitted with `--export=ALL,TYPE_A_SCALE_NK=1` if the coarse sweep selects `nk=1`.

- `g4x/type-a/A1-au111-manyk/e003-pool-placement/run.sbatch`
  - optional targeted follow-up for `nk=7`;
  - same 16-GPU allocation for both candidates;
  - compares rank layouts `7+7` and `8+6`;
  - the `8+6` layout keeps contiguous two-rank pool pairs node-local.

- `g4x/type-b/B1-si1000-gamma/e001-gpu-scaling/run.sbatch`
  - fixed two-node allocation;
  - compares 4, 8, and 16 ranks/GPUs;
  - `nk=1` throughout;
  - three interleaved repeats each.

- `lib/g4x_sweep_common.sh`
  - checksum guards;
  - isolated trial setup;
  - inherited clean rank/GPU mapping;
  - parser invocation;
  - continue-after-QE-failure behavior so the matrix is preserved.

- `../../collect_g4x_sweep.py`
  - verifies requested and actual pool shape;
  - verifies rank layout and mapping count;
  - verifies convergence, energy, SCF iteration count, and normal completion;
  - writes `results.csv`, `candidate-summary.csv`, and `collection-summary.json`.

## Execution order

Do not submit every script at once.

1. Run static validation and `sbatch --test-only`.
2. Submit `g4x/type-a/A1-au111-manyk/e001-npool-screen/run.sbatch`.
3. Inspect `results.csv` and `candidate-summary.csv`.
4. Submit Type A GPU scaling with the selected primary `nk`.
5. Run the topology probe only if `nk=7` and 14 ranks remain competitive.
6. Submit Type B 4/8/16 scaling.
7. Design OMP/rank-shape confirmation only after the scaling winners are known.

## Claim scope

The first-pass ratios are controlled same-allocation screening results, not final competition speedup claims. The final baseline and winner must receive a dedicated confirmation round with at least five interleaved repeats.


## Canonical directory hierarchy

Sweep sources use:

    <build-or-build-set>/
      <type>/
        <canonical-case>/
          <attempt-id>-<purpose>/
            run.sbatch
            README.md

The directory path stores experiment identity. The run.sbatch file stores
executable behavior.

Future result directories mirror this hierarchy under:

    /work/$USER/hipac26-qe-runs/sweeps/

Existing completed Stage 1 result directories remain at their historical
locations and are not moved solely for source-tree cleanup.

The collector records numerical comparability. The Slurm job status is
determined separately from trial execution and parser status.

See INDEX.md for the current experiment registry.
