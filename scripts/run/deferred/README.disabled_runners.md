# Deferred Slurm runners

These files are intentionally disabled.

Rules:
- Do not rename to `.sbatch` unless the corresponding gate scope is explicitly approved.
- Do not submit disabled runners.
- benchmark_valid must remain false unless a formal benchmark gate approves otherwise.
- G1p is profiling-only.
- C3 is correctness arbiter only.
- TypeB runners are not approved yet.
- G3 GPU-aware runners require separate runtime/resource policy.
