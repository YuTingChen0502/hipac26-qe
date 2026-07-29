# HiPAC 2026 QE — Incident and Validation Ledger

## Classification model

Always separate:

1. scheduler state;
2. QE execution validity;
3. parser and collector validity;
4. numerical equivalence;
5. scientific acceptance.

A Slurm `FAILED` state alone does not prove a QE failure.

## Type A

### Job 203322

- infrastructure failure;
- zero QE executions;
- invalid scientific attempt;
- replaced by immutable bundle submission.

### Job 203455

- six QE executions valid;
- bundle omitted `qe_convergence.py`;
- raw outputs recovered without QE rerun.

### Job 203925

- ten QE executions valid;
- offline verifier initially assumed six energy values;
- verifier corrected and raw outputs reprocessed without QE rerun.

## Type B

### Job 200733

- scheduler state: FAILED;
- QE executions: 9/9 valid;
- mapping: valid;
- root cause: collector tolerance `1e-8 Ry` was stricter than the B1
  convergence threshold;
- recovery: raw verification;
- QE rerun: no.

### Job 218990

- launcher smoke only;
- QE executions: zero;
- r6 and r8 rank/GPU mappings passed.

### Job 218992

- scheduler: COMPLETED 0:0;
- trials: 10/10 valid;
- decision: preliminary r8 latency winner.

### Job 219031

- scheduler: COMPLETED 0:0;
- trials: 10/10 valid;
- latency winner: r8;
- active-GPU-seconds winner: r6;
- an incorrect reporting gate required both winners to be identical;
- reporting gate corrected;
- no QE rerun.

### Job 219063

- scheduler: COMPLETED 0:0;
- trials: 10/10 valid;
- r8 layout: 8;
- r16 layout: 8,8;
- decision: FROZEN_R8_ONE_NODE.

## Architecture rules

Submitted bundles are immutable and must include:

- runtime source;
- helper;
- parser and parser dependencies;
- environment script;
- collector;
- bundle metadata;
- SHA-256 manifest.

Execution acceptance checks:

- expected and actual trial count;
- QE exit code;
- `JOB DONE`;
- convergence marker;
- PWSCF wall marker;
- parser exit;
- input SHA-256;
- rank/GPU mapping;
- expected node layout.
