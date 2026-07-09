#!/usr/bin/env bash
# GCC 13.2 serial sanity route.
ensure_module
module purge
module load gcc/13.2 cmake/4.0.0
export FC=gfortran
export CC=gcc
export CXX=g++
export HIPAC_BUILD_ROUTE="gcc/13.2-serial"
