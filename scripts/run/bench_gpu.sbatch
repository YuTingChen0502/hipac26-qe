#!/usr/bin/env bash
#SBATCH -J qe-bench
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=12
#SBATCH --gres=gpu:1
#SBATCH -t 01:00:00
set -euo pipefail

source "/work/${USER}/hipac26-qe/scripts/lib/common.sh"
require_allow_qe_execution
ensure_module

: "${CAND:?}"
: "${CASE:?}"
: "${NK:=1}"
: "${REP:=1}"

PWX="${QE_BUILDROOT}/${CAND}/install/bin/pw.x"
RUN="${QE_RUNROOT}/${CAND}-${CASE}-nk${NK}-r${REP}-$(date +%Y%m%d_%H%M%S)"

mkdir -p "${RUN}"
cd "${RUN}"
cp "${QE_CASES}/${CASE}/pw.in" .

case "${CAND}" in
  *nvhpc263*) module purge && module load x86-nvhpc/26.3 ;;
  *nvhpc259*) module purge && module load x86-nvhpc/25.9 ;;
  *gcc132*) module purge && module load gcc/13.2 ;;
esac

export OMP_NUM_THREADS="${OMP_OVERRIDE:-${SLURM_CPUS_PER_TASK}}"
export ESPRESSO_PSEUDO="${QE_PSEUDOS}"

{
  echo "jobid=${SLURM_JOB_ID}"
  echo "node=$(hostname)"
  echo "cand=${CAND}"
  echo "case=${CASE}"
  echo "nk=${NK}"
  echo "rep=${REP}"
  echo "omp=${OMP_NUM_THREADS}"
  echo "benchmark_valid=false"
  sha256sum pw.in
  sha256sum "${PWX}"
} > run_meta.txt

module list > module_list_runtime.txt 2>&1 || true
ldd "${PWX}" > ldd_at_runtime.txt || true

srun --cpu-bind=cores "${PWX}" -nk "${NK}" -input pw.in > pw.out 2> pw.err

grep "!    total energy" pw.out | tail -1 > result_energy.txt || true
grep -E "PWSCF.*WALL" pw.out > result_wall.txt || true
grep -E "electrons|c_bands|sum_band|h_psi|fftw|fft_scatter|cegterg|.diaghg" pw.out \
  | tail -30 > result_timers.txt || true
