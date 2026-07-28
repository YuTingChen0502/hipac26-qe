#!/usr/bin/env bash
#SBATCH --account=ACD114087
#SBATCH --partition=8gpus
#SBATCH --job-name=B1-e002-smoke
#SBATCH --exclude=25a-hgpn144
#SBATCH --nodes=1
#SBATCH --ntasks=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=12
#SBATCH --gres=gpu:8
#SBATCH --time=00:20:00
#SBATCH --output=/work/%u/hipac26-qe-runs/slurm/%x-%j.out
#SBATCH --error=/work/%u/hipac26-qe-runs/slurm/%x-%j.err

set -uo pipefail
umask 027

REPO="/work/${USER}/hipac26-qe"
RUN_ROOT="/work/${USER}/hipac26-qe-runs"

SMOKE_DIRECTORY="${RUN_ROOT}/sweeps/g4x/type-b/B1-si1000-gamma/e002-single-node-refinement/launcher-smoke/job-${SLURM_JOB_ID}"

SMOKE_FAILURES=0

source "${REPO}/scripts/env/nvhpc259.sh"

if [[ "${SLURM_JOB_NUM_NODES}" -ne 1 ]]; then
    echo "ERROR: expected one allocated node" >&2
    exit 2
fi

if [[ "${SLURM_NTASKS}" -ne 8 ]]; then
    echo "ERROR: expected eight allocated task slots" >&2
    exit 2
fi

if [[ -e "${SMOKE_DIRECTORY}" ]]; then
    echo "ERROR: smoke directory already exists: ${SMOKE_DIRECTORY}" >&2
    exit 2
fi

mkdir -p "${SMOKE_DIRECTORY}/runs"

scontrol show job "${SLURM_JOB_ID}" \
    > "${SMOKE_DIRECTORY}/slurm-job.txt"

scontrol show hostnames "${SLURM_JOB_NODELIST}" \
    > "${SMOKE_DIRECTORY}/allocated-hosts.txt"

module list \
    2> "${SMOKE_DIRECTORY}/modules.txt" \
    || true

ALLOCATED_HOST="$(
    head -n 1 "${SMOKE_DIRECTORY}/allocated-hosts.txt"
)"

{
    echo "created_at=$(date -Is)"
    echo "job_id=${SLURM_JOB_ID}"
    echo "job_name=${SLURM_JOB_NAME}"
    echo "partition=${SLURM_JOB_PARTITION}"
    echo "allocated_nodes=${SLURM_JOB_NUM_NODES}"
    echo "allocated_tasks=${SLURM_NTASKS}"
    echo "allocated_nodelist=${SLURM_JOB_NODELIST}"
    echo "allocated_host=${ALLOCATED_HOST}"
    echo "purpose=validate_r6_and_r8_explicit_host_slots_and_gpu_mapping"
    echo "qe_executed=NO"
} > "${SMOKE_DIRECTORY}/smoke-metadata.txt"

cat > "${SMOKE_DIRECTORY}/plan.tsv" <<'PLAN'
order shape mpi_ranks ranks_per_node expected_layout
1 r6 6 6 6
2 r8 8 8 8
PLAN

