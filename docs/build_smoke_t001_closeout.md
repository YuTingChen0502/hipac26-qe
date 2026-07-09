# BUILD-SMOKE-T001 Closeout

Status: PASS

## Accepted smoke run

- Job ID: 174191
- Candidate: G1-qe75-nvhpc259-gpu-base
- Case: smoke-si8
- Binary: /work/$USER/hipac26-qe-builds/G1-qe75-nvhpc259-gpu-base/install/bin/pw.x
- Launcher: mpirun_np1_bind_to_none
- Partition: dev
- Resources: 1 GPU, 12 CPUs/task, 1 task
- Slurm state: COMPLETED
- ExitCode: 0:0

## Smoke result

- qe_started: true
- qe_normal_end: true
- smoke_pass: true
- failure_class: null
- convergence_status: converged
- total_energy_ry: -91.34003974
- scf_iterations: 7
- number_of_atoms: 8
- number_of_k_points: 14

## Runtime fixes accepted

- Added Slurm account directive for smoke runner.
- Loaded NVHPC 25.9 runtime environment in Slurm shell.
- Made NVHPC env scripts standalone for non-interactive shells.
- Added OPAL_PREFIX for relocated HPC-X/OpenMPI runtime.
- Switched smoke launcher to mpirun --bind-to none -np 1.
- Added parser classification for MPI runtime failures.

## Collector / reporting

- Parser: scripts/parse_qe_smoke.py
- Collector: scripts/collect_qe_runs.py
- CSV: /work/$USER/hipac26-qe-runs/results.csv
- XLSX: /work/$USER/hipac26-qe-runs/qe_results.xlsx

## Guard

- benchmark_valid: false
- performance_claim_allowed: false
- optimization_claim_allowed: false

This gate validates controlled QE execution plumbing only. It does not establish a benchmark, best build, or optimization result.
