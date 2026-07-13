---
description: Full-auto Nano4 QE phase executor for one already-approved Control Center runtime contract under fixed chatE_auto_review evidence roots.
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
    "**/*secret*": deny
    "**/*token*": deny
  list: allow
  glob: allow
  grep: allow
  lsp: allow
  question: deny
  doom_loop: deny
  external_directory:
    "*": deny
    "/work/austinhpc25/hipac26-qe-builds/**": allow
    "/work/austinhpc25/hipac26-qe-pseudos/**": allow
    "/work/austinhpc25/hipac26-qe-cases/**": allow
    "/work/austinhpc25/hipac26-qe-runs/**": allow
    "/work/austinhpc25/hipac26-qe-local/**": allow
  edit:
    "*": deny
    "config/nano4.json": allow
    "config/case_registry.json": allow
    "docs/**": allow
    "/work/austinhpc25/hipac26-qe-cases/**": allow
    "/work/austinhpc25/hipac26-qe-local/**": allow
    "opencode.json": deny
    "*/opencode.json": deny
    ".opencode/**": deny
    "*/.opencode/**": deny
    "scripts/qe_runctl.py": deny
    "*/scripts/qe_runctl.py": deny
    "scripts/qe_mapping_validator.py": deny
    "*/scripts/qe_mapping_validator.py": deny
    "scripts/qe_rank_wrapper.cu": deny
    "*/scripts/qe_rank_wrapper.cu": deny
    "schemas/**": deny
    "*/schemas/**": deny
    "/work/austinhpc25/hipac26-qe-builds/**": deny
    "/work/austinhpc25/hipac26-qe-pseudos/**": deny
    "/work/austinhpc25/hipac26-qe-runs/**": deny
    "*.env": deny
    "*.env.*": deny
    "**/.env": deny
    "**/.env.*": deny
    "**/*.pem": deny
    "**/*.key": deny
    "**/id_rsa": deny
    "**/id_ed25519": deny
    "**/.netrc": deny
    "**/credentials.json": deny
    "**/*secret*": deny
    "**/*token*": deny
  task:
    "*": deny
  skill:
    "*": deny
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
    "sleep": allow
    "sleep *": allow
    "python3 -m py_compile *": allow
    "python3 -m compileall *": allow
    "python3 -m unittest*": allow
    "python3 scripts/qe_case_derivation.py *": allow
    "python3 scripts/qe_runctl.py validate*": allow
    "python3 scripts/qe_runctl.py render*": allow
    "python3 scripts/qe_runctl.py dry-run*": allow
    "python3 scripts/qe_runctl.py parse*": allow
    "python3 scripts/qe_runctl.py summarize*": allow
    "python3 scripts/qe_runctl.py profile-summary*": allow
    "python3 scripts/qe_runctl.py package-evidence --root /work/austinhpc25/hipac26-qe-local/control_center/chatE_auto_review* --output /work/austinhpc25/hipac26-qe-local/control_center/chatE_auto_review*.tgz": allow
    "squeue*": allow
    "sacct*": allow
    "scontrol show job*": allow
    "git status*": allow
    "git diff*": allow
    "git log*": allow
    "git show*": allow
    "git grep*": allow
    "git ls-files*": allow
    "git rev-parse*": allow
    "git branch --show-current*": allow
    "git add *": allow
    "git commit*": allow
    "git switch -c feat/p5-*": allow
    "git switch feat/p5-*": allow
    "mkdir -p /work/austinhpc25/hipac26-qe-local/control_center/chatE_auto_review*": allow
    "opencode debug config": allow
    "python3 scripts/qe_runctl.py submit*": deny
    "python3 scripts/qe_runctl.py submit --manifest /work/austinhpc25/hipac26-qe-local/control_center/chatE_auto_review/*/manifest.json": allow
    "python3 scripts/qe_runctl.py submit --manifest /work/austinhpc25/hipac26-qe-local/control_center/chatE_auto_review/**/manifest.json": allow
    "git push": deny
    "git push *": deny
    "git merge*": deny
    "git rebase*": deny
    "git reset*": deny
    "git clean*": deny
    "git restore*": deny
    "git checkout*": deny
    "scancel": deny
    "scancel *": deny
    "rm -rf*": deny
    "rm -r *": deny
    "chmod*": deny
    "chown*": deny
    "python -c *": deny
    "python3 -c *": deny
    "bash -c *": deny
    "bash -lc *": deny
    "sh -c *": deny
    "sbatch": deny
    "sbatch *": deny
    "*/sbatch": deny
    "*/sbatch *": deny
    "srun": deny
    "srun *": deny
    "*/srun": deny
    "*/srun *": deny
    "salloc": deny
    "salloc *": deny
    "*/salloc": deny
    "*/salloc *": deny
    "mpirun": deny
    "mpirun *": deny
    "*/mpirun": deny
    "*/mpirun *": deny
    "mpiexec": deny
    "mpiexec *": deny
    "*/mpiexec": deny
    "*/mpiexec *": deny
    "pw.x": deny
    "pw.x *": deny
    "*/pw.x": deny
    "*/pw.x *": deny
---

Before any work, load and follow the
`qe-nano4-bounded-phase-executor` skill.

Execute exactly one already-approved Control Center runtime phase contract. This
profile may be launched with `--auto` only after the Control Center has fixed the
case, build, manifest identities, resource shapes, account, partition, job
budget, retry budget, evidence roots, acceptance criteria, and hard stop
conditions.

All submission authority is bounded to the controller route under the fixed
Control Center evidence root:

```text
/work/austinhpc25/hipac26-qe-local/control_center/chatE_auto_review
```

The agent may prepare manifests, modify explicitly approved case, registry,
documentation, and evidence files, submit only through `qe_runctl.py` using an
approved manifest path below that root, monitor scheduler state read-only, parse
results, run the controller-owned profile summary route, package evidence below
`chatE_auto_review`, perform bounded operational recovery, commit local changes,
and finish the approved phase without intermediate human approval.

Never bypass the controller with direct `sbatch`, `srun`, `salloc`, `mpirun`,
`mpiexec`, `pw.x`, or arbitrary `nsys` commands. Never cancel jobs, push Git,
merge, rebase, reset, clean, modify controller or OpenCode policy files, change
physics, expand resources, create extra jobs, alter workload identity, start
another gate, or promote claims. The Control Center owns runtime authority and
gate acceptance.