run_shape() {
    local shape="$1"
    local ranks="$2"

    local directory="${SMOKE_DIRECTORY}/runs/${shape}"
    local host_spec="${ALLOCATED_HOST}:${ranks}"
    local mpirun_rc
    local mapping_count
    local unique_hosts
    local unique_gpus
    local shape_status

    mkdir -p \
        "${directory}/rank-mapping"

    export RUN_DIRECTORY="${directory}"

    echo "SMOKE_START shape=${shape} ranks=${ranks} host=${host_spec}"

    set +e
    mpirun \
        --bind-to none \
        --host "${host_spec}" \
        --np "${ranks}" \
        --map-by "ppr:${ranks}:node" \
        -x RUN_DIRECTORY \
        bash -c '
            set -euo pipefail

            GLOBAL_RANK="${OMPI_COMM_WORLD_RANK:?missing global rank}"
            LOCAL_RANK="${OMPI_COMM_WORLD_LOCAL_RANK:?missing local rank}"
            ORIGINAL_VISIBLE_GPUS="${CUDA_VISIBLE_DEVICES:-}"

            if [[ -n "${ORIGINAL_VISIBLE_GPUS}" ]]; then
                IFS="," read -r -a GPU_LIST <<< "${ORIGINAL_VISIBLE_GPUS}"

                if (( LOCAL_RANK >= ${#GPU_LIST[@]} )); then
                    echo "ERROR: local rank exceeds visible GPU count" >&2
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
        ' > "${directory}/stdout.txt" 2> "${directory}/stderr.txt"

    mpirun_rc=$?
    set +e

    mapping_count="$(
        find "${directory}/rank-mapping" \
            -maxdepth 1 \
            -type f \
            -name 'rank-*.txt' \
            | wc -l
    )"

    unique_hosts="$(
        awk '
            {
                for (i = 1; i <= NF; i++) {
                    if ($i ~ /^host=/) {
                        split($i, value, "=")
                        print value[2]
                    }
                }
            }
        ' "${directory}"/rank-mapping/rank-*.txt \
        2>/dev/null \
        | sort -u \
        | wc -l
    )"

    unique_gpus="$(
        awk '
            {
                for (i = 1; i <= NF; i++) {
                    if ($i ~ /^selected_gpu=/) {
                        split($i, value, "=")
                        print value[2]
                    }
                }
            }
        ' "${directory}"/rank-mapping/rank-*.txt \
        2>/dev/null \
        | sort -u \
        | wc -l
    )"

    shape_status="PASS"

    if [[ "${mpirun_rc}" -ne 0 ]]; then
        shape_status="FAIL"
    fi

    if [[ "${mapping_count}" -ne "${ranks}" ]]; then
        shape_status="FAIL"
    fi

    if [[ "${unique_hosts}" -ne 1 ]]; then
        shape_status="FAIL"
    fi

    if [[ "${unique_gpus}" -ne "${ranks}" ]]; then
        shape_status="FAIL"
    fi

    {
        echo "shape=${shape}"
        echo "expected_ranks=${ranks}"
        echo "host_spec=${host_spec}"
        echo "mpirun_rc=${mpirun_rc}"
        echo "mapping_count=${mapping_count}"
        echo "unique_hosts=${unique_hosts}"
        echo "unique_gpus=${unique_gpus}"
        echo "status=${shape_status}"
        echo "finished_at=$(date -Is)"
    } > "${directory}/smoke-status.txt"

    if [[ "${shape_status}" != "PASS" ]]; then
        SMOKE_FAILURES=$((SMOKE_FAILURES + 1))
    fi

    echo "SMOKE_END shape=${shape} status=${shape_status}"
}

run_shape "r6" 6
run_shape "r8" 8

ACTUAL_SHAPES="$(
    find "${SMOKE_DIRECTORY}/runs" \
        -mindepth 1 \
        -maxdepth 1 \
        -type d \
    | wc -l
)"

SMOKE_STATUS="PASS"

if [[ "${ACTUAL_SHAPES}" -ne 2 ]]; then
    SMOKE_FAILURES=$((SMOKE_FAILURES + 1))
    SMOKE_STATUS="FAIL"
fi

if [[ "${SMOKE_FAILURES}" -ne 0 ]]; then
    SMOKE_STATUS="FAIL"
fi

{
    echo "expected_shapes=2"
    echo "actual_shapes=${ACTUAL_SHAPES}"
    echo "launch_or_mapping_failures=${SMOKE_FAILURES}"
    echo "smoke_status=${SMOKE_STATUS}"
    echo "qe_executed=NO"
    echo "collector_status=NOT_APPLICABLE"
    echo "finished_at=$(date -Is)"
} > "${SMOKE_DIRECTORY}/execution-summary.txt"

echo "SMOKE_DIRECTORY=${SMOKE_DIRECTORY}"
echo "SMOKE_STATUS=${SMOKE_STATUS}"
echo "SMOKE_FAILURES=${SMOKE_FAILURES}"

if [[ "${SMOKE_STATUS}" == "PASS" ]]; then
    exit 0
fi

exit 1
