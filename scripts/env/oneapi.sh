#!/usr/bin/env bash
# Optional oneAPI route. Not part of first GPU-first path unless manually approved.
ensure_module
module purge
module load oneapi/2025.1 cmake/4.0.0
export FC=mpiifx
export CC=mpiicx
export CXX=mpiicpx
if [[ -z "${MKLROOT:-}" ]]; then
  echo "WARN: MKLROOT not set; verify oneAPI module before use." >&2
fi
export HIPAC_BUILD_ROUTE="oneapi/2025.1"
