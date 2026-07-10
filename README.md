# hipac26-qe

Clean automation repository for HiPAC26 Quantum ESPRESSO work on nano4.

The old process/history repository is `hipac26-qe-process`. This repository is intentionally minimal and keeps only files needed for future controlled automation.

## Scope

This repo contains:

```text
automation policy
nano4 configuration
manifest and testcase registry schemas
single run controller
controlled manifest templates
opencode skills and bounded phase agent policy
```

This repo does not contain:

```text
QE source tree
QE binaries
pseudopotentials
input cases
run directories
Slurm logs
QE outputs
optimization claims
```

## Current control boundary

```text
Level 4 automation ladder was validated in the archived process repo.
Level 5 adaptive behavior remains disabled.
benchmark_valid must remain false until an official benchmark gate exists.
two_node_environment_verified=false
two_node_qe_submit_enabled=false
environment_probe_submit_enabled=false
performance_claim_allowed=false
optimization_claim_allowed=false
```

Prepared, rendered, validated, approved, submitted, running, completed, parsed,
accepted, and pass-closed are distinct states. This repository can prepare,
render, and locally validate artifacts. Only a Control Center decision can
approve submission, accept evidence, pass-close a gate, or authorize the next
gate.

No command in this repository grants permission to submit jobs by itself. Execution requires a human-approved manifest and must go through:

```bash
python3 scripts/qe_runctl.py submit --manifest <approved_manifest.json>
```

Forbidden outside explicit approval:

```text
naked sbatch
manual mpirun
manual pw.x
bash job.sh
./job.sh
automatic retry
adaptive search
benchmark_valid=true
```

## Minimal workflow

```text
1. Prepare inputs on nano4 storage, not in Git.
2. Create a manifest that records binary/input/pseudo paths and hashes.
3. Render run directories with qe_runctl.py render.
4. Validate manifest and rendered jobs with qe_runctl.py validate.
5. Human approval edits/creates an approved manifest.
6. Submit only with qe_runctl.py submit.
7. Parse with qe_runctl.py parse.
8. Summarize with qe_runctl.py summarize.
```

For P0-B/P0-C, the controlled environment probe route is render/validate/dry-run
only. The template `config/manifests/p0b_2node_probe.template.json` is prepared
for `P1A-T001`, but it is unapproved and non-submittable.

The P1-A no-QE probe renderer is deterministic and controller-owned: it records
secret-safe allowlisted runtime identity, verifies the approved Nano4 NVHPC/HPC-X
MPI route, compiles a fixed task-local CUDA runtime identity probe, and keeps
production submission fixed to `sbatch` behind `qe_runctl.py submit`.

V2 manifests are fail-closed on path containment and rendered-artifact
integrity. `run_root` must match the configured Nano4 run root, every `run_dir`
must be a strict descendant, and wrapper-only submit rejects symlinks or any
post-render modification of `job.sh` or `metadata.json` before subprocess use.

## P0-B/P0-C claim boundary

Do not claim that the two-node environment is verified, that two-node QE is
ready, that an official benchmark exists, that a speedup was measured, that a
best configuration was found, that a build is optimized, or that an official
HiPAC result exists.

The configured binary identity discrepancy is intentional and unresolved:
`config.current_binary.path` differs from the accepted G1 smoke path
`/work/$USER/hipac26-qe-builds/G1-qe75-nvhpc259-gpu-base/install/bin/pw.x`.
The status remains `identity_status=needs_nano4_verification`; compute-side
identity/linkage verification is deferred.

## Canonical nano4 locations

Configured in `config/nano4.json`:

```text
repo root: /work/$USER/hipac26-qe
build root: /work/$USER/hipac26-qe-builds
pseudo root: /work/$USER/hipac26-qe-pseudos
run root: /work/$USER/hipac26-qe-runs
case root: /work/$USER/hipac26-qe-cases
```

## First nano4 sync

```bash
# [nano4]
cd /work/$USER
git clone git@github.com:YuTingChen0502/hipac26-qe.git
cd /work/$USER/hipac26-qe
git status --short
```
