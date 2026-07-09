# hipac26-qe

Clean automation repository for HiPAC26 Quantum ESPRESSO work on nano4.

The old process/history repository is `hipac26-qe-process`. This repository is intentionally minimal and keeps only files needed for future controlled automation.

## Scope

This repo contains:

```text
automation policy
nano4 configuration
manifest schema
single run controller
opencode skill
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
historical gate reports
optimization claims
```

## Current control boundary

```text
Level 4 automation ladder was validated in the archived process repo.
Level 5 adaptive behavior remains disabled.
benchmark_valid must remain false until an official benchmark gate exists.
```

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
