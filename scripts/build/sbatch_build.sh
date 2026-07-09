#!/usr/bin/env bash
# build/sbatch_build.sh — gated build submit wrapper.
# usage after approval: bash build/sbatch_build.sh <G1|G1p|G2|G3|C1|C2|C3>
# This wrapper is the only allowed build-submit route.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/../lib/common.sh"

CAND="${1:?usage: sbatch_build.sh <candidate>}"
CONF="${SCRIPT_DIR}/candidates.d/${CAND}.conf"
[[ -f "${CONF}" ]] || die "unknown candidate: ${CAND} (no ${CONF})"
require_allow_build_submit

# shellcheck disable=SC1090
source "${CONF}"
: "${ACCOUNT:=ACD114087}"
: "${GPU_PART:=dev}"

mkdir -p "${QE_RUNROOT}/buildlogs"

sbatch \
  --account="${ACCOUNT}" \
  --partition="${GPU_PART}" \
  --nodes=1 \
  --ntasks=1 \
  --cpus-per-task=12 \
  --gres=gpu:1 \
  --time=02:00:00 \
  --job-name="qeb-${CAND}" \
  --output="${QE_RUNROOT}/buildlogs/%x-%j.out" \
  --wrap "bash ${SCRIPT_DIR}/build_qe.sh ${CAND}"
