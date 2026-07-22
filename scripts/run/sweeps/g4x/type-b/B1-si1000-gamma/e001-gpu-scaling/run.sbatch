#!/usr/bin/env bash
#SBATCH --account=ACD114087
#SBATCH --partition=16gpus
#SBATCH --job-name=B1-e001-gpu
#SBATCH --exclude=25a-hgpn144
#SBATCH --nodes=2
#SBATCH --ntasks=16
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=12
#SBATCH --gres=gpu:8
#SBATCH --time=04:00:00
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
ATTEMPT_ID="e001-gpu-scaling"

SWEEP_NAME="type_b_gpu_scaling"
CASE_NAME="type_b"
SWEEP_DIRECTORY="${RUN_ROOT}/sweeps/${BUILD_ID}/${TYPE_ID}/${CASE_ID}/${ATTEMPT_ID}/job-${SLURM_JOB_ID}"
OPENMP_THREADS=12
EXPECTED_ENERGY_RY="-11418.55709692"
EXPECTED_SCF_ITERATIONS=20
EXPECTED_K_POINTS=1
TRIAL_PAUSE_SECONDS=5
export NUMERICAL_ENERGY_TOLERANCE_RY="${NUMERICAL_ENERGY_TOLERANCE_RY:-1e-7}"

source "${REPO}/scripts/env/nvhpc259.sh"
REPO_ROOT="$(
    git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel
)"
SWEEP_ROOT="${REPO_ROOT}/scripts/run/sweeps"
source "${SWEEP_ROOT}/lib/g4x_sweep_common.sh"

[[ "${SLURM_JOB_NUM_NODES}" -eq 2 ]] || sweep_die "expected 2 allocated nodes"
[[ "${SLURM_NTASKS}" -eq 16 ]] || sweep_die "expected 16 allocated tasks"
[[ ! -e "${SWEEP_DIRECTORY}" ]] || sweep_die "sweep directory already exists: ${SWEEP_DIRECTORY}"

require_exact_sha256 "${QE_EXECUTABLE}" "${G4X_EXPECTED_SHA256}"
require_exact_sha256 "${QE_INPUT_SOURCE}" "${TYPE_B_EXPECTED_INPUT_SHA256}"
write_sweep_provenance "${REPO}" "${SWEEP_DIRECTORY}" "${QE_EXECUTABLE}" "${QE_INPUT_SOURCE}"

cat > "${SWEEP_DIRECTORY}/plan.tsv" <<'PLAN'
order	trial_id	candidate	role	repeat	mpi_ranks	ranks_per_node	nk	expected_rank_layout	rationale
1	001-r16-r1	r16	baseline	1	16	8	1	8,8	current two-node shape
2	002-r8-r1	r8	primary	1	8	8	1	8	single-node full-GPU shape
3	003-r4-r1	r4	primary	1	4	4	1	4	single-node reduced-rank diagnostic for the scaling curve
4	004-r4-r2	r4	primary	2	4	4	1	4	interleaved repeat
5	005-r16-r2	r16	baseline	2	16	8	1	8,8	interleaved repeat
6	006-r8-r2	r8	primary	2	8	8	1	8	interleaved repeat
7	007-r8-r3	r8	primary	3	8	8	1	8	interleaved repeat
8	008-r4-r3	r4	primary	3	4	4	1	4	interleaved repeat
9	009-r16-r3	r16	baseline	3	16	8	1	8,8	interleaved repeat
PLAN

run_g4x_trial "001-r16-r1" "r16" "baseline" 1 1 16 8 1 "gpu_scaling" "8,8"
run_g4x_trial "002-r8-r1"  "r8"  "primary"  1 2 8  8 1 "gpu_scaling" "8"
run_g4x_trial "003-r4-r1"  "r4"  "primary"  1 3 4  4 1 "gpu_scaling" "4"
run_g4x_trial "004-r4-r2"  "r4"  "primary"  2 4 4  4 1 "gpu_scaling" "4"
run_g4x_trial "005-r16-r2" "r16" "baseline" 2 5 16 8 1 "gpu_scaling" "8,8"
run_g4x_trial "006-r8-r2"  "r8"  "primary"  2 6 8  8 1 "gpu_scaling" "8"
run_g4x_trial "007-r8-r3"  "r8"  "primary"  3 7 8  8 1 "gpu_scaling" "8"
run_g4x_trial "008-r4-r3"  "r4"  "primary"  3 8 4  4 1 "gpu_scaling" "4"
run_g4x_trial "009-r16-r3" "r16" "baseline" 3 9 16 8 1 "gpu_scaling" "8,8"

finalize_g4x_sweep
