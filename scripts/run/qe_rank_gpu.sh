#!/usr/bin/env bash
set -euo pipefail

LOCAL_RANK="${OMPI_COMM_WORLD_LOCAL_RANK:-${SLURM_LOCALID:-}}"

if [[ -z "${LOCAL_RANK}" ]]; then
    echo "ERROR: unable to determine local MPI rank" >&2
    exit 2
fi

export CUDA_VISIBLE_DEVICES="${LOCAL_RANK}"

printf 'host=%s global_rank=%s local_rank=%s cuda_visible_devices=%s\n' \
    "$(hostname)" \
    "${OMPI_COMM_WORLD_RANK:-unknown}" \
    "${LOCAL_RANK}" \
    "${CUDA_VISIBLE_DEVICES}" \
    >> "${RUN_DIR}/rank_mapping.tsv"

exec "$@"
