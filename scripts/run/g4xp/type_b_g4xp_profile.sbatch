#!/usr/bin/env bash

# Job identity
#SBATCH --account=ACD114087
#SBATCH --partition=16gpus
#SBATCH --job-name=type-b-g4xp-profile

# Benchmark placement
#SBATCH --nodelist=25a-hgpn[002-003]

# Compute resources
#SBATCH --nodes=2
#SBATCH --ntasks=16
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=12
#SBATCH --gres=gpu:8

# Time and logs
#SBATCH --time=04:00:00
#SBATCH --output=/work/%u/hipac26-qe-runs/slurm/%x-%j.out
#SBATCH --error=/work/%u/hipac26-qe-runs/slurm/%x-%j.err

set -euo pipefail
umask 027

source "/work/${USER}/hipac26-qe/scripts/env/nvhpc259.sh"

QE_EXECUTABLE="/work/${USER}/hipac26-qe-builds/G4Xp-qe75-nvhpc259-h200-sm90-noelpa-nvtx/install/bin/pw.x"
QE_INPUT_SOURCE="/work/${USER}/hipac26-qe-cases/typeB-si1000-gamma/pw.in"
MPI_RANKS=16
RANKS_PER_NODE=8
K_POINT_POOLS=1
OPENMP_THREADS=12
PROFILE_RANKS="0,3,8,11"

NSYS_EXECUTABLE="$(command -v nsys || true)"
if [[ -z "${NSYS_EXECUTABLE}" ]]; then
    echo "ERROR: nsys is not available after loading the NVHPC environment" >&2
    exit 2
fi

RUN_DIRECTORY="/work/${USER}/hipac26-qe-runs/g4x-g4xp-runtime/type_b/g4xp-${SLURM_JOB_ID}"
QE_INPUT_COPY="${RUN_DIRECTORY}/pw.in"

test -x "${QE_EXECUTABLE}"
test -f "${QE_INPUT_SOURCE}"
test "${SLURM_NTASKS}" -eq "${MPI_RANKS}"

mkdir -p     "${RUN_DIRECTORY}"     "${RUN_DIRECTORY}/out"     "${RUN_DIRECTORY}/profiles"     "${RUN_DIRECTORY}/rank-mapping"

cp "${QE_INPUT_SOURCE}" "${QE_INPUT_COPY}"

export OMP_NUM_THREADS="${OPENMP_THREADS}"
export QE_EXECUTABLE
export QE_INPUT_COPY
export K_POINT_POOLS
export RUN_DIRECTORY
export PROFILE_RANKS
export NSYS_EXECUTABLE

{
    echo "job_id=${SLURM_JOB_ID}"
    echo "job_name=${SLURM_JOB_NAME}"
    echo "binary=${QE_EXECUTABLE}"
    echo "input=${QE_INPUT_SOURCE}"
    echo "nodes=${SLURM_JOB_NUM_NODES}"
    echo "mpi_ranks=${MPI_RANKS}"
    echo "ranks_per_node=${RANKS_PER_NODE}"
    echo "gpus_per_node=8"
    echo "openmp_threads=${OPENMP_THREADS}"
    echo "k_point_pools=${K_POINT_POOLS}"
    echo "profile_ranks=${PROFILE_RANKS}"
    echo "nsys=${NSYS_EXECUTABLE}"
} > "${RUN_DIRECTORY}/run-metadata.txt"

sha256sum     "${QE_EXECUTABLE}"     "${QE_INPUT_COPY}"     > "${RUN_DIRECTORY}/sha256sums.txt"

module list 2> "${RUN_DIRECTORY}/modules.txt" || true
scontrol show job "${SLURM_JOB_ID}" > "${RUN_DIRECTORY}/slurm-job.txt"

# Run QE from the isolated run directory so relative outdir paths
# resolve inside this job rather than inside the submission directory.
cd "${RUN_DIRECTORY}"

set +e

mpirun     --bind-to none     --np "${MPI_RANKS}"     --map-by "ppr:${RANKS_PER_NODE}:node"     -x OMP_NUM_THREADS     -x QE_EXECUTABLE     -x QE_INPUT_COPY     -x K_POINT_POOLS     -x RUN_DIRECTORY     -x PROFILE_RANKS     -x NSYS_EXECUTABLE     bash -c '
        set -euo pipefail

            GLOBAL_RANK="${OMPI_COMM_WORLD_RANK:?missing OMPI_COMM_WORLD_RANK}"
            LOCAL_RANK="${OMPI_COMM_WORLD_LOCAL_RANK:?missing OMPI_COMM_WORLD_LOCAL_RANK}"
            ORIGINAL_VISIBLE_GPUS="${CUDA_VISIBLE_DEVICES:-}"

            if [[ -n "${ORIGINAL_VISIBLE_GPUS}" ]]; then
                IFS="," read -r -a GPU_LIST <<< "${ORIGINAL_VISIBLE_GPUS}"
                if (( LOCAL_RANK >= ${#GPU_LIST[@]} )); then
                    echo "ERROR: local rank ${LOCAL_RANK} exceeds visible GPU count ${#GPU_LIST[@]}" >&2
                    exit 2
                fi
                SELECTED_GPU="${GPU_LIST[$LOCAL_RANK]}"
            else
                SELECTED_GPU="${LOCAL_RANK}"
            fi

            export CUDA_VISIBLE_DEVICES="${SELECTED_GPU}"
            export ACC_DEVICE_NUM=0

            printf "host=%s global_rank=%s local_rank=%s original_visible_gpus=%s selected_gpu=%s\n" \
                "$(hostname)" \
                "${GLOBAL_RANK}" \
                "${LOCAL_RANK}" \
                "${ORIGINAL_VISIBLE_GPUS:-unset}" \
                "${SELECTED_GPU}" \
                > "${RUN_DIRECTORY}/rank-mapping/rank-${GLOBAL_RANK}.txt"
        case ",${PROFILE_RANKS}," in
            *",${GLOBAL_RANK},"*)
                exec "${NSYS_EXECUTABLE}" profile                     --force-overwrite=true                     --trace=cuda,nvtx                     --sample=none                     --cpuctxsw=none                     --output="${RUN_DIRECTORY}/profiles/nsys-rank-${GLOBAL_RANK}"                     "${QE_EXECUTABLE}"                     -nk "${K_POINT_POOLS}"                     -in "${QE_INPUT_COPY}"
                ;;
            *)
                exec "${QE_EXECUTABLE}"                     -nk "${K_POINT_POOLS}"                     -in "${QE_INPUT_COPY}"
                ;;
        esac
    '     > "${RUN_DIRECTORY}/qe.out"     2> "${RUN_DIRECTORY}/qe.err"

QE_EXIT_CODE=$?

set -e

printf "%s\n" "${QE_EXIT_CODE}" > "${RUN_DIRECTORY}/qe-exit-code.txt"
exit "${QE_EXIT_CODE}"
