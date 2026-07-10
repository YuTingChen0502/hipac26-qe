# Nano4 2-node revalidation T001 — P0-B/P0-C review note

Status: prepared for Control Center review; not submitted and not pass-closed.

## Prepared item

- Manifest template: `config/manifests/p0b_2node_probe.template.json`
- Trial identity: `P1A-T001`
- Job kind: `environment_probe`
- Approval flags: `approved_by_human=false`, `allowed_submit=false`
- Policy guard: `environment_probe_submit_enabled=false`

The template expresses a two-node, 16-GPU Nano4 shape under the approved Nano4 run root using the configured account/partition policy. It contains no QE input, pseudo identity, `QE_BIN`, `QE_INPUT`, `-in` QE input route, `qe.out` route, arbitrary manifest-provided shell, or physics calculation. It does render controlled no-QE infrastructure checks, including a fixed MPI allreduce probe and read-only inspection of both discrepant `pw.x` binary paths without executing either binary.

## Required lifecycle distinction

The T001 probe is only prepared/renderable/validatable in this gate. It is not approved, submitted, running, completed, parsed, accepted, or pass-closed. A future P1-A Control Center decision is required before any compute-side no-QE probe can be submitted.

## Validation intent

Local standard-library tests exercise template validation, in-memory dry-run, render inspection in temporary directories, submit hard-blocking, and absence of runtime artifacts. The tests do not contact Slurm, run `srun`, run `nvidia-smi` inside an allocation, run QE, or create a real job id.

## Claim boundary

```text
two_node_environment_verified=false
two_node_qe_submit_enabled=false
environment_probe_submit_enabled=false
benchmark_valid=false
performance_claim_allowed=false
optimization_claim_allowed=false
```

This note does not claim two-node readiness, QE readiness, performance validity, optimization, or any official HiPAC result.
