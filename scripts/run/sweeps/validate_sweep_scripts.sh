#!/usr/bin/env bash

set -euo pipefail

ROOT="$(
    cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
    pwd
)"

HELPER="${ROOT}/lib/g4x_sweep_common.sh"
COLLECTOR="${ROOT}/../../collect_g4x_sweep.py"

failed=0

fail() {
    echo "ERROR: $*" >&2
    failed=1
}

if [[ ! -f "$HELPER" ]]; then
    echo "ERROR: missing helper: $HELPER" >&2
    exit 1
fi

if [[ ! -f "$COLLECTOR" ]]; then
    echo "ERROR: missing collector: $COLLECTOR" >&2
    exit 1
fi

if ! bash -n "$HELPER"; then
    fail "helper syntax failed: ${HELPER#"$ROOT"/}"
fi

python3 - "$COLLECTOR" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text()
compile(source, str(path), "exec")
print(f"COLLECTOR_SYNTAX=PASS {path}")
PY

mapfile -d '' SCRIPTS < <(
    find "$ROOT" \
        -type f \
        -name 'run.sbatch' \
        -print0 |
    sort -z
)

if (( ${#SCRIPTS[@]} == 0 )); then
    echo "ERROR: no run.sbatch files found under $ROOT" >&2
    exit 1
fi

for script in "${SCRIPTS[@]}"; do
    relative="${script#"$ROOT"/}"

    printf 'VALIDATE\t%s\n' "$relative"

    if [[ ! "$relative" =~ ^([^/]+)/(type-[^/]+)/([^/]+)/(e[0-9]{3}-[^/]+)/run\.sbatch$ ]]; then
        fail "invalid hierarchy: $relative"
        continue
    fi

    expected_build="${BASH_REMATCH[1]}"
    expected_type="${BASH_REMATCH[2]}"
    expected_case="${BASH_REMATCH[3]}"
    expected_attempt="${BASH_REMATCH[4]}"

    if ! bash -n "$script"; then
        fail "shell syntax failed: $relative"
    fi

    for expected_line in \
        "BUILD_ID=\"${expected_build}\"" \
        "TYPE_ID=\"${expected_type}\"" \
        "CASE_ID=\"${expected_case}\"" \
        "ATTEMPT_ID=\"${expected_attempt}\""
    do
        if ! grep -Fqx "$expected_line" "$script"; then
            fail "missing identity '$expected_line': $relative"
        fi
    done

    repo_root_count="$(
        grep -c '^REPO_ROOT=' "$script" || true
    )"

    sweep_root_count="$(
        grep -c '^SWEEP_ROOT=' "$script" || true
    )"

    finalizer_count="$(
        grep -Fxc 'finalize_g4x_sweep' "$script" || true
    )"

    if [[ "$repo_root_count" -ne 1 ]]; then
        fail "REPO_ROOT count=$repo_root_count: $relative"
    fi

    if [[ "$sweep_root_count" -ne 1 ]]; then
        fail "SWEEP_ROOT count=$sweep_root_count: $relative"
    fi

    if [[ "$finalizer_count" -ne 1 ]]; then
        fail "finalizer count=$finalizer_count: $relative"
    fi

    if ! grep -Fq \
        'source "${SWEEP_ROOT}/lib/g4x_sweep_common.sh"' \
        "$script"
    then
        fail "canonical helper source missing: $relative"
    fi

    if ! grep -Fq \
        'SWEEP_DIRECTORY="${RUN_ROOT}/sweeps/${BUILD_ID}/${TYPE_ID}/${CASE_ID}/${ATTEMPT_ID}/job-${SLURM_JOB_ID}"' \
        "$script"
    then
        fail "canonical output hierarchy missing: $relative"
    fi

    if grep -Fq \
        'python3 "${REPO}/scripts/collect_g4x_sweep.py"' \
        "$script"
    then
        fail "direct collector invocation remains: $relative"
    fi

    if grep -Fq \
        '/g4x-sweeps/' \
        "$script"
    then
        fail "old active result hierarchy remains: $relative"
    fi
done

helper_finalizer_count="$(
    grep -c '^finalize_g4x_sweep()' "$HELPER" || true
)"

if [[ "$helper_finalizer_count" -ne 1 ]]; then
    fail "helper finalizer count=$helper_finalizer_count"
fi

if ! grep -Fq \
    'collector-exit-code.txt' \
    "$HELPER"
then
    fail "helper does not record collector exit code"
fi

if ! grep -Fq \
    'execution-summary.txt' \
    "$HELPER"
then
    fail "helper does not record execution summary"
fi

if ! grep -Fq \
    'SWEEP_EXECUTION_STATUS=PASS' \
    "$HELPER"
then
    fail "helper does not report execution PASS"
fi

OLD_NAMES='type_a_g4x_(nk_coarse|gpu_scaling|pool_topology)\.sbatch|type_b_g4x_gpu_scaling\.sbatch'

if grep -RInE \
    "$OLD_NAMES" \
    "$ROOT" \
    --exclude='validate_sweep_scripts.sh'
then
    fail "stale old sweep filenames remain"
fi

for required_doc in \
    "$ROOT/INDEX.md" \
    "$ROOT/g4x/type-a/A1-au111-manyk/README.md" \
    "$ROOT/g4x/type-a/A1-au111-manyk/e001-npool-screen/README.md" \
    "$ROOT/g4x/type-a/A1-au111-manyk/e002-resource-shape/README.md" \
    "$ROOT/g4x/type-a/A1-au111-manyk/e003-pool-placement/README.md" \
    "$ROOT/g4x/type-b/B1-si1000-gamma/README.md" \
    "$ROOT/g4x/type-b/B1-si1000-gamma/e001-gpu-scaling/README.md"
do
    if [[ ! -s "$required_doc" ]]; then
        fail "missing or empty documentation: $required_doc"
    fi
done

if (( failed != 0 )); then
    echo "SWEEP_VALIDATION=FAIL" >&2
    exit 1
fi

printf 'SWEEP_VALIDATION=PASS scripts=%d\n' "${#SCRIPTS[@]}"
