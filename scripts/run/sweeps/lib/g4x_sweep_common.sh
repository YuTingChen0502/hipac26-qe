#!/usr/bin/env bash
# Common runtime for controlled, unprofiled G4X sweeps on Nano4.
# This file is sourced by the sweep sbatch scripts.

export PYTHONDONTWRITEBYTECODE=1

G4X_EXPECTED_SHA256="64968da5119d9e33b8639ad4e60e449b379f4f254ae9d09df2de1e0974d5a473"
TYPE_A_EXPECTED_INPUT_SHA256="7c9354016502431300025747b73aebe9ae2b3a6766c811fe0bf0e8a8066b03d2"
TYPE_B_EXPECTED_INPUT_SHA256="3efd3830a380a185e76124e8d7beba2111ea6c1333d8e946bbac199c1c06a340"

sweep_die() {
    echo "ERROR: $*" >&2
    exit 2
}

require_exact_sha256() {
    local path="$1"
    local expected="$2"
    local actual

    test -f "${path}" || sweep_die "missing file: ${path}"
    actual="$(sha256sum "${path}" | awk '{print $1}')"
    if [[ "${actual}" != "${expected}" ]]; then
        sweep_die "SHA-256 mismatch for ${path}: expected=${expected} actual=${actual}"
    fi
}

write_sweep_provenance() {
    local repo="$1"
    local sweep_directory="$2"
    local qe_executable="$3"
    local qe_input_source="$4"

    mkdir -p "${sweep_directory}/runs"

    {
        echo "created_at=$(date -Is)"
        echo "job_id=${SLURM_JOB_ID}"
        echo "job_name=${SLURM_JOB_NAME}"
        echo "partition=${SLURM_JOB_PARTITION}"
        echo "allocated_nodes=${SLURM_JOB_NUM_NODES}"
        echo "allocated_tasks=${SLURM_NTASKS}"
        echo "allocated_nodelist=${SLURM_JOB_NODELIST}"
        echo "repo=${repo}"
        echo "branch=$(git -C "${repo}" branch --show-current 2>/dev/null || true)"
        echo "head=$(git -C "${repo}" rev-parse HEAD 2>/dev/null || true)"
        echo "binary=${qe_executable}"
        echo "input=${qe_input_source}"
        echo "build_id=${BUILD_ID:-unset}"
        echo "type_id=${TYPE_ID:-unset}"
        echo "case_id=${CASE_ID:-unset}"
        echo "attempt_id=${ATTEMPT_ID:-unset}"
        echo "sweep_name=${SWEEP_NAME:-unset}"
        echo "case_name=${CASE_NAME:-unset}"
    } > "${sweep_directory}/sweep-metadata.txt"

    scontrol show job "${SLURM_JOB_ID}" > "${sweep_directory}/slurm-job.txt"
    scontrol show hostnames "${SLURM_JOB_NODELIST}" > "${sweep_directory}/allocated-hosts.txt"
    module list 2> "${sweep_directory}/modules.txt" || true
    sha256sum "${qe_executable}" "${qe_input_source}" > "${sweep_directory}/sha256sums.txt"
}

run_g4x_trial() {
    if [[ "$#" -ne 10 ]]; then
        sweep_die "run_g4x_trial requires 10 arguments"
    fi

    local trial_id="$1"
    local candidate="$2"
    local candidate_role="$3"
    local repeat_index="$4"
    local order_index="$5"
    local mpi_ranks="$6"
    local ranks_per_node="$7"
    local k_point_pools="$8"
    local parameter_family="$9"
    local expected_rank_layout="${10}"

    local run_directory="${SWEEP_DIRECTORY}/runs/${trial_id}"
    local qe_input_copy="${run_directory}/pw.in"
    local previous_directory="${PWD}"
    local qe_exit_code
    local parser_exit_code
    local active_node_count
    local selected_host_csv

    if [[ -e "${run_directory}" ]]; then
        echo "TRIAL_REFUSED existing_run_directory=${run_directory}" >&2
        return 91
    fi

    if (( mpi_ranks < 1 || ranks_per_node < 1 || k_point_pools < 1 )); then
        echo "TRIAL_REFUSED invalid_positive_integer trial=${trial_id}" >&2
        return 92
    fi

    if (( mpi_ranks % k_point_pools != 0 )); then
        echo "TRIAL_REFUSED nk_does_not_divide_mpi_ranks trial=${trial_id}" >&2
        return 93
    fi

    active_node_count=$(( (mpi_ranks + ranks_per_node - 1) / ranks_per_node ))
    selected_host_csv="$(
        head -n "${active_node_count}" "${SWEEP_DIRECTORY}/allocated-hosts.txt" |
        awk -v slots="${ranks_per_node}" '
            BEGIN {
                separator = ""
            }
            {
                printf "%s%s:%s", separator, $0, slots
                separator = ","
            }
            END {
                print ""
            }
        '
    )"
    if [[ -z "${selected_host_csv}" ]]; then
        echo "TRIAL_REFUSED no_selected_hosts trial=${trial_id}" >&2
        return 96
    fi

    mkdir -p \
        "${run_directory}/out" \
        "${run_directory}/rank-mapping"

    cp "${QE_INPUT_SOURCE}" "${qe_input_copy}"

    python3 - \
        "${run_directory}/run-metadata.json" \
        "${trial_id}" \
        "${candidate}" \
        "${candidate_role}" \
        "${repeat_index}" \
        "${order_index}" \
        "${mpi_ranks}" \
        "${ranks_per_node}" \
        "${k_point_pools}" \
        "${parameter_family}" \
        "${expected_rank_layout}" \
        "${OPENMP_THREADS}" \
        "${QE_EXECUTABLE}" \
        "${QE_INPUT_SOURCE}" \
        "${SWEEP_NAME}" \
        "${CASE_NAME}" \
        "${EXPECTED_ENERGY_RY}" \
        "${EXPECTED_SCF_ITERATIONS}" \
        "${EXPECTED_K_POINTS}" \
        "${SLURM_JOB_ID}" \
        "${SLURM_JOB_NODELIST}" \
        "${selected_host_csv}" <<'PY'
