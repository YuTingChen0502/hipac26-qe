# qe-nano4-automation skill

## Role

opencode is executor, not authority.

Control Center decides gate, phase, autonomy level, execution permission, and promotion. Human approval is required before any execution or promotion.

## Current default state

```text
execution_allowed=false
scheduler_submit_allowed=false
qe_execution_allowed=false
benchmark_valid=false
level5_enabled=false
```

## Repository scope

This repository is the clean automation controller repo. Historical reports and process evidence live in `hipac26-qe-process`.

This repo must not store:

```text
QE binaries
QE source trees
pseudopotentials
input cases
run outputs
Slurm logs
QE outputs
historical gate reports
```

## Required workflow

```text
manifest
  -> render
  -> validate
  -> human approval
  -> approved manifest
  -> wrapper-only submit
  -> parse
  -> summarize
```

The only allowed automation entrypoint is:

```text
scripts/qe_runctl.py
```

## Render-only gate

Render-only work may create:

```text
run directory
metadata.json
job.sh with mode 0640
candidate manifest
```

Render-only work must not create:

```text
qe.out
tmp/
env_snapshot.txt
module_snapshot.txt
job_id.txt
submission_record.txt
```

Render-only work must not make `job.sh` executable.

## Submission rule

Submission is allowed only when all are true:

```text
approved_by_human=true
allowed_submit=true
benchmark_valid=false
max_retries=0
manifest validated
```

Submission must go through:

```text
python3 scripts/qe_runctl.py submit --manifest <approved_manifest.json>
```

Do not submit jobs with manual shell loops or direct scheduler commands.

## QE execution boundary

Do not manually run QE executables or launcher commands from the shell. QE may run only inside approved scheduler jobs produced by the controller.

## Benchmark policy

Until an official benchmark gate exists:

```text
benchmark_valid=false
```

Allowed wording:

```text
observed wall time
workflow validation
runtime mapping observation
candidate build
```

Forbidden wording:

```text
benchmark result
speedup
best configuration
optimized build
official HiPAC result
```

## Promotion rule

Never promote because tasks completed. Promote only because controls are trusted.

Level 5 adaptive behavior remains disabled.
