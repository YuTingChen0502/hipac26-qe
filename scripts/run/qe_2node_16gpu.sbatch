#!/usr/bin/env bash
#SBATCH -A ACD114087
#SBATCH -p 16gpus
#SBATCH -N 2
#SBATCH --ntasks=16
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=12
#SBATCH --gres=gpu:8
#SBATCH -t 04:00:00
#SBATCH -o slurm.out
#SBATCH -e slurm.err

set -euo pipefail

: "${QE_BIN:?QE_BIN is required}"
: "${QE_INPUT:?QE_INPUT is required}"
: "${RUN_DIR:?RUN_DIR is required}"

NPOOL="${NPOOL:-1}"
OMP_NUM_THREADS="${OMP_NUM_THREADS:-12}"

REPO="/work/${USER}/hipac26-qe"
WRAPPER="${REPO}/scripts/run/qe_rank_gpu.sh"
PARSER="${REPO}/scripts/parse_qe_smoke.py"

test -x "${QE_BIN}"
test -f "${QE_INPUT}"
test -x "${WRAPPER}"
test -f "${REPO}/scripts/env/nvhpc259.sh"

if (( SLURM_NTASKS % NPOOL != 0 )); then
    echo "ERROR: NPOOL=${NPOOL} does not divide NTASKS=${SLURM_NTASKS}" >&2
    exit 2
fi

source "${REPO}/scripts/env/nvhpc259.sh"

mkdir -p "${RUN_DIR}"
cd "${RUN_DIR}"

cp "${QE_INPUT}" pw.in

export RUN_DIR
export OMP_NUM_THREADS
export OMP_PLACES=cores
export OMP_PROC_BIND=close

{
    echo "job_id=${SLURM_JOB_ID}"
    echo "nodes=${SLURM_JOB_NUM_NODES}"
    echo "ntasks=${SLURM_NTASKS}"
    echo "ntasks_per_node=${SLURM_NTASKS_PER_NODE}"
    echo "cpus_per_task=${SLURM_CPUS_PER_TASK}"
    echo "omp_num_threads=${OMP_NUM_THREADS}"
    echo "npool=${NPOOL}"
    echo "qe_bin=${QE_BIN}"
    echo "qe_input=${QE_INPUT}"
} > run_metadata.txt

sha256sum "${QE_BIN}" pw.in > identities.sha256
scontrol show job "${SLURM_JOB_ID}" > slurm_job.txt
module list 2> modules.txt || true
nvidia-smi -L > gpu_list.txt
: > rank_mapping.tsv

set +e

mpirun \
    --bind-to none \
    -np "${SLURM_NTASKS}" \
    --map-by "ppr:${SLURM_NTASKS_PER_NODE}:node" \
    "${WRAPPER}" \
    "${QE_BIN}" \
    -nk "${NPOOL}" \
    -in pw.in \
    > qe.out \
    2> qe.err

qe_rc=$?

set -e

printf '%s\n' "${qe_rc}" > qe_exit_code.txt

python3 "${PARSER}" \
    --pw-out qe.out \
    --pw-err qe.err \
    --pw-in pw.in \
    --out parsed.json \
    || true

exit "${qe_rc}"
