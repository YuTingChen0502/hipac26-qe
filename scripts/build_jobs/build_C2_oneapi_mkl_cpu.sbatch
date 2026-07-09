#!/usr/bin/env bash
#SBATCH --account=ACD114087
#SBATCH --partition=dev
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --gres=gpu:1
#SBATCH --time=02:00:00
#SBATCH --job-name=C2-qe75-oneapi-mkl-cpu
#SBATCH --output=/work/%u/hipac26-qe-runs/buildlogs/%x-%j.out

set -euo pipefail

test -f /work/$USER/hipac26-qe-local/ALLOW_BUILD_EXECUTION

export HOME=/work/$USER
export XDG_CONFIG_HOME=/work/$USER/.config
mkdir -p "$XDG_CONFIG_HOME"

ROOT=/work/$USER/hipac26-qe
SRC=/work/$USER/hipac26-qe-src/qe-7.5
CID=C2-qe75-oneapi-mkl-cpu
CDIR=/work/$USER/hipac26-qe-builds/$CID
BUILD="$CDIR/build"
INSTALL="$CDIR/install"
MANIFEST="$CDIR/manifest"

if type module >/dev/null 2>&1; then :; else
  [ -r /etc/profile.d/modules.sh ] && source /etc/profile.d/modules.sh
  [ -r /etc/profile.d/lmod.sh ] && source /etc/profile.d/lmod.sh
fi

module purge

# Reuse the existing env route if present; then record exactly what it did.
if [ -f "$ROOT/scripts/env/oneapi.sh" ]; then
  source "$ROOT/scripts/env/oneapi.sh"
else
  module load oneapi cmake/4.0.0
fi

# Defensive compiler discovery after oneAPI env is loaded.
if command -v mpiifx >/dev/null 2>&1; then
  FC=${FC:-mpiifx}
elif command -v mpiifort >/dev/null 2>&1; then
  FC=${FC:-mpiifort}
elif command -v ifx >/dev/null 2>&1; then
  FC=${FC:-ifx}
else
  echo "ERROR: no oneAPI Fortran compiler found"
  exit 1
fi

if command -v mpiicx >/dev/null 2>&1; then
  CC=${CC:-mpiicx}
elif command -v icx >/dev/null 2>&1; then
  CC=${CC:-icx}
else
  echo "ERROR: no oneAPI C compiler found"
  exit 1
fi

if command -v mpiicpx >/dev/null 2>&1; then
  CXX=${CXX:-mpiicpx}
elif command -v icpx >/dev/null 2>&1; then
  CXX=${CXX:-icpx}
else
  echo "ERROR: no oneAPI C++ compiler found"
  exit 1
fi

export FC CC CXX

mkdir -p "$CDIR" "$INSTALL/bin" "$MANIFEST"
rm -rf "$BUILD"
mkdir -p "$BUILD"

echo "===== $CID build start ====="
date
hostname
module list 2>&1 | tee "$MANIFEST/modules.txt"
env | sort > "$MANIFEST/env.txt"

echo "===== compilers ====="
echo "FC=$FC"
echo "CC=$CC"
echo "CXX=$CXX"
which "$FC" || true
which "$CC" || true
which "$CXX" || true
"$FC" --version | head -n 10 || true
"$CC" --version | head -n 10 || true

echo "===== MKLROOT ====="
echo "MKLROOT=${MKLROOT:-UNSET}"

test -f "$SRC/CMakeLists.txt"
test -d "$SRC/PW"
git -C "$SRC" rev-parse HEAD | tee "$MANIFEST/qe_source_head.txt" || true

cmake -S "$SRC" -B "$BUILD" \
  -DCMAKE_INSTALL_PREFIX="$INSTALL" \
  -DCMAKE_Fortran_COMPILER="$FC" \
  -DCMAKE_C_COMPILER="$CC" \
  -DCMAKE_CXX_COMPILER="$CXX" \
  -DCMAKE_BUILD_TYPE=Release \
  -DQE_ENABLE_MPI=ON \
  -DQE_ENABLE_CUDA=OFF \
  -DQE_ENABLE_OPENACC=OFF \
  -DQE_ENABLE_OPENMP=ON \
  -DQE_ENABLE_SCALAPACK=ON \
  -DQE_ENABLE_HDF5=OFF \
  -DQE_ENABLE_LIBXC=OFF \
  -DQE_FFTW_VENDOR=Internal \
  -DBLA_VENDOR=Intel10_64lp \
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
