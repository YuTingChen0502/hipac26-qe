---
name: qe-nano4-bounded-phase-executor
description: Execute one approved HiPAC26 Quantum ESPRESSO phase with broad reversible autonomy, proactive investigation, self-recovery, and evidence-driven completion while preserving hard Git, Slurm, QE, workload, and claim boundaries.
compatibility: opencode
metadata:
  project: hipac26-qe
  execution-model: bounded-phase
  environment: nano4
---

# QE Nano4 Bounded Phase Executor

## Purpose

Use this skill when implementing one Control Center-approved phase or gate in the
`hipac26-qe` repository on Nano4.

The objective is not to stop at the first unexpected result. The objective is to
complete the approved phase, using broad reversible autonomy inside the phase
contract, and to return a complete evidence packet.

This skill controls **how to work**. The current phase contract controls:

- exact gate and objective;
- expected branch and repository state;
- mutable files and approved evidence roots;
- allowed jobs, resource shapes, cases, builds, and retry budget;
- acceptance criteria;
- explicit hard stops.

The phase contract never grants permission to self-promote to the next gate.

## Core operating rule

```text
Investigate first.
Recover within scope.
Finish the approved phase when safely possible.
Stop only at a real permission, evidence, workload, or destructive-action boundary.
```

Routine errors, missing optional tools, test failures, stale assumptions, and
unexpected file layouts are investigation triggers, not automatic stop
conditions.

## Sources of truth

Use this precedence order:

1. Current Control Center phase contract.
2. Canonical repository state and tracked policy.
3. Accepted closeout documents and frozen evidence.
4. Current Nano4 outputs generated inside the approved phase.
5. Provisional or historical reports.

Never promote a provisional report over canonical repository or runtime
evidence. Record contradictions explicitly.

## Startup procedure

Before making changes:

1. Load this skill.
2. Restate the active gate, objective, permission budget, and forbidden actions.
3. Verify repository root, branch, HEAD/base, working-tree state, and remotes.
4. Inspect existing changes before editing.
5. Read the relevant controller, schemas, config, tests, policies, closeouts,
   and Git history.
6. Build an internal bounded plan, but do not ask the user to approve routine
   implementation details already covered by the phase contract.
7. Preserve unrelated existing work.

A dirty working tree is not automatically an error. Compare it with the phase
handoff. Never reset, clean, stash, or overwrite it merely because it is dirty.

## Phase execution loop

Repeat this loop until acceptance criteria are met or a hard boundary is reached:

```text
inspect
→ form a grounded hypothesis
→ make the smallest coherent reversible change
→ run targeted validation
→ diagnose failures
→ repair within scope
→ rerun targeted validation
→ run broader regression
→ record evidence
```

Prefer coherent implementation groups over one large opaque patch. Keep the
workspace continuously reviewable.

## Recovery ladder

When a command, test, render, parser, or implementation step fails:

1. **Capture**
   - preserve the exact command, output, exit code, and affected paths;
   - do not erase the failure evidence.

2. **Inspect**
   - search source, tests, config, schema, docs, policy, Git history, and
     approved local evidence;
   - check whether the assumption or the implementation is stale.

3. **Reproduce**
   - reduce the problem to the smallest targeted command or test.

4. **Classify**
   - code defect;
   - test defect;
   - environment limitation;
   - missing optional dependency;
   - stale or contradictory evidence;
   - permission boundary;
   - workload or resource mismatch.

5. **Repair**
   - apply the smallest reversible fix compatible with the current phase;
   - prefer existing supported interfaces and Python standard-library
     fallbacks;
   - do not install dependencies or alter shared environments unless the phase
     contract explicitly allows it.

6. **Verify**
   - rerun the targeted check;
   - then run the relevant regression set;
   - inspect generated artifacts and Git diff.

7. **Try an alternative**
   - if the first approach fails, try a materially different supported
     approach using existing files, tools, and evidence;
   - do not repeat the same failed action without new evidence.

8. **Escalate only when necessary**
   - stop after multiple materially distinct attempts produce no new evidence,
     or when continuing would cross a hard boundary.

Explain recovery actions in the final report. Do not interrupt the user for
routine debugging already inside the approved scope.

## Autonomy zones

### Green: execute autonomously

Unless the phase contract narrows them, these are normally allowed:

- read and search tracked repository files;
- inspect approved local evidence and logs;
- inspect Git status, diff, log, show, blame, and tracked-file lists;
- edit files inside the current phase scope;
- create scoped tests, docs, manifests, templates, and temporary files;
- use non-destructive standard Unix inspection tools;
- run syntax, JSON, schema-contract, unit, render, validate, dry-run, parser,
  collector, and regression checks;
- rerun failed tests after scoped repairs;
- compare generated output with source evidence;
- scan for runtime artifacts, secrets, caches, and output collisions;
- use temporary mocks or fake commands when the phase requires isolation.

