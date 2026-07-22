#!/usr/bin/env bash
#SBATCH --account=ACD114087
#SBATCH --partition=16gpus
#SBATCH --job-name=A1-e001-npool
#SBATCH --exclude=25a-hgpn144
#SBATCH --nodes=2
#SBATCH --ntasks=14
#SBATCH --ntasks-per-node=7
#SBATCH --cpus-per-task=12
#SBATCH --gres=gpu:7
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
ATTEMPT_ID="e001-npool-screen"

SWEEP_NAME="type_a_nk_coarse"
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
[[ "${SLURM_NTASKS}" -eq 14 ]] || sweep_die "expected 14 allocated tasks"
[[ ! -e "${SWEEP_DIRECTORY}" ]] || sweep_die "sweep directory already exists: ${SWEEP_DIRECTORY}"

require_exact_sha256 "${QE_EXECUTABLE}" "${G4X_EXPECTED_SHA256}"
require_exact_sha256 "${QE_INPUT_SOURCE}" "${TYPE_A_EXPECTED_INPUT_SHA256}"
write_sweep_provenance "${REPO}" "${SWEEP_DIRECTORY}" "${QE_EXECUTABLE}" "${QE_INPUT_SOURCE}"

cat > "${SWEEP_DIRECTORY}/plan.tsv" <<'PLAN'
order	trial_id	candidate	role	repeat	mpi_ranks	ranks_per_node	nk	expected_rank_layout	rationale
1	001-nk7-r1	nk7	baseline	1	14	7	7	7,7	current balanced 7-pool baseline
2	002-nk1-r1	nk1	primary	1	14	7	1	7,7	no k-pool decomposition
3	003-nk2-r1	nk2	diagnostic	1	14	7	2	7,7	legal rank split but 7 k-points are imbalanced across 2 pools
4	004-nk2-r2	nk2	diagnostic	2	14	7	2	7,7	interleaved repeat
5	005-nk7-r2	nk7	baseline	2	14	7	7	7,7	interleaved repeat
6	006-nk1-r2	nk1	primary	2	14	7	1	7,7	interleaved repeat
7	007-nk1-r3	nk1	primary	3	14	7	1	7,7	interleaved repeat
8	008-nk2-r3	nk2	diagnostic	3	14	7	2	7,7	interleaved repeat
9	009-nk7-r3	nk7	baseline	3	14	7	7	7,7	interleaved repeat
PLAN

run_g4x_trial "001-nk7-r1" "nk7" "baseline"   1 1 14 7 7 "npool" "7,7"
run_g4x_trial "002-nk1-r1" "nk1" "primary"    1 2 14 7 1 "npool" "7,7"
run_g4x_trial "003-nk2-r1" "nk2" "diagnostic" 1 3 14 7 2 "npool" "7,7"
run_g4x_trial "004-nk2-r2" "nk2" "diagnostic" 2 4 14 7 2 "npool" "7,7"
run_g4x_trial "005-nk7-r2" "nk7" "baseline"   2 5 14 7 7 "npool" "7,7"
run_g4x_trial "006-nk1-r2" "nk1" "primary"    2 6 14 7 1 "npool" "7,7"
run_g4x_trial "007-nk1-r3" "nk1" "primary"    3 7 14 7 1 "npool" "7,7"
run_g4x_trial "008-nk2-r3" "nk2" "diagnostic" 3 8 14 7 2 "npool" "7,7"
run_g4x_trial "009-nk7-r3" "nk7" "baseline"   3 9 14 7 7 "npool" "7,7"

finalize_g4x_sweep
