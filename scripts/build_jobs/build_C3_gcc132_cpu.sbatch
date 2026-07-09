#!/usr/bin/env bash
#SBATCH --account=ACD114087
#SBATCH --partition=dev
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --gres=gpu:1
#SBATCH --time=02:00:00
#SBATCH --job-name=C3-qe75-gcc132-cpu-sanity
#SBATCH --output=/work/%u/hipac26-qe-runs/buildlogs/%x-%j.out

set -euo pipefail

# build only; no QE execution in this job
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

export FC=gfortran
export CC=gcc
export CXX=g++

SRC=/work/$USER/hipac26-qe-src/qe-7.5
CID=C3-qe75-gcc132-cpu-sanity
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
  -DQE_LAPACK_INTERNAL=ON \
  -DQE_ENABLE_HDF5=OFF \
  -DQE_ENABLE_LIBXC=OFF \
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
} > "$MANIFEST/build_summary.txt"

echo "===== $CID build done ====="
