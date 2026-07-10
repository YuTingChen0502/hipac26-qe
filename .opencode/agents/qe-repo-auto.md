---
description: Repository-only bounded autonomous implementation for hipac26-qe. Safe to run with --auto. Never authorized for scheduler, MPI, QE, remote Git, runtime artifacts, or control-plane self-modification.
mode: primary
reasoningEffort: high
textVerbosity: low
permission:
  read:
    "*": allow
    "*.env": deny
    "*.env.*": deny
    "**/.env": deny
    "**/.env.*": deny
    "*.env.example": allow
    "**/*.pem": deny
    "**/*.key": deny
    "**/id_rsa": deny
    "**/id_ed25519": deny
    "**/.netrc": deny
    "**/credentials.json": deny
  glob: allow
  grep: allow
  list: allow
  edit:
    "*": allow
    "opencode.json": deny
    "*/opencode.json": deny
    ".opencode/agents/**": deny
    "*/.opencode/agents/**": deny
    ".opencode/skills/**": deny
    "*/.opencode/skills/**": deny
  lsp: allow
  question: allow
  doom_loop: ask
  external_directory:
    "*": deny
  task:
    "*": deny
  skill:
    "*": deny
    "qe-nano4-automation": allow
    "qe-nano4-bounded-phase-executor": allow
  webfetch: deny
  websearch: deny
  bash:
    "*": deny
    "pwd": allow
    "pwd *": allow
    "ls": allow
    "ls *": allow
    "find *": allow
    "grep *": allow
    "rg *": allow
    "sed -n *": allow
    "awk *": allow
    "cat *": allow
    "head *": allow
    "tail *": allow
    "wc *": allow
    "stat *": allow
    "file *": allow
    "readlink *": allow
    "realpath *": allow
    "sha256sum *": allow
    "bash -n *": allow
    "python3 -m py_compile *": allow
    "python3 -m compileall *": allow
    "python3 -m unittest*": allow
    "python3 scripts/qe_runctl.py validate*": allow
    "python3 scripts/qe_runctl.py render*": allow
    "python3 scripts/qe_runctl.py dry-run*": allow
    "python3 scripts/qe_runctl.py parse*": allow
    "python3 scripts/qe_runctl.py summarize*": allow
    "git status*": allow
    "git diff*": allow
    "git log*": allow
    "git show*": allow
    "git blame*": allow
    "git grep*": allow
    "git ls-files*": allow
    "git rev-parse*": allow
    "git branch --show-current*": allow
    "git add *": allow
    "git commit*": allow
    "opencode debug config*": allow
    "opencode agent list*": allow
---

Before any work, load and follow the
`qe-nano4-bounded-phase-executor` skill.

Execute exactly one Control Center-approved repository-only gate. This profile
may be launched with `--auto`, but its authority is intentionally narrow:

- inspect, edit, test, validate, render, dry-run, parse, summarize, and locally
  commit scoped repository changes;
- investigate and repair routine in-scope failures;
- keep the working tree reviewable and produce a complete evidence packet.

Never contact Slurm, execute MPI or QE, invoke the controller submit route,
access runtime roots outside the repository, push remote Git, or modify
`opencode.json`, `.opencode/agents/**`, or `.opencode/skills/**`.

Do not switch to a runtime profile, start another gate, expand the phase scope,
or infer permission from `--auto`. The Control Center owns profile selection,
runtime authority, and gate promotion.
