#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 4 || $# -gt 5 ]]; then
    echo "Usage: $0 CASE_ID QE_BIN QE_INPUT NPOOL [LABEL]" >&2
    exit 2
fi

CASE_ID="$1"
QE_BIN="$2"
QE_INPUT="$3"
NPOOL="$4"
LABEL="${5:-baseline}"

REPO="/work/${USER}/hipac26-qe"
STAMP="$(date +%Y%m%d_%H%M%S)"
RUN_DIR="/work/${USER}/hipac26-qe-runs/simple/${CASE_ID}/${LABEL}_${STAMP}"
SBATCH_SCRIPT="${REPO}/scripts/run/qe_2node_16gpu.sbatch"

test -x "${QE_BIN}"
test -f "${QE_INPUT}"
test -f "${SBATCH_SCRIPT}"

mkdir -p "${RUN_DIR}"

submit_output="$(
    sbatch \
        --job-name="qe-${CASE_ID}" \
        --chdir="${RUN_DIR}" \
        --export="ALL,QE_BIN=${QE_BIN},QE_INPUT=${QE_INPUT},RUN_DIR=${RUN_DIR},NPOOL=${NPOOL},OMP_NUM_THREADS=12" \
        "${SBATCH_SCRIPT}"
)"

printf '%s\n' "${submit_output}"

job_id="$(awk '/Submitted batch job/ {print $4}' <<< "${submit_output}")"

if [[ ! "${job_id}" =~ ^[0-9]+$ ]]; then
    echo "ERROR: unable to parse Slurm job ID" >&2
    exit 2
fi

printf '%s\n' "${job_id}" > "${RUN_DIR}/job_id.txt"

echo "JOB_ID=${job_id}"
echo "RUN_DIR=${RUN_DIR}"
