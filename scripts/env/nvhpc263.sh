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
