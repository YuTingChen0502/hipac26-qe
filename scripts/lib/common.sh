#!/usr/bin/env bash
# lib/common.sh — shared paths + manifest helpers for hipac26 QE builds.
# Sourced by build/run scripts. Do not execute directly.
set -euo pipefail
export QE_WORKROOT="/work/${USER}"
export QE_CTRL="${QE_WORKROOT}/hipac26-qe"
export QE_SRCROOT="${QE_WORKROOT}/hipac26-qe-src"
export QE_BUILDROOT="${QE_WORKROOT}/hipac26-qe-builds"
export QE_LIBROOT="${QE_WORKROOT}/hipac26-qe-libs"
export QE_PSEUDOS="${QE_WORKROOT}/hipac26-qe-pseudos"
export QE_CASES="${QE_WORKROOT}/hipac26-qe-cases"
export QE_RUNROOT="${QE_WORKROOT}/hipac26-qe-runs"
export QE_LOCAL="${QE_WORKROOT}/hipac26-qe-local"
export QE_TARBALL="${QE_WORKROOT}/qe-7.5-source.tar.gz"
export QE_SRC="${QE_SRCROOT}/qe-7.5"

if [[ -f "${QE_LOCAL}/site.env" ]]; then
  # shellcheck disable=SC1091
  source "${QE_LOCAL}/site.env"
fi

log() { printf '[%s] %s\n' "$(date +%F_%T)" "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }

ensure_module() {
  if type module >/dev/null 2>&1; then
    return 0
  fi
  if [[ -r /etc/profile.d/modules.sh ]]; then
    # shellcheck disable=SC1091
    source /etc/profile.d/modules.sh
  elif [[ -r /etc/profile.d/lmod.sh ]]; then
    # shellcheck disable=SC1091
    source /etc/profile.d/lmod.sh
  fi
  type module >/dev/null 2>&1 || die "module command unavailable"
}

require_file() {
  local f="$1"
  [[ -f "$f" ]] || die "missing required file: $f"
}

require_allow_build_execution() {
  [[ -f "${QE_LOCAL}/ALLOW_BUILD_EXECUTION" ]] || die "missing approval token: ${QE_LOCAL}/ALLOW_BUILD_EXECUTION"
}

require_allow_build_submit() {
  [[ -f "${QE_LOCAL}/ALLOW_BUILD_SUBMIT" ]] || die "missing approval token: ${QE_LOCAL}/ALLOW_BUILD_SUBMIT"
}

require_allow_qe_execution() {
  [[ -f "${QE_LOCAL}/ALLOW_QE_EXECUTION" ]] || die "missing approval token: ${QE_LOCAL}/ALLOW_QE_EXECUTION"
}

prepare_source() {
  mkdir -p "${QE_SRCROOT}"
  if [[ -d "${QE_SRC}" ]]; then
    log "source tree exists: ${QE_SRC}"
  else
    [[ -f "${QE_TARBALL}" ]] || die "tarball not found: ${QE_TARBALL}"
    log "extracting ${QE_TARBALL} -> ${QE_SRCROOT}"
    tar -xzf "${QE_TARBALL}" -C "${QE_SRCROOT}"
    if [[ ! -d "${QE_SRC}" ]]; then
      local top
      top="$(tar -tzf "${QE_TARBALL}" | head -1 | cut -d/ -f1)"
      [[ -d "${QE_SRCROOT}/${top}" ]] || die "cannot find extracted top dir: ${top}"
      mv "${QE_SRCROOT}/${top}" "${QE_SRC}"
    fi
  fi
  sha256sum "${QE_TARBALL}" > "${QE_SRCROOT}/qe-7.5-source.tar.gz.sha256"
}

# BUILD-EXEC stage must not execute pw.x.
# This function records provenance only.
snapshot_manifest() {
  local cdir="$1"
  local m="${cdir}/manifest"
  local pwx="${cdir}/install/bin/pw.x"
  mkdir -p "${m}"
  ensure_module
  module list > "${m}/modules.txt" 2>&1 || true
  env | sort > "${m}/env.txt"
  [[ -x "${pwx}" ]] || die "pw.x missing: ${pwx}"
  ldd "${pwx}" > "${m}/ldd.txt" 2>&1 || true
  sha256sum "${pwx}" > "${m}/sha256.txt"
  
  if [[ -f "${cdir}/build/CMakeCache.txt" ]]; then
    grep -E "QE_|CUDA|CMAKE_Fortran|CMAKE_C_COMPILER|CMAKE_CXX_COMPILER|CMAKE_BUILD_TYPE|BLAS|LAPACK|FFT|SCALAPACK|OPENMP|MPI" \
      "${cdir}/build/CMakeCache.txt" > "${m}/cmake_cache_snapshot.txt" || true
  fi
  
  if [[ -f "${cdir}/build_make.log" ]]; then
    grep -m10 -oE "cc90|compute_90|gpu=cc[0-9]+|cuda13\.0|CUDA|OpenACC|SCALAPACK|ScaLAPACK" \
      "${cdir}/build_make.log" > "${m}/gpu_arch_evidence.txt" 2>/dev/null || true
  fi
  
  {
    echo "candidate_dir=${cdir}"
    echo "pwx=${pwx}"
    echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "host=$(hostname)"
    echo "user=${USER}"
    echo "benchmark_valid=false"
    echo "qe_execution_in_build_exec=false"
  } > "${m}/build_summary.txt"
  log "manifest written: ${m}"
}
