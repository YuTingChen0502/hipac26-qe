# HiPAC 2026 QE — Incident and Validation Ledger

## 1. Job 203322

Layer:

    infrastructure and submission artifact

Failure:

    Slurm copied run.sbatch into its spool directory.
    BASH_SOURCE therefore referred to /var/spool/slurmd rather than
    the repository.
    Runtime git-root discovery and helper lookup failed.

Scientific classification:

    invalid infrastructure attempt
    QE execution count = 0
    no scientific evidence

Correction:

    remove runtime repository-root discovery
    submit immutable standalone bundles

## 2. Job 203455

Layer:

    post-processing package

Execution:

    six QE calculations completed
    all QE exit codes zero
    all runs converged
    raw output preserved

Failure:

    parse_qe_smoke.py imported qe_convergence.py
    the initial standalone bundle omitted that dependency
    parser failed six times
    collector returned nonzero
    Slurm state became FAILED

Scientific classification:

    QE execution valid
    post-processing invalid
    results recoverable without QE rerun

Correction:

    include parser dependencies in bundles
    separate Slurm execution validity from scientific post-processing

## 3. Job 203897

Architecture:

    standalone bundle
    no runtime repository helper source
    execution-only gate
    external raw-output verifier

Result:

    COMPLETED 0:0
    six of six trials valid
    map8x6 selected

## 4. Job 203925

Execution:

    COMPLETED 0:0
    ten of ten trials completed
    execution failures zero
    all final energies equal
    all mappings correct

Initial verifier failure:

    expected energy count remained hard-coded as six
    e004 contained ten trials
    reference energy became None
    every trial was falsely marked energy_reference_missing

Correction:

    replace len(valid_energies) == 6
    with len(valid_energies) == expected_trials

Recovery:

    reprocess e002, e003 and e004 from preserved raw outputs
    no QE resubmission
    no regenerated scientific execution

## 5. Current architecture rules

Submitted bundle rules:

- no runtime git-root discovery from BASH_SOURCE;
- no runtime source of repository helper scripts;
- bundle hashes must verify before submission;
- submitted bundles are immutable evidence.

Execution-only gate checks:

- expected trial count;
- QE exit code;
- JOB DONE marker;
- SCF convergence marker;
- PWSCF wall-time marker.

Offline raw verifier checks:

- candidate identity;
- number of k-points;
- rank mapping count;
- node layout;
- final energy;
- energy tolerance;
- fatal markers;
- wall time;
- candidate statistics.

Legacy collector status:

    retained for history and diagnostics
    not authoritative for Slurm execution success
