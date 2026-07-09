#!/usr/bin/env bash
#SBATCH --job-name=BUILD-SMOKE-T001-G1-smoke-si8
#SBATCH --account=ACD114087
#SBATCH --partition=dev
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=12
#SBATCH --gres=gpu:1
#SBATCH --time=00:20:00
#SBATCH --output=/work/%u/hipac26-qe-runs/slurm/%x-%j.out
#SBATCH --error=/work/%u/hipac26-qe-runs/slurm/%x-%j.err

set -euo pipefail

USER_NAME="${USER}"
WORKROOT="/work/${USER_NAME}"
REPO="${WORKROOT}/hipac26-qe"
BUILDROOT="${WORKROOT}/hipac26-qe-builds"
CASEROOT="${WORKROOT}/hipac26-qe-cases"
PSEUDOROOT="${WORKROOT}/hipac26-qe-pseudos"
RUNROOT="${WORKROOT}/hipac26-qe-runs"
TOKEN="${WORKROOT}/hipac26-qe-local/ALLOW_QE_EXECUTION"

GATE_ID="${GATE_ID:-BUILD-SMOKE-T001}"
RUN_TYPE="${RUN_TYPE:-smoke}"
BUILD_ID="${BUILD_ID:-G1-qe75-nvhpc259-gpu-base}"
CASE_NAME="${CASE_NAME:-smoke-si8}"
BUILD_HASH="${BUILD_HASH:-d2b0d6221e4a1d18dfdb6407baad3f428c52a3e8e3c2dde8bd301827f3c66543}"
PWX="${PWX:-${BUILDROOT}/${BUILD_ID}/install/bin/pw.x}"

# Initialize environment modules in non-interactive Slurm shell.
if ! command -v module >/dev/null 2>&1; then
  if [ -f /etc/profile.d/modules.sh ]; then
    # shellcheck disable=SC1091
    source /etc/profile.d/modules.sh
  elif [ -f /usr/share/Modules/init/bash ]; then
    # shellcheck disable=SC1091
    source /usr/share/Modules/init/bash
  fi
fi

# Provide the same helper expected by scripts/env/*.sh.
COMMON="${REPO}/scripts/lib/common.sh"
if [ -f "${COMMON}" ]; then
  # shellcheck disable=SC1090
  source "${COMMON}"
fi

if ! command -v ensure_module >/dev/null 2>&1; then
  ensure_module() {
    local mod
    for mod in "$@"; do
      module load "${mod}"
    done
  }
fi

ENV_SCRIPT="${REPO}/scripts/env/nvhpc259.sh"
if [ -f "${ENV_SCRIPT}" ]; then
  # Load the same NVHPC/HPC-X runtime route used by the G1 build.
  # shellcheck disable=SC1090
  source "${ENV_SCRIPT}"
else
  ensure_module x86-nvhpc/25.9 cmake/4.0.0
fi


if ! command -v mpirun >/dev/null 2>&1; then
  echo "ERROR: mpirun not found after NVHPC environment load" >&2
  exit 94
fi

if ! mpirun --bind-to none -np 1 true >/dev/null 2>&1; then
  echo "ERROR: mpirun cannot initialize (OPAL_PREFIX=${OPAL_PREFIX:-unset})" >&2
  exit 94
fi

mkdir -p "${RUNROOT}/slurm"

if [ ! -f "${TOKEN}" ]; then
  echo "ERROR: missing QE execution token: ${TOKEN}" >&2
  echo "Refusing to run pw.x." >&2
  exit 90
fi

ENV_FILE="$(
  python3 "${REPO}/scripts/qe_smoke_prepare.py" \
    --workroot "${WORKROOT}" \
    --repo "${REPO}" \
    --buildroot "${BUILDROOT}" \
    --caseroot "${CASEROOT}" \
    --pseudoroot "${PSEUDOROOT}" \
    --runroot "${RUNROOT}" \
    --gate-id "${GATE_ID}" \
    --run-type "${RUN_TYPE}" \
    --build-id "${BUILD_ID}" \
    --case-name "${CASE_NAME}" \
    --build-hash "${BUILD_HASH}" \
    --pwx "${PWX}" \
    --slurm-job-id "${SLURM_JOB_ID:-}" \
    --partition "${SLURM_JOB_PARTITION:-dev}" \
    --nodes "${SLURM_JOB_NUM_NODES:-1}" \
    --ntasks "${SLURM_NTASKS:-1}" \
    --ntasks-per-node "1" \
    --cpus-per-task "${SLURM_CPUS_PER_TASK:-12}" \
    --gres "gpu:1" \
    --time-limit "00:20:00"
)"

# shellcheck disable=SC1090
source "${ENV_FILE}"

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-12}"

set +e
cd "${RUN_DIR}"
mpirun --bind-to none -np 1 "${PWX_RESOLVED}" -in "${PW_INPUT}" > "${PW_OUT}" 2> "${PW_ERR}"
QE_EXIT=$?
set -e

python3 "${REPO}/scripts/parse_qe_smoke.py" \
  --pw-out "${PW_OUT}" \
  --pw-err "${PW_ERR}" \
  --metadata "${METADATA_JSON}" \
  --out "${PARSED_JSON}" || true

python3 "${REPO}/scripts/qe_smoke_finalize.py" \
  --metadata "${METADATA_JSON}" \
  --parsed "${PARSED_JSON}" \
  --qe-exit-code "${QE_EXIT}"

python3 "${REPO}/scripts/collect_qe_runs.py" \
  --root "${RUNROOT}" \
  --csv "${RUNROOT}/results.csv" \
  --xlsx "${RUNROOT}/qe_results.xlsx" || true

echo "RUN_DIR=${RUN_DIR}"
exit "${QE_EXIT}"
