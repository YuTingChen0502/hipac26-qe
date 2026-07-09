#!/usr/bin/env bash
# NVHPC 25.9 environment: CUDA 13.0 + HPC-X OpenMPI bundled in module.
ensure_module
module purge
module load x86-nvhpc/25.9 cmake/4.0.0
export FC=mpif90
export CC=mpicc
export CXX=mpic++
export HIPAC_SITE="nano4"
export HIPAC_PLATFORM="nano4_h200"
export HIPAC_GPU_TARGET="Hopper_cc90"
export HIPAC_CUDA_CC_CANDIDATE="90"
export HIPAC_BUILD_ROUTE="x86-nvhpc/25.9"
