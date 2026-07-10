#!/usr/bin/env bash
# Canonical Nano4 H200 NVHPC 25.9 profile for controlled no-QE probes.
# This profile intentionally delegates to the existing repository-owned
# environment bootstrap so the route identity remains centralized.

set -euo pipefail

profile_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${profile_dir}/.." && pwd)"

# shellcheck source=../scripts/env/nvhpc259.sh
. "${repo_root}/scripts/env/nvhpc259.sh"

export HIPAC_NANO4_PROFILE="nano4_h200_nvhpc259"
