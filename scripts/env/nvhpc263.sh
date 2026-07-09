# Self-contained module bootstrap for non-interactive shells.
if ! command -v module >/dev/null 2>&1; then
  if [ -f /etc/profile.d/modules.sh ]; then
    # shellcheck disable=SC1091
    source /etc/profile.d/modules.sh
  elif [ -f /usr/share/Modules/init/bash ]; then
    # shellcheck disable=SC1091
    source /usr/share/Modules/init/bash
  fi
fi

if ! command -v ensure_module >/dev/null 2>&1; then
  ensure_module() {
    local mod
    for mod in "$@"; do
      module load "${mod}"
    done
  }
fi

#!/usr/bin/env bash
# NVHPC 26.3 environment. Verify bundled CUDA route before promotion.
ensure_module
module purge
module load x86-nvhpc/26.3 cmake/4.0.0
export FC=mpif90
export CC=mpicc
export CXX=mpic++
export HIPAC_SITE="nano4"
export HIPAC_PLATFORM="nano4_h200"
export HIPAC_GPU_TARGET="Hopper_cc90"
export HIPAC_CUDA_CC_CANDIDATE="90"
export HIPAC_BUILD_ROUTE="x86-nvhpc/26.3"

# HPC-X/OpenMPI may be installed as a relocated tree on nano4.
# OPAL_PREFIX tells OpenMPI where to find help files and MCA plugins.
if command -v mpirun >/dev/null 2>&1; then
  OMPI_BIN="$(dirname "$(command -v mpirun)")"
  export OPAL_PREFIX="$(dirname "${OMPI_BIN}")"
fi