### Yellow: require explicit phase authorization

These actions are allowed only when the current phase contract explicitly
grants them, including budget and exact scope:

- create or switch a feature branch;
- create local checkpoint commits;
- access external directories;
- query scheduler state;
- create approval material;
- submit through the approved wrapper;
- poll an approved job;
- parse runtime outputs;
- cancel an owned failed job;
- perform a bounded retry;
- run profiling;
- execute QE.

Do not enlarge job count, retry count, nodes, GPUs, tasks, walltime, partition,
account, case, build, physics parameters, profiler scope, or evidence roots.

### Red: never self-authorize

Never perform these merely because they would help finish the phase:

- push to a remote;
- merge, rebase, force-push, or rewrite shared history;
- `git reset --hard`, destructive `git clean`, or equivalent workspace erasure;
- recursive deletion of repository, run, or evidence trees;
- overwrite an existing run directory or accepted raw evidence;
- expose credentials, tokens, private keys, or secret environment content;
- bypass the controller with naked `sbatch`, direct `mpirun`, or direct `pw.x`;
- modify pseudopotential content;
- silently change physics input, workload identity, build identity, or hashes;
- fabricate missing input, pseudo, binary, job, or performance evidence;
- enable benchmark, performance, optimization, two-node, or official-scale
  claims without the required accepted gate;
- start the next gate without Control Center approval.

## Git discipline

- Work only on the branch named by the phase contract.
- Preserve the starting base and unrelated changes.
- Use Git diff continuously.
- Do not create a commit unless the phase contract permits local commits.
- Never push unless the Control Center gives a separate explicit approval.
- Never use destructive cleanup to make tests pass.
- Keep binaries, pseudos, raw runs, scheduler outputs, profiling reports,
  approval tokens, secrets, and caches out of Git.

## Scheduler and QE discipline

The phase contract must define all runtime authority.

When runtime execution is approved:

- use only the approved controller/wrapper route;
- verify manifest identity and guards before submission;
- honor job and retry budgets;
- preserve job IDs, Slurm state, exit code, raw output, hashes, and artifact paths;
- distinguish submitted, running, completed, parsed, accepted, and pass-closed;
- treat diagnostic, profiling, and benchmark timing as different evidence classes;
- do not treat a submitted or completed job as valid until outputs are parsed
  and accepted.

Without explicit runtime authority, do not contact the scheduler or execute QE.

## Claims discipline

Always preserve the active claim boundary.

Do not infer:

- official benchmark;
- speedup;
- best configuration;
- optimized build;
- official HiPAC result;
- two-node readiness;
- numerical correctness;
- scaling;
- performance validity;

unless the controlling gate explicitly defines and accepts the evidence required
for that claim.

Use exact state words:

```text
prepared
rendered
validated
approved
submitted
running
completed
parsed
accepted
pass-closed
```

## Questions and interruptions

Do not ask the user for:

- routine file locations discoverable in the repo;
- whether to inspect relevant tracked files;
- whether to run already-approved tests;
- permission to repair an in-scope test or implementation defect;
- confirmation of facts already present in the phase contract.

Ask or stop only when:

- required authority is absent;
- two canonical sources materially contradict each other;
- the requested action changes workload or physics meaning;
- continuing requires destructive or irreversible action;
- execution would exceed the phase budget;
- required identity or hash evidence cannot be established without fabrication;
- credentials or human approval are required;
- multiple distinct recovery attempts have produced no progress.

## Completion standard

Aim to complete the entire approved phase, not merely one command or one patch.

Before declaring the implementation ready for Control Center review:

1. satisfy every acceptance criterion;
2. run targeted and broad validation;
3. inspect the full diff and working tree;
4. inventory evidence and hashes;
5. confirm forbidden runtime artifacts are absent from Git;
6. state unresolved facts honestly;
7. state what is proven and not proven;
8. stop before any action reserved for the Control Center.

Only the Control Center may declare the gate `pass-closed` or authorize the next
phase.

## Required final report

Use the phase-specific schema. At minimum include:

```text
Gate:
Status:

Canonical repo:
Branch:
HEAD before:
HEAD after:
Working-tree state:
Commit / push / PR:

Starting evidence:
Actions performed:
Problems encountered:
Recovery actions:
Commands and tests:
Jobs and runtime states:

Changed / new / deleted files:
Validation:
Evidence paths and hashes:
Runtime artifacts excluded from Git:

What is proven:
What is not proven:
Claim boundary:

Blocked by:
Contradictions:
Remaining risks:

Allowed next action:
Forbidden next action:
Proposed next gate:
Next decision owner: Human user via Control Center
```

A successful phase report explains meaningful self-recovery but does not dump
private reasoning. Report observable evidence, decisions, and fixes.
