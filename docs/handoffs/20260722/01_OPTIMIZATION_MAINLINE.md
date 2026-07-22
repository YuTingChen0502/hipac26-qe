# HiPAC 2026 QE — Optimization Mainline Handoff

Data cutoff: 2026-07-22

## 1. Project objective

The execution and optimization ladder is:

    correct build
    -> reproducible artifact
    -> validated runtime
    -> workload-aware profiling
    -> case-specific tuning
    -> transferable policy
    -> official-scale confirmation

## 2. Build roles

| Build | NVTX | Role |
|---|---:|---|
| G1 | OFF | reference runtime baseline |
| G1p | ON | G1 profiling twin |
| G4X | OFF | H200 and SM90 runtime/tuning candidate |
| G4Xp | ON | G4X profiling twin |

Runtime evidence compares G1 and G4X.
Mechanism diagnosis compares G1p and G4Xp.
Profiler-active wall time is not formal runtime evidence.

## 3. Two optimization paths

### Type A many-k

    many-k
    -> k-point pool count
    -> ranks per pool
    -> node and rank placement

### Type B Gamma-only

    Gamma-only
    -> single-node GPU scaling
    -> node-boundary regime

Type A exposes k-point concurrency. Type B has only one Gamma point and
therefore does not obtain concurrency by increasing nk.

## 4. Type A experiment ledger

### e001 — npool screening

Purpose:

    Determine the pool direction for the seven-k-point A1 input.

Result:

    nk=7 selected as the strongest tested Stage 1 direction.

Known nk=7 Stage 1 wall times:

    20.35, 20.59, 21.41 seconds
    median 20.59 seconds

### e002 — resource shape

Question:

    With nk=7 fixed, use one or two ranks per pool?

Candidates:

    r7:
      7 ranks
      7 GPUs
      1 active node
      1 rank per pool

    r14:
      14 ranks
      14 GPUs
      2 active nodes
      2 ranks per pool

Job 203322:

    Infrastructure-invalid attempt.
    Slurm spool location broke runtime helper discovery.
    QE execution count was zero.
    It contains no scientific evidence.

Job 203455:

    Six QE calculations completed.
    The Slurm job later failed because the bundled parser omitted
    qe_convergence.py.
    Scientific results were recovered from preserved qe.out files.
    No QE rerun was required.

Results:

| Candidate | Wall times | Median | CV |
|---|---|---:|---:|
| r14 | 21.17, 21.22, 20.82 | 21.17 s | 1.034% |
| r7 | 27.08, 26.77, 26.70 | 26.77 s | 0.753% |

    r14/r7 = 0.790811
    r14 latency improvement = 20.919%

r14 is the latency choice. r7 remains more efficient in GPU-seconds.

### e003 — pool placement

Fixed conditions:

    14 MPI ranks
    14 active GPUs
    2 allocated nodes
    nk=7
    2 ranks per pool

Candidates:

    map7x7: active rank layout 7,7
    map8x6: active rank layout 8,6

Job:

    203897
    COMPLETED
    exit 0:0
    six of six trials valid

Results:

| Candidate | Wall times | Median | CV |
|---|---|---:|---:|
| map7x7 | 21.88, 20.92, 21.07 | 21.07 s | 2.426% |
| map8x6 | 19.47, 20.04, 19.61 | 19.61 s | 1.507% |

    map8x6/map7x7 = 0.930707
    map8x6 improvement = 6.929%

### e004 — independent placement confirmation

Job:

    203925
    COMPLETED
    exit 0:0
    ten of ten QE trials completed
    execution failures = 0

The initial offline verifier falsely returned energy_reference_missing
because its energy-count condition was still hard-coded to six trials.
The canonical verifier was corrected to use expected_trials.
e002, e003 and e004 all passed offline regression.
No QE job was resubmitted.

Results:

| Candidate | Wall times | Median | Mean | CV |
|---|---|---:|---:|---:|
| map7x7 | 20.80, 20.81, 20.82, 20.88, 20.78 | 20.81 s | 20.818 s | 0.181% |
| map8x6 | 18.72, 18.44, 19.10, 19.52, 18.46 | 18.72 s | 18.848 s | 2.444% |

    e004 ratio = 0.899567516
    e004 improvement = 10.043%
    paired map8x6 wins = 5/5

Combined e003 and e004:

    map7x7 median = 20.850 seconds
    map8x6 median = 19.285 seconds
    ratio = 0.924940048
    improvement = 7.506%

## 5. Frozen Type A configuration

Scope:

    A1-au111-manyk under the tested G4X environment

Frozen values:

| Field | Value |
|---|---|
| Build | G4X |
| nk | 7 |
| MPI ranks | 14 |
| Active GPUs | 14 |
| Allocated nodes | 2 |
| OpenMP threads | 12 |
| Ranks per pool | 2 |
| Active layout | 8,6 |
| Placement | map8x6 |

This is case-derived. Official-scale Type A inputs still require transfer
screening.

## 6. Next mainline

Type A is frozen for A1.

Next work:

    Type B Gamma-only
    -> recover existing 4, 8 and 16 GPU Stage 1 evidence
    -> design single-node 6 versus 8 GPU refinement
    -> determine whether 8 GPUs remains the latency winner
    -> treat cross-node scaling as an independent regime

Do not blindly rerun the completed 4/8/16 sweep.

## 7. Claim boundary

Supported:

- G4X is the active H200 and SM90 runtime candidate.
- A1 freezes to nk=7, 14 ranks and map8x6.
- e003 and e004 independently favor map8x6.
- For the tested Gamma-only Type B case, the single-node direction is
  stronger than the tested 16-GPU two-node direction.

Not yet supported:

- universal parameters for all Type A inputs;
- universal parameters for all Type B inputs;
- final repeated G1-to-G4X speedup;
- official-scale competition performance;
- native/container equivalence;
- a universal node-boundary crossover.
