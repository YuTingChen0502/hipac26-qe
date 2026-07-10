# Nano4 environment contract — P0-B/P0-C

Status: Chat C entry policy after Control Center accepted P1-B as pass-closed.

## Machine-readable policy

`config/nano4.json` records the active fail-closed defaults:

```text
benchmark_valid_default=false
performance_claim_allowed_default=false
optimization_claim_allowed_default=false
two_node_environment_verified=true
two_node_qe_submit_enabled=false
environment_probe_submit_enabled=false
max_retries_default=0
submit_requires_human_approval=true
submit_wrapper_only=true
```

Authorized accounts are `ACD114087` and `GOV114009`; `ACD115059` is explicitly forbidden. Nano4 H200 nodes are represented as 8 GPUs per node, 104 allocatable CPU TRES per node, and at most 12 requested CPU cores per requested GPU for this preflight. The current preflight ceiling is 2 nodes.

Host memory is recorded only as observed text (`2 TB`) with `host_memory_unit_normalization_status=not_verified`; no byte conversion is claimed.

## Submission and runtime boundary

No P0-B/P0-C command may contact Slurm or execute QE. In particular, do not run `sinfo`, `squeue`, `sacct`, `salloc`, `srun`, `sbatch`, `scancel`, `mpirun`, `mpiexec`, or `pw.x` as real commands. Tests may render text containing a future `srun` line, but that script must not be executed.

No approval token, job id, Slurm output, QE output, or real run directory is created by this gate.

V2 render paths are contained by contract: the manifest run root must equal the configured Nano4 run root, and each job run directory must be a strict descendant. The controller rejects relative paths, alias components, repeated separators, symlink parent components, sibling-prefix escapes, and run roots inside the Git repository. The submit route revalidates rendered `job.sh` and `metadata.json` byte-for-byte/field-for-field against deterministic builders before any subprocess boundary, and production submission always invokes `sbatch` rather than an environment-selected executable.

The P1-A probe records only a deterministic allowlist of runtime environment variables needed for route and placement identity. Names containing or plausibly containing secret material (`TOKEN`, `SECRET`, `PASSWORD`, `PASSWD`, `API_KEY`, `PRIVATE_KEY`, `CREDENTIAL`, or `AUTH`) are excluded from the evidence policy.

## State distinctions

Prepared, rendered, and validated artifacts are review evidence only. They are not approved, submitted, running, completed, parsed, accepted, or pass-closed evidence. Only Control Center can approve a next action or close a gate.

## Accepted two-node environment evidence

`two_node_environment_verified=true` is based on accepted P1-A-R001 recovery evidence:

- `/work/$USER/hipac26-qe-local/control_center/p1a_r001_recovery_review/`
- `/work/$USER/hipac26-qe-local/control_center/p1a_r001_recovery_review.tgz`
- archive SHA-256: `e3b4de7aea01356cab6d8627fe1c9bf8122eae56df4cd266bfbcbcac1906ab65`
- extracted `SHA256SUMS`: verified during Chat C entry.

The flag records only the accepted no-QE two-node environment proof. It does not
enable two-node QE submission by itself; `two_node_qe_submit_enabled` remains
false by default and must be temporarily enabled only for a single approved
wrapper submission.

## Production binary identity

The accepted G1 production binary for Chat C is
`/work/$USER/hipac26-qe-builds/G1-qe75-nvhpc259-gpu-base/install/bin/pw.x`
with SHA-256 `d2b0d6221e4a1d18dfdb6407baad3f428c52a3e8e3c2dde8bd301827f3c66543`.
This identity is diagnostic/readiness-only and carries no benchmark,
performance, or optimization claim.
