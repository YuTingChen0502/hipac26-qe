# Candidate map — primary build harness naming

| Candidate | Meaning | Main variable | Stage |
|---|---|---|---|
| G1 | NVHPC 25.9 GPU base, ScaLAPACK OFF | primary GPU route | first build anchor |
| G2 | NVHPC 26.3 GPU base, ScaLAPACK OFF | toolchain version | after G1 smoke |
| G3 | NVHPC 25.9 GPU-aware MPI, ScaLAPACK OFF | MPI GPU-aware ON | only for >=2 GPU case |
| G1p | NVHPC 25.9 GPU + NVTX, ScaLAPACK OFF | profiling only | profiling stage only |
| C1 | NVHPC 25.9 CPU-only, ScaLAPACK OFF | CUDA disabled | GPU effect isolation |
| C2 | oneAPI MKL CPU | deferred: ScaLAPACK link unresolved | optional CPU performance |
| C3 | GCC 13.2 + OpenBLAS CPU | independent correctness arbiter | smoke correctness only |

Notes:
- G1 is the primary CMake build anchor.
- Old B001 existing binary remains reference evidence only.
- benchmark_valid=false until a later explicit benchmark gate.
- BUILD execution requires /work/$USER/hipac26-qe-local/ALLOW_BUILD_EXECUTION.
- BUILD submit requires /work/$USER/hipac26-qe-local/ALLOW_BUILD_SUBMIT.
- QE execution requires /work/$USER/hipac26-qe-local/ALLOW_QE_EXECUTION.
