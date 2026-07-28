#!/usr/bin/env bash
#SBATCH --account=ACD114087
#SBATCH --partition=8gpus
#SBATCH --job-name=B1-e002-refine
#SBATCH --exclude=25a-hgpn144
#SBATCH --nodes=1
#SBATCH --ntasks=8
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=12
#SBATCH --gres=gpu:8
#SBATCH --time=01:00:00
#SBATCH --output=/work/%u/hipac26-qe-runs/slurm/%x-%j.out
#SBATCH --error=/work/%u/hipac26-qe-runs/slurm/%x-%j.err

set -uo pipefail
umask 027

REPO="/work/${USER}/hipac26-qe"
RUN_ROOT="/work/${USER}/hipac26-qe-runs"

QE_EXECUTABLE="/work/${USER}/hipac26-qe-builds/G4X-qe75-nvhpc259-h200-sm90-noelpa/install/bin/pw.x"
QE_INPUT_SOURCE="/work/${USER}/hipac26-qe-cases/typeB-si1000-gamma/pw.in"

BUILD_ID="g4x"
TYPE_ID="type-b"
CASE_ID="B1-si1000-gamma"
ATTEMPT_ID="e002-single-node-refinement"

SWEEP_NAME="B1_single_node_gpu_refinement"
CASE_NAME="type_b"

SWEEP_DIRECTORY="${RUN_ROOT}/sweeps/${BUILD_ID}/${TYPE_ID}/${CASE_ID}/${ATTEMPT_ID}/job-${SLURM_JOB_ID}"

OPENMP_THREADS=12
EXPECTED_ENERGY_RY="-11418.55709692"
EXPECTED_SCF_ITERATIONS=20
EXPECTED_K_POINTS=1
TRIAL_PAUSE_SECONDS=5

export NUMERICAL_ENERGY_TOLERANCE_RY="${NUMERICAL_ENERGY_TOLERANCE_RY:-1e-7}"

source "${REPO}/scripts/env/nvhpc259.sh"

REPO_ROOT="${REPO}"
SWEEP_ROOT="${REPO_ROOT}/scripts/run/sweeps"
source "${SWEEP_ROOT}/lib/g4x_sweep_common.sh"

[[ "${SLURM_JOB_NUM_NODES}" -eq 1 ]] \
    || sweep_die "expected one allocated node"

[[ "${SLURM_NTASKS}" -eq 8 ]] \
    || sweep_die "expected eight allocated task slots"

[[ ! -e "${SWEEP_DIRECTORY}" ]] \
    || sweep_die "sweep directory already exists: ${SWEEP_DIRECTORY}"

require_exact_sha256 \
    "${QE_EXECUTABLE}" \
    "${G4X_EXPECTED_SHA256}"

require_exact_sha256 \
    "${QE_INPUT_SOURCE}" \
    "${TYPE_B_EXPECTED_INPUT_SHA256}"

write_sweep_provenance \
    "${REPO}" \
    "${SWEEP_DIRECTORY}" \
    "${QE_EXECUTABLE}" \
    "${QE_INPUT_SOURCE}"

cat > "${SWEEP_DIRECTORY}/plan.tsv" <<'PLAN'
order trial_id candidate role repeat mpi_ranks ranks_per_node nk expected_rank_layout rationale
1 001-r6-c1 r6 challenger 1 6 6 1 6 first paired comparison
2 002-r8-c1 r8 baseline 1 8 8 1 8 first paired comparison
3 003-r8-c2 r8 baseline 2 8 8 1 8 reversed order
4 004-r6-c2 r6 challenger 2 6 6 1 6 reversed order
5 005-r6-c3 r6 challenger 3 6 6 1 6 interleaved repeat
6 006-r8-c3 r8 baseline 3 8 8 1 8 interleaved repeat
7 007-r8-c4 r8 baseline 4 8 8 1 8 reversed order
8 008-r6-c4 r6 challenger 4 6 6 1 6 reversed order
9 009-r6-c5 r6 challenger 5 6 6 1 6 final paired comparison
10 010-r8-c5 r8 baseline 5 8 8 1 8 final paired comparison
PLAN

run_g4x_trial \
    "001-r6-c1" "r6" "challenger" \
    1 1 6 6 1 \
    "single_node_gpu_refinement" "6"

run_g4x_trial \
    "002-r8-c1" "r8" "baseline" \
    1 2 8 8 1 \
    "single_node_gpu_refinement" "8"

run_g4x_trial \
    "003-r8-c2" "r8" "baseline" \
    2 3 8 8 1 \
    "single_node_gpu_refinement" "8"

run_g4x_trial \
    "004-r6-c2" "r6" "challenger" \
    2 4 6 6 1 \
    "single_node_gpu_refinement" "6"

run_g4x_trial \
    "005-r6-c3" "r6" "challenger" \
    3 5 6 6 1 \
    "single_node_gpu_refinement" "6"

run_g4x_trial \
    "006-r8-c3" "r8" "baseline" \
    3 6 8 8 1 \
    "single_node_gpu_refinement" "8"

run_g4x_trial \
    "007-r8-c4" "r8" "baseline" \
    4 7 8 8 1 \
    "single_node_gpu_refinement" "8"

run_g4x_trial \
    "008-r6-c4" "r6" "challenger" \
    4 8 6 6 1 \
    "single_node_gpu_refinement" "6"

run_g4x_trial \
    "009-r6-c5" "r6" "challenger" \
    5 9 6 6 1 \
    "single_node_gpu_refinement" "6"

run_g4x_trial \
    "010-r8-c5" "r8" "baseline" \
    5 10 8 8 1 \
    "single_node_gpu_refinement" "8"

finalize_g4x_sweep