import json
import sys
from datetime import datetime, timezone

(
    output,
    trial_id,
    candidate,
    candidate_role,
    repeat_index,
    order_index,
    mpi_ranks,
    ranks_per_node,
    k_point_pools,
    parameter_family,
    expected_rank_layout,
    openmp_threads,
    binary,
    input_source,
    sweep_name,
    case_name,
    expected_energy_ry,
    expected_scf_iterations,
    expected_k_points,
    slurm_job_id,
    slurm_nodelist,
    selected_hosts,
) = sys.argv[1:]

metadata = {
    "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
    "trial_id": trial_id,
    "candidate": candidate,
    "candidate_role": candidate_role,
    "repeat_index": int(repeat_index),
    "order_index": int(order_index),
    "mpi_ranks": int(mpi_ranks),
    "ranks_per_node": int(ranks_per_node),
    "k_point_pools": int(k_point_pools),
    "parameter_family": parameter_family,
    "expected_rank_layout": expected_rank_layout,
    "openmp_threads": int(openmp_threads),
    "binary": binary,
    "input_source": input_source,
    "sweep_name": sweep_name,
    "case_name": case_name,
    "expected_energy_ry": float(expected_energy_ry),
    "expected_scf_iterations": int(expected_scf_iterations),
    "expected_k_points": int(expected_k_points),
    "slurm_job_id": slurm_job_id,
    "slurm_nodelist": slurm_nodelist,
    "selected_hosts": selected_hosts,
}
with open(output, "w", encoding="utf-8") as handle:
    json.dump(metadata, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY

    {
        echo "trial_id=${trial_id}"
        echo "candidate=${candidate}"
        echo "candidate_role=${candidate_role}"
        echo "repeat_index=${repeat_index}"
        echo "order_index=${order_index}"
        echo "mpi_ranks=${mpi_ranks}"
        echo "ranks_per_node=${ranks_per_node}"
        echo "k_point_pools=${k_point_pools}"
        echo "openmp_threads=${OPENMP_THREADS}"
        echo "expected_rank_layout=${expected_rank_layout}"
        echo "selected_hosts=${selected_host_csv}"
        echo "binary=${QE_EXECUTABLE}"
        echo "input=${QE_INPUT_SOURCE}"
    } > "${run_directory}/run-metadata.txt"

    sha256sum "${QE_EXECUTABLE}" "${qe_input_copy}" > "${run_directory}/sha256sums.txt"

    export OMP_NUM_THREADS="${OPENMP_THREADS}"
    export QE_EXECUTABLE
    export QE_INPUT_COPY="${qe_input_copy}"
    export K_POINT_POOLS="${k_point_pools}"
    export RUN_DIRECTORY="${run_directory}"

    echo "TRIAL_START order=${order_index} id=${trial_id} candidate=${candidate} mpi=${mpi_ranks} rpn=${ranks_per_node} nk=${k_point_pools}"

    cd "${run_directory}" || return 94

    set +e
    mpirun \
        --bind-to none \
        --host "${selected_host_csv}" \
        --np "${mpi_ranks}" \
        --map-by "ppr:${ranks_per_node}:node" \
        -x OMP_NUM_THREADS \
        -x QE_EXECUTABLE \
        -x QE_INPUT_COPY \
        -x K_POINT_POOLS \
        -x RUN_DIRECTORY \
        bash -c '
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

            exec "${QE_EXECUTABLE}" \
                -nk "${K_POINT_POOLS}" \
                -in "${QE_INPUT_COPY}"
        ' > "${run_directory}/qe.out" 2> "${run_directory}/qe.err"
    qe_exit_code=$?
    set +e

    cd "${previous_directory}" || exit 95

    printf '%s\n' "${qe_exit_code}" > "${run_directory}/qe-exit-code.txt"

    set +e
    python3 "${REPO}/scripts/parse_qe_smoke.py" \
        --pw-out "${run_directory}/qe.out" \
        --pw-err "${run_directory}/qe.err" \
        --pw-in "${qe_input_copy}" \
        --out "${run_directory}/parsed.json"
    parser_exit_code=$?
    set +e

    {
        echo "qe_exit_code=${qe_exit_code}"
        echo "parser_exit_code=${parser_exit_code}"
        echo "finished_at=$(date -Is)"
    } > "${run_directory}/trial-status.txt"

    echo "TRIAL_END order=${order_index} id=${trial_id} qe_rc=${qe_exit_code} parser_rc=${parser_exit_code}"

    sleep "${TRIAL_PAUSE_SECONDS}"
    return 0
}

