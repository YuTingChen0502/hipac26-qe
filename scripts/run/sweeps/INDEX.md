# Sweep Experiment Index

Canonical hierarchy:

    <build-or-build-set>/
      <type>/
        <canonical-case>/
          <attempt-id>-<purpose>/
            run.sbatch
            README.md

Current experiments:

| Build | Type | Case | Attempt | Status | Current result |
|---|---|---|---|---|---|
| G4X | A | typeA-au111-manyk | a001-nk-coarse | complete | nk=7 |
| G4X | A | typeA-au111-manyk | a002-gpu-scaling | planned | pending |
| G4X | A | typeA-au111-manyk | a003-pool-topology | conditional | pending |
| G4X | B | B1-si1000-gamma | e001-gpu-scaling | complete | r8 tested latency winner; r4 active-GPU-s winner |
| G4X | B | B1-si1000-gamma | e002-single-node-refinement | smoke-passed | paired r6-versus-r8 QE refinement pending |

Rules:

1. Directory paths store experiment identity.
2. run.sbatch stores executable behavior.
3. One attempt means one experimental protocol, not one Slurm job.
4. Repeats and infrastructure resubmissions remain in the same attempt.
5. A changed research question or resource shape creates a new attempt.
6. Existing completed result directories are not moved solely for cleanup.
7. Future result directories mirror the source hierarchy.
