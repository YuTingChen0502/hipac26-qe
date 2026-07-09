#!/usr/bin/env bash
# build/build_qe.sh — gated QE build driver.
# usage: bash build/build_qe.sh <G1|G1p|G2|G3|C1|C2|C3>
# Runs on current node. For GPU candidates, prefer sbatch_build.sh.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/../lib/common.sh"
CAND="${1:?usage: build_qe.sh <candidate>}"
CONF="${SCRIPT_DIR}/candidates.d/${CAND}.conf"
[[ -f "${CONF}" ]] || die "unknown candidate: ${CAND} (no ${CONF})"
require_allow_build_execution
# shellcheck disable=SC1090
source "${CONF}"
# shellcheck disable=SC1090
source "${SCRIPT_DIR}/../env/${ENVFILE}"

prepare_source
CDIR="${QE_BUILDROOT}/${CID}"
BUILD="${CDIR}/build"
INSTALL="${CDIR}/install"

mkdir -p "${CDIR}"
log "=== candidate ${CID} ==="
log "description=${DESCRIPTION:-}"
log "node=$(hostname)"
log "FC=${FC} -> $(command -v "${FC}" || true)"
"${FC}" --version 2>&1 | head -n 5 || true

if [[ "${CMAKE_FLAGS}" == *"QE_ENABLE_CUDA=ON"* ]]; then
  command -v nvfortran >/dev/null 2>&1 || die "nvfortran not visible for GPU build"
  command -v nvcc >/dev/null 2>&1 || log "WARN: nvcc not visible; NVHPC bundled CUDA may still be used"
fi

command -v "${FC}" >/dev/null 2>&1 || die "FC not found: ${FC}"
command -v "${CC}" >/dev/null 2>&1 || die "CC not found: ${CC}"

module list > "${CDIR}/module_list_before_build.txt" 2>&1 || true
env | sort > "${CDIR}/env_before_build.txt"
if command -v mpif90 >/dev/null 2>&1; then
  mpif90 -show > "${CDIR}/mpif90_show.txt" 2>&1 || true
fi
if command -v mpicc >/dev/null 2>&1; then
  mpicc -show > "${CDIR}/mpicc_show.txt" 2>&1 || true
fi

rm -rf "${BUILD}"
mkdir -p "${BUILD}"

{
  echo "# $(date +%F_%T) on $(hostname)"
  echo "candidate=${CAND}"
  echo "cid=${CID}"
  echo "description=${DESCRIPTION:-}"
  echo "cmake -S ${QE_SRC} -B ${BUILD} \\"
  echo "  -DCMAKE_INSTALL_PREFIX=${INSTALL} \\"
  echo "  -DCMAKE_C_COMPILER=${CC} \\"
  echo "  -DCMAKE_CXX_COMPILER=${CXX} \\"
  echo "  -DCMAKE_Fortran_COMPILER=${FC} \\"
  echo "  ${CMAKE_FLAGS}"
} > "${CDIR}/config_cmd.sh"

# shellcheck disable=SC2086
cmake -S "${QE_SRC}" -B "${BUILD}" \
  -DCMAKE_INSTALL_PREFIX="${INSTALL}" \
  -DCMAKE_C_COMPILER="${CC}" \
  -DCMAKE_CXX_COMPILER="${CXX}" \
  -DCMAKE_Fortran_COMPILER="${FC}" \
  ${CMAKE_FLAGS} 2>&1 | tee "${CDIR}/build_cmake.log"

make -C "${BUILD}" -j "${BUILD_JOBS:-16}" pw 2>&1 | tee "${CDIR}/build_make.log"
make -C "${BUILD}" install 2>&1 | tee -a "${CDIR}/build_make.log" || {
  mkdir -p "${INSTALL}/bin"
  if [[ -x "${BUILD}/bin/pw.x" ]]; then
    cp "${BUILD}/bin/pw.x" "${INSTALL}/bin/pw.x"
  elif [[ -x "${BUILD}/PW/src/pw.x" ]]; then
    cp "${BUILD}/PW/src/pw.x" "${INSTALL}/bin/pw.x"
  else
    die "make install failed and no fallback pw.x found"
  fi
}

[[ -x "${INSTALL}/bin/pw.x" ]] || die "build finished but ${INSTALL}/bin/pw.x missing"
snapshot_manifest "${CDIR}"
log "=== ${CID} DONE: ${INSTALL}/bin/pw.x ==="