finalize_g4x_sweep() {
    local collector_rc=0
    local expected_trials=0
    local actual_trials=0
    local count_mismatch=0
    local qe_failures=0
    local parser_failures=0
    local malformed_statuses=0
    local run_directory
    local qe_rc
    local parser_rc
    local -a run_directories=()

    # Collector classification is recorded, but does not define
    # whether QE execution itself succeeded.
    if python3 "${REPO}/scripts/collect_g4x_sweep.py" \
        --root "${SWEEP_DIRECTORY}"
    then
        collector_rc=0
    else
        collector_rc=$?
    fi

    printf '%s\n' "${collector_rc}" \
        > "${SWEEP_DIRECTORY}/collector-exit-code.txt"

    if [[ -f "${SWEEP_DIRECTORY}/plan.tsv" ]]; then
        expected_trials="$(
            awk '
                NR > 1 && NF {
                    count++
                }
                END {
                    print count + 0
                }
            ' "${SWEEP_DIRECTORY}/plan.tsv"
        )"
    else
        malformed_statuses=$((malformed_statuses + 1))
    fi

    mapfile -d '' run_directories < <(
        find "${SWEEP_DIRECTORY}/runs" \
            -mindepth 1 \
            -maxdepth 1 \
            -type d \
            -print0 |
        sort -z
    )

    actual_trials="${#run_directories[@]}"

    if (( actual_trials != expected_trials )); then
        count_mismatch=1
    fi

    for run_directory in "${run_directories[@]}"; do
        qe_rc=""
        parser_rc=""

        if [[ -f "${run_directory}/qe-exit-code.txt" ]]; then
            qe_rc="$(
                tr -d '[:space:]' \
                    < "${run_directory}/qe-exit-code.txt"
            )"
        fi

        if [[ -f "${run_directory}/trial-status.txt" ]]; then
            parser_rc="$(
                awk -F= '
                    $1 == "parser_exit_code" {
                        value = $2
                    }
                    END {
                        print value
                    }
                ' "${run_directory}/trial-status.txt"
            )"
        fi

        if [[ ! "${qe_rc}" =~ ^[0-9]+$ ]]; then
            echo "EXECUTION_STATUS_MALFORMED missing_or_invalid_qe_rc=${run_directory}" >&2
            malformed_statuses=$((malformed_statuses + 1))
        elif (( qe_rc != 0 )); then
            echo "QE_EXECUTION_FAILED rc=${qe_rc} run=${run_directory}" >&2
            qe_failures=$((qe_failures + 1))
        fi

        if [[ ! "${parser_rc}" =~ ^[0-9]+$ ]]; then
            echo "EXECUTION_STATUS_MALFORMED missing_or_invalid_parser_rc=${run_directory}" >&2
            malformed_statuses=$((malformed_statuses + 1))
        elif (( parser_rc != 0 )); then
            echo "QE_PARSER_FAILED rc=${parser_rc} run=${run_directory}" >&2
            parser_failures=$((parser_failures + 1))
        fi
    done

    {
        echo "expected_trials=${expected_trials}"
        echo "actual_trials=${actual_trials}"
        echo "count_mismatch=${count_mismatch}"
        echo "qe_failures=${qe_failures}"
        echo "parser_failures=${parser_failures}"
        echo "malformed_statuses=${malformed_statuses}"
        echo "collector_rc=${collector_rc}"
        echo "finished_at=$(date -Is)"
    } > "${SWEEP_DIRECTORY}/execution-summary.txt"

    echo "SWEEP_DIRECTORY=${SWEEP_DIRECTORY}"
    echo "SWEEP_COLLECTOR_RC=${collector_rc}"
    echo "SWEEP_EXPECTED_TRIALS=${expected_trials}"
    echo "SWEEP_ACTUAL_TRIALS=${actual_trials}"
    echo "SWEEP_QE_FAILURES=${qe_failures}"
    echo "SWEEP_PARSER_FAILURES=${parser_failures}"
    echo "SWEEP_MALFORMED_STATUSES=${malformed_statuses}"

    if (( collector_rc != 0 )); then
        echo "WARNING: collector classification failed; QE execution status is evaluated separately" >&2
    fi

    if (( count_mismatch != 0 ||
          qe_failures != 0 ||
          parser_failures != 0 ||
          malformed_statuses != 0 )); then
        echo "SWEEP_EXECUTION_STATUS=FAIL" >&2
        return 1
    fi

    echo "SWEEP_EXECUTION_STATUS=PASS"
    return 0
}
