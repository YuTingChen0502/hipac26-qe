# B1 e001 post-processing recovery

## Historical execution

The retained evidence comes from Slurm job `200733`.

It contains nine completed `pw.x` executions:

- `r4` x 3;
- `r8` x 3;
- `r16` x 3.

No QE calculation was rerun during this recovery.

## Historical failure classification

Slurm recorded the batch job as `FAILED` with exit code `1:0`.

The QE execution and rank/GPU mapping layers completed. The historical
collector applied a universal `1e-8 Ry` comparison tolerance, while
the B1 input used `conv_thr = 1e-7 Ry`. The `r4` result differed by
approximately `4e-8 Ry`, so the collector rejected a scientifically
comparable completed execution.

The recovery therefore separates:

1. QE execution validity;
2. MPI rank and GPU mapping validity;
3. numerical comparability;
4. collector policy;
5. final batch-script status.

## Authoritative recovery

The current raw verifier checks the retained files directly:

- trial and candidate identity;
- copied input SHA-256;
- QE exit code;
- `JOB DONE.` marker;
- fatal-error markers;
- number of k-points;
- SCF iteration count;
- final-energy tolerance;
- MPI rank count;
- node layout;
- PWSCF wall time;
- candidate statistics.

Recovery artifacts are stored beside the historical run under:

```text
raw-verification-v2/
```

The original trial directories, raw QE outputs, old collector outputs,
and historical Slurm records remain unchanged.
