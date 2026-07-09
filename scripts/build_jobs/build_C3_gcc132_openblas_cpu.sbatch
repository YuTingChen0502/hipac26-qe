#!/usr/bin/env bash
#SBATCH --account=ACD114087
#SBATCH --partition=dev
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --gres=gpu:1
#SBATCH --time=02:00:00
#SBATCH --job-name=C3-qe75-gcc132-openblas-cpu
#SBATCH --output=/work/%u/hipac26-qe-runs/buildlogs/%x-%j.out

set -euo pipefail

test -f /work/$USER/hipac26-qe-local/ALLOW_BUILD_EXECUTION

export HOME=/work/$USER
export XDG_CONFIG_HOME=/work/$USER/.config
mkdir -p "$XDG_CONFIG_HOME"

if type module >/dev/null 2>&1; then :; else
  [ -r /etc/profile.d/modules.sh ] && source /etc/profile.d/modules.sh
  [ -r /etc/profile.d/lmod.sh ] && source /etc/profile.d/lmod.sh
fi

module purge
module load gcc/13.2 cmake/4.0.0

OPENBLAS=/opt/ohpc/pub/libs/gnu12/openblas/0.3.21
test -f "$OPENBLAS/lib/libopenblas.so"
export LD_LIBRARY_PATH="$OPENBLAS/lib:${LD_LIBRARY_PATH:-}"

export FC=gfortran
export CC=gcc
export CXX=g++

SRC=/work/$USER/hipac26-qe-src/qe-7.5
CID=C3-qe75-gcc132-openblas-cpu
CDIR=/work/$USER/hipac26-qe-builds/$CID
BUILD="$CDIR/build"
INSTALL="$CDIR/install"
MANIFEST="$CDIR/manifest"

mkdir -p "$CDIR" "$INSTALL/bin" "$MANIFEST"
rm -rf "$BUILD"
mkdir -p "$BUILD"

echo "===== $CID build start ====="
date
hostname
module list 2>&1 | tee "$MANIFEST/modules.txt"
env | sort > "$MANIFEST/env.txt"

echo "OPENBLAS=$OPENBLAS" | tee "$MANIFEST/openblas.txt"
ls -lah "$OPENBLAS/lib/libopenblas.so" | tee -a "$MANIFEST/openblas.txt"

which gfortran
which gcc
gfortran --version | head -n 5

test -f "$SRC/CMakeLists.txt"
test -d "$SRC/PW"
git -C "$SRC" rev-parse HEAD | tee "$MANIFEST/qe_source_head.txt" || true

cmake -S "$SRC" -B "$BUILD" \
  -DCMAKE_INSTALL_PREFIX="$INSTALL" \
  -DCMAKE_Fortran_COMPILER=gfortran \
  -DCMAKE_C_COMPILER=gcc \
  -DCMAKE_CXX_COMPILER=g++ \
  -DCMAKE_BUILD_TYPE=Release \
  -DQE_ENABLE_MPI=OFF \
  -DQE_ENABLE_CUDA=OFF \
  -DQE_ENABLE_OPENACC=OFF \
  -DQE_ENABLE_OPENMP=OFF \
  -DQE_ENABLE_SCALAPACK=OFF \
  -DQE_LAPACK_INTERNAL=OFF \
  -DBLA_VENDOR=OpenBLAS \
  -DBLAS_LIBRARIES="$OPENBLAS/lib/libopenblas.so" \
  -DLAPACK_LIBRARIES="$OPENBLAS/lib/libopenblas.so" \
  -DQE_ENABLE_HDF5=OFF \
  -DQE_ENABLE_LIBXC=OFF \
  -DQE_FFTW_VENDOR=Internal \
  2>&1 | tee "$CDIR/build_cmake.log"

cmake --build "$BUILD" --target pw -j 12 2>&1 | tee "$CDIR/build_make.log"

if [ -x "$BUILD/bin/pw.x" ]; then
  cp "$BUILD/bin/pw.x" "$INSTALL/bin/pw.x"
elif [ -x "$BUILD/PW/src/pw.x" ]; then
  cp "$BUILD/PW/src/pw.x" "$INSTALL/bin/pw.x"
else
  echo "ERROR: pw.x not found after build"
  find "$BUILD" -name pw.x -type f -print
  exit 1
fi

sha256sum "$INSTALL/bin/pw.x" | tee "$MANIFEST/sha256.txt"
ldd "$INSTALL/bin/pw.x" > "$MANIFEST/ldd.txt" 2>&1 || true

{
  echo "candidate=$CID"
  echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "host=$(hostname)"
  echo "benchmark_valid=false"
  echo "qe_execution_in_build_exec=false"
  echo "openblas=$OPENBLAS"
} > "$MANIFEST/build_summary.txt"

echo "===== $CID build done ====="
