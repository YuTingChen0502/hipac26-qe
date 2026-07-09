# hipac26-qe build harness

Status:
- scripts are installed directly on nano4
- no build approved yet
- no sbatch approved yet
- no QE execution approved yet
- benchmark_valid=false

## Layout
```text
scripts/
├─ qe_runctl.py
├─ README.build_harness.md
├─ CANDIDATE_MAP.md
├─ lib/common.sh
├─ env/{nvhpc259,nvhpc263,oneapi,gcc132}.sh
├─ build/
│  ├─ candidates.d/{G1,G1p,G2,G3,C1,C2,C3}.conf
│  ├─ build_qe.sh
│  └─ sbatch_build.sh
└─ run/
   ├─ smoke_gpu.sbatch
   └─ bench_gpu.sbatch
```

Candidate order
Primary path:
G1 -> smoke -> M-case x3 -> G2/C1 -> shortlist

Deferred:
G1p only when profiling starts
G3 only when >=2 GPU case exists
C2/C3 only when CPU route or correctness arbitration matters

Approval guards
Do not create these unless Control Center explicitly approves:
/work/$USER/hipac26-qe-local/ALLOW_BUILD_EXECUTION
/work/$USER/hipac26-qe-local/ALLOW_BUILD_SUBMIT
/work/$USER/hipac26-qe-local/ALLOW_QE_EXECUTION

Script invocation
Scripts are intentionally chmod 0640.
Use:
bash scripts/build/sbatch_build.sh G1
bash scripts/build/build_qe.sh G1

Do not use:
./scripts/build/sbatch_build.sh G1
./scripts/build/build_qe.sh G1

Current default site config
ACCOUNT=ACD114087
GPU_PART=dev
BENCH_PART=8gpus
BUILD_JOBS=16
