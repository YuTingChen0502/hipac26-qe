# HiPAC 2026 QE Handoff — Read First

Data cutoff: 2026-07-22

Repository:

    /work/$USER/hipac26-qe

Branch:

    refactor/simple-runtime

HEAD at generation:

    fd46334bc3a11f5ab0a922238017237ad8a1f317

## Source priority

Use sources in this order:

1. 20260722 optimization mainline handoff.
2. 20260722 exact evidence manifest.
3. 20260722 incident and validation ledger.
4. Packaged raw evidence.
5. Current nano4 read-only state.
6. 20260721 full project handoff.
7. Historical inventory and weekly deck.

Current nano4 evidence overrides older documentation when they conflict.
Any discrepancy must be recorded rather than silently reconciled.

## Safety boundary for the next chat

Before comprehension is confirmed, do not:

- modify the repository;
- git add, commit or push;
- submit Slurm jobs;
- rebuild QE;
- rerun e001 through e004;
- delete, move or rewrite run artifacts;
- reuse blocked or superseded bundles.

The first response must be a comprehension check only.
