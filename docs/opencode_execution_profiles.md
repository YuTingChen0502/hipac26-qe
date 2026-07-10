# OpenCode Execution Profiles

## Purpose

This repository separates repository-only automation from scheduler/QE runtime
authority.

```text
qe-repo-auto
  repository-only bounded autonomy
  may be launched with --auto

qe-runtime-gated
  scheduler/QE/profiling phases
  must never be launched with --auto

qe-bounded-phase
  legacy compatibility alias
  prefer one of the two profiles above
```

The split reduces repetitive approval prompts for reversible repo work without
turning runtime execution into an unattended action.

## Config discovery

Project policy is stored in:

```text
opencode.json
.opencode/agents/
.opencode/skills/
```

OpenCode should be started from the repository root or a child directory. It
loads `opencode.json` from the project root and project-local agents from
`.opencode/agents/`.

Restart OpenCode after changing project config, agents, or skills so the resolved
policy is reloaded.

Inspect the active policy with:

```bash
cd /work/$USER/hipac26-qe
opencode debug config
opencode agent list
```

Do not save provider credentials or secret-bearing resolved config in evidence.

## Safe default

```bash
cd /work/$USER/hipac26-qe
opencode .
```

The project default agent is:

```text
qe-runtime-gated
```

This is intentionally conservative.

## Repository-only full-auto

```bash
cd /work/$USER/hipac26-qe
opencode . --agent qe-repo-auto --auto
```

Use this only for Control Center-approved repository work such as:

- source, schema, config, docs, and test changes;
- syntax checks and standard-library tests;
- `qe_runctl.py` validate/render/dry-run/parse/summarize;
- Git inspection and local checkpoint commits;
- closeout evidence generation.

It cannot:

- access runtime roots outside the repository;
- call controller submit;
- call Slurm, MPI, or QE directly;
- push or rewrite Git history;
- modify `opencode.json`, `.opencode/agents/**`, or `.opencode/skills/**`;
- self-promote to a runtime phase.

## Human-gated runtime

```bash
cd /work/$USER/hipac26-qe
opencode . --agent qe-runtime-gated
```

Never add `--auto`.

A runtime phase prompt must freeze:

- gate and objective;
- case, input, pseudo, and build identities;
- account, partition, nodes, tasks, GPUs, CPUs, and walltime;
- job and retry budgets;
- allowed evidence roots;
- acceptance criteria and stop conditions.

Submission is allowed only through:

```bash
python3 scripts/qe_runctl.py submit --manifest <approved-manifest>
```

That command remains an interactive approval point. Direct `sbatch`, `srun`,
`salloc`, `mpirun`, `mpiexec`, and `pw.x` are denied.

## External roots

The runtime-gated profile is intended to read approved paths under:

```text
/work/austinhpc25/hipac26-qe-builds
/work/austinhpc25/hipac26-qe-pseudos
/work/austinhpc25/hipac26-qe-cases
/work/austinhpc25/hipac26-qe-runs
/work/austinhpc25/hipac26-qe-local
```

Direct edits to builds, pseudos, and run directories are denied. Case changes
ask for approval. Evidence under `hipac26-qe-local` is allowed.

## Wrong-agent recovery

If the wrong agent was selected:

1. do not approve runtime or destructive requests;
2. stop the session;
3. verify `git status --short`;
4. restart from the repo root with the correct explicit `--agent`;
5. re-read the current Control Center phase contract.

Do not switch from `qe-repo-auto` to `qe-runtime-gated` inside a phase merely to
gain authority. Profile selection belongs to the Control Center.

## Security boundary

OpenCode permissions are a project safety and workflow layer, not an operating
system sandbox. Agent-specific permissions can override project defaults, and
shell pattern matching cannot prove semantic safety for arbitrary wrappers.

The final runtime enforcement remains:

- `qe_runctl.py`;
- approved manifest hashes;
- controller-owned renderers;
- resource and case/build identity guards;
- temporary enablement;
- job and retry budgets;
- Control Center evidence review.

`--auto` is approved only for `qe-repo-auto`.
