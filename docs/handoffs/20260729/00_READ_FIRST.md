# HiPAC 2026 QE Handoff — Read First

Data cutoff: 2026-07-29

Generated: 2026-07-30

Repository:

    /work/$USER/hipac26-qe

Branch:

    refactor/simple-runtime

Scientific evidence source HEAD:

    71edc1780c145a1b0642848794914689ea146eb5

## Source priority

1. `01_OPTIMIZATION_MAINLINE.md`
2. `02_EXACT_EVIDENCE_MANIFEST.md`
3. `03_INCIDENT_AND_VALIDATION_LEDGER.md`
4. `HiPAC26_QE_Experiments_20260729.xlsx`
5. packaged raw evidence and SHA-256 manifest
6. current nano4 read-only state
7. historical 20260722 handoff

## Frozen configurations

### A1-au111-manyk

    Build=G4X
    nk=7
    MPI ranks=14
    Active GPUs=14
    Nodes=2
    OMP threads=12
    Ranks per pool=2
    Layout=8,6
    Placement=map8x6

### B1-si1000-gamma

    Build=G4X
    nk=1
    MPI ranks=8
    Active GPUs=8
    Nodes=1
    OMP threads=12
    Layout=8
    Mapping=one MPI rank per active GPU

## Safety boundary

Before a fresh repository review is complete:

- do not alter frozen A1 or B1 launch files;
- do not rerun A1/B1 e001–e004;
- do not rebuild QE;
- do not rewrite historical evidence;
- do not classify Slurm `FAILED` as QE failure without raw evidence;
- do not use profiler-active wall time as formal runtime evidence.
