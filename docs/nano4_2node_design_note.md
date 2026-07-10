# Nano4 2-node design note — P0-B/P0-C

Status: prepared and validated for Control Center review; not approved, not submitted, not accepted, and not pass-closed.

## State vocabulary

- prepared: source policy, manifests, templates, or tests exist in the repository.
- rendered: the controller has created reviewable text artifacts such as `job.sh` and `metadata.json`.
- validated: local schema/controller checks passed without scheduler or QE execution.
- approved: a human Control Center decision explicitly authorizes a bounded action.
- submitted: an approved wrapper has contacted Slurm and produced a job id.
- running: Slurm reports an active allocation or job.
- completed: Slurm reports job completion.
- parsed: outputs were parsed after completion.
- accepted: Control Center accepted the evidence for the gate.
- pass-closed: Control Center closed the gate and may authorize the next one.

P0-B/P0-C reaches only prepared/validated review state. It does not approve, submit, run, complete, parse, accept, or pass-close a two-node job.

## Claim boundary

```text
two_node_environment_verified=false
two_node_qe_submit_enabled=false
environment_probe_submit_enabled=false
benchmark_valid=false
performance_claim_allowed=false
optimization_claim_allowed=false
```

This work must not be described as a verified two-node environment, two-node QE readiness, an official benchmark, a speedup, a best configuration, an optimized build, or an official HiPAC result.

## Controller design

Legacy manifests remain accepted for one-node QE render/validate behavior. The v2 manifest path is explicit and fail-closed: per-node and total resource fields are required, QE and `environment_probe` jobs cannot be mixed, and v2-only fields with a mistyped schema version are rejected rather than silently treated as legacy.

V2 resource validation requires explicit `nodes`, `ntasks`, `ntasks_per_node`, `gpus_per_node`, `total_gpus`, `cpus_per_task`, `gres`, `account`, `partition`, and `time`. Current preflight uses one MPI task per requested GPU and checks account, partition, GPU limits, CPU TRES, CPU-per-GPU, walltime, GRES consistency, `mpirun_np`, and `npools` divisibility.

V2 also requires `manifest.run_root` to match the configured Nano4 run root and every `job.run_dir` to be a strict descendant. Relative paths, `.`/`..`, repeated separators, sibling-prefix escapes, symlink parent components, and Git-repository-contained run roots fail closed. Before wrapper-only submit, `job.sh` and `metadata.json` must be regular non-symlink files and must exactly match deterministic controller builders derived from the manifest.

## Controlled environment probe route

The environment probe is a separate `job_kind=environment_probe`. It renders fixed controller-owned diagnostics for future compute-side inspection of allocation placement, per-task hostnames, Slurm task/node identifiers, CPU affinity, explicit one-GPU-per-task step syntax, `CUDA_VISIBLE_DEVICES`, task-local CUDA runtime GPU count/UUID/PCI-bus identity, shared-filesystem marker consistency, approved profile/MPI realpath/version/linkage evidence, a tiny no-QE MPI allreduce probe, and read-only binary identity/linkage checks for both discrepant `pw.x` paths. The rendered probe script is validated to exclude QE execution routes such as `QE_BIN`, `QE_INPUT`, `-in` QE input use, and `qe.out` generation. A controlled fixed `mpirun` invocation is present only for the no-QE MPI infrastructure probe.

Runtime environment evidence is explicitly allowlisted and denies variable names plausibly containing secrets such as tokens, passwords, API keys, private keys, credentials, or authorization material. Production submission is fixed to `sbatch`; tests may only fake submission by patching the subprocess boundary, not by replacing the production executable through environment variables.

The probe template at `config/manifests/p0b_2node_probe.template.json` is prepared for `P1A-T001` but remains unapproved and non-submittable. Real submit is hard blocked while `environment_probe_submit_enabled=false`.

## Binary identity handling

`config.current_binary.path` intentionally differs from the accepted G1 smoke path `/work/$USER/hipac26-qe-builds/G1-qe75-nvhpc259-gpu-base/install/bin/pw.x`. The discrepancy is preserved with `identity_status=needs_nano4_verification`; no path is promoted and no hash is updated without compute-side evidence.
