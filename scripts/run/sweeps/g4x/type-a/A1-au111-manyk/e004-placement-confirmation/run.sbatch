#!/usr/bin/env bash
#SBATCH --account=ACD114087
#SBATCH --partition=16gpus
#SBATCH --job-name=A1-e004-confirm
#SBATCH --exclude=25a-hgpn144
#SBATCH --nodes=2
#SBATCH --ntasks=16
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=12
#SBATCH --gres=gpu:8
#SBATCH --time=02:00:00
#SBATCH --output=/work/%u/hipac26-qe-runs/slurm/%x-%j.out
#SBATCH --error=/work/%u/hipac26-qe-runs/slurm/%x-%j.err

set -uo pipefail
umask 027

REPO="/work/${USER}/hipac26-qe"
RUN_ROOT="/work/${USER}/hipac26-qe-runs"
QE_EXECUTABLE="/work/${USER}/hipac26-qe-builds/G4X-qe75-nvhpc259-h200-sm90-noelpa/install/bin/pw.x"
QE_INPUT_SOURCE="/work/${USER}/hipac26-qe-cases/typeA-au111-manyk/pw.in"

BUILD_ID="g4x"
TYPE_ID="type-a"
CASE_ID="A1-au111-manyk"
ATTEMPT_ID="e004-placement-confirmation"

SWEEP_NAME="A1_pool_placement_confirmation_nk7"
CASE_NAME="type_a"
SWEEP_DIRECTORY="${RUN_ROOT}/sweeps/${BUILD_ID}/${TYPE_ID}/${CASE_ID}/${ATTEMPT_ID}/job-${SLURM_JOB_ID}"
OPENMP_THREADS=12
EXPECTED_ENERGY_RY="-11426.06699031"
EXPECTED_SCF_ITERATIONS=15
EXPECTED_K_POINTS=7
TRIAL_PAUSE_SECONDS=5
export NUMERICAL_ENERGY_TOLERANCE_RY="${NUMERICAL_ENERGY_TOLERANCE_RY:-1e-6}"

source "${REPO}/scripts/env/nvhpc259.sh"
REPO_ROOT="${REPO}"
SWEEP_ROOT="${REPO_ROOT}/scripts/run/sweeps"
source "${SWEEP_ROOT}/lib/g4x_sweep_common.sh"

[[ "${SLURM_JOB_NUM_NODES}" -eq 2 ]] || sweep_die "expected 2 allocated nodes"
[[ "${SLURM_NTASKS}" -eq 16 ]] || sweep_die "expected 16 allocated task slots"
[[ ! -e "${SWEEP_DIRECTORY}" ]] || sweep_die "sweep directory already exists: ${SWEEP_DIRECTORY}"

require_exact_sha256 "${QE_EXECUTABLE}" "${G4X_EXPECTED_SHA256}"
require_exact_sha256 "${QE_INPUT_SOURCE}" "${TYPE_A_EXPECTED_INPUT_SHA256}"
write_sweep_provenance "${REPO}" "${SWEEP_DIRECTORY}" "${QE_EXECUTABLE}" "${QE_INPUT_SOURCE}"

cat > "${SWEEP_DIRECTORY}/plan.tsv" <<'PLAN'
order	trial_id	candidate	role	repeat	mpi_ranks	ranks_per_node	nk	expected_rank_layout	rationale
1	001-map7x7-r1	map7x7	baseline	1	14	7	7	7,7	current layout; pool pair 6/7 crosses nodes if pool ranks are contiguous
2	002-map8x6-r1	map8x6	primary	1	14	8	7	8,6	packs all contiguous two-rank pools within one node
3	003-map8x6-r2	map8x6	primary	2	14	8	7	8,6	interleaved repeat
4	004-map7x7-r2	map7x7	baseline	2	14	7	7	7,7	interleaved repeat
5	005-map7x7-r3	map7x7	baseline	3	14	7	7	7,7	interleaved repeat
6	006-map8x6-r3	map8x6	primary	3	14	8	7	8,6	interleaved repeat
PLAN

run_g4x_trial "001-map8x6-c1" "map8x6" "primary"  1 1  14 8 7 "pool_placement_confirmation" "8,6"
run_g4x_trial "002-map7x7-c1" "map7x7" "baseline" 1 2  14 7 7 "pool_placement_confirmation" "7,7"
run_g4x_trial "003-map7x7-c2" "map7x7" "baseline" 2 3  14 7 7 "pool_placement_confirmation" "7,7"
run_g4x_trial "004-map8x6-c2" "map8x6" "primary"  2 4  14 8 7 "pool_placement_confirmation" "8,6"
run_g4x_trial "005-map8x6-c3" "map8x6" "primary"  3 5  14 8 7 "pool_placement_confirmation" "8,6"
run_g4x_trial "006-map7x7-c3" "map7x7" "baseline" 3 6  14 7 7 "pool_placement_confirmation" "7,7"
run_g4x_trial "007-map7x7-c4" "map7x7" "baseline" 4 7  14 7 7 "pool_placement_confirmation" "7,7"
run_g4x_trial "008-map8x6-c4" "map8x6" "primary"  4 8  14 8 7 "pool_placement_confirmation" "8,6"
run_g4x_trial "009-map8x6-c5" "map8x6" "primary"  5 9  14 8 7 "pool_placement_confirmation" "8,6"
run_g4x_trial "010-map7x7-c5" "map7x7" "baseline" 5 10 14 7 7 "pool_placement_confirmation" "7,7"

finalize_g4x_sweep
