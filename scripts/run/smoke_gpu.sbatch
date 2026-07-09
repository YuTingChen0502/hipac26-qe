#!/usr/bin/env bash
#SBATCH -J qe-smoke-gpu
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=14
#SBATCH --gres=gpu:1
#SBATCH -t 00:20:00
set -euo pipefail

source "/work/${USER}/hipac26-qe/scripts/lib/common.sh"
require_allow_qe_execution
ensure_module

: "${CAND:?export CAND=<candidate dir name>}"
PWX="${QE_BUILDROOT}/${CAND}/install/bin/pw.x"
CASE="${QE_CASES}/smoke"
RUN="${QE_RUNROOT}/${CAND}-smoke-$(date +%Y%m%d_%H%M%S)"

mkdir -p "${RUN}"
cd "${RUN}"
cp "${CASE}/pw.in" .

case "${CAND}" in
  *nvhpc263*) module purge && module load x86-nvhpc/26.3 ;;
  *nvhpc259*) module purge && module load x86-nvhpc/25.9 ;;
  *gcc132*) module purge && module load gcc/13.2 ;;
esac

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export ESPRESSO_PSEUDO="${QE_PSEUDOS}"

{
  echo "jobid=${SLURM_JOB_ID}"
  echo "node=$(hostname)"
  echo "cand=${CAND}"
  echo "benchmark_valid=false"
  sha256sum pw.in
  sha256sum "${PWX}"
} > run_meta.txt

module list > module_list_runtime.txt 2>&1 || true
ldd "${PWX}" > ldd_at_runtime.txt || true
nvidia-smi > nvidia_smi_before.txt || true

srun --cpu-bind=cores "${PWX}" -input pw.in > pw.out 2> pw.err
rc=$?

grep -E "GPU|Parallel version" pw.out | head -5 > result_parallel.txt || true
grep "!    total energy" pw.out > result_energy.txt || true
grep -E "convergence has been achieved|PWSCF.*WALL" pw.out > result_status_wall.txt || true

exit "${rc}"
