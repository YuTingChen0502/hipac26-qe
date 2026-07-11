#!/usr/bin/env python3
"""Minimal QE automation controller for hipac26-qe.

Subcommands:
  render     Create run directories and non-executable job scripts.
  validate   Fail-closed manifest/render validation.
  dry-run    Validate and render scripts in memory without scheduler contact.
  submit     Submit only an approved manifest through this wrapper.
  parse      Parse QE/Slurm outputs after jobs finish.
  summarize  Build a compact comparison summary.

This file is intentionally self-contained to keep the clean repo small.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pwd
import re
import shlex
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "config" / "nano4.json"
DEFAULT_CASE_REGISTRY = REPO_ROOT / "config" / "case_registry.json"
MANIFEST_V2 = "hipac26_qe_manifest_v2"
SUBMIT_COMMAND = "sbatch"
PERMIT_SCHEMA = "hipac26_qe_submit_permit_v1"
LEDGER_SCHEMA = "hipac26_qe_submit_ledger_v1"


class RunCtlError(RuntimeError):
    pass


def expand_path(value: str) -> Path:
    return Path(os.path.expandvars(value)).expanduser()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise RunCtlError(f"JSON root must be object: {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def approved_local_root() -> Path:
    user = os.environ.get("USER") or pwd.getpwuid(os.getuid()).pw_name
    return Path("/work") / user / "hipac26-qe-local"


def require_controller_local_path(path: Path, label: str) -> Path:
    root = approved_local_root().resolve()
    path = path.expanduser().resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError:
        fail(f"{label} must be under controller local root: {root}")
    repo_root = REPO_ROOT.resolve()
    try:
        path.relative_to(repo_root)
    except ValueError:
        pass
    else:
        fail(f"{label} must not be inside the Git repository")
    return path


def validate_controller_directory(path: Path, label: str, *, create: bool = False) -> None:
    if path.exists() and path.is_symlink():
        fail(f"{label} must not be a symlink: {path}")
    if create:
        path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        fail(f"{label} must be a directory: {path}")
    if path.is_symlink():
        fail(f"{label} must not be a symlink: {path}")
    st = path.stat()
    if st.st_uid != os.getuid():
        fail(f"{label} must be owned by current user: {path}")
    mode = stat.S_IMODE(st.st_mode)
    if mode & 0o002:
        fail(f"{label} must not be world-writable: {path}: {oct(mode)}")


def canonical_json_bytes(data: dict[str, Any]) -> bytes:
    return (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def manifest_sha256(path: Path) -> str:
    return sha256_file(path)


def fail(msg: str) -> None:
    raise RunCtlError(msg)


def production_submit_command() -> str:
    """Return the only production scheduler submission executable."""
    return SUBMIT_COMMAND


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = read_json(path)
    if config.get("platform") != "nano4":
        fail("config platform must be nano4")
    return config


def load_case_registry(
    path: Path = DEFAULT_CASE_REGISTRY,
) -> dict[str, Any]:
    registry = read_json(path)
    if registry.get("schema_version") != "hipac26_qe_case_registry_v1":
        fail("unsupported case registry schema_version")
    return registry


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = read_json(path)
    validate_manifest(
        manifest,
        submit_mode=False,
        strict_files=False,
    )
    return manifest


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{label} must be an object")
    return value


def require_exact_keys(
    value: dict[str, Any],
    *,
    required: set[str],
    allowed: set[str],
    label: str,
) -> None:
    keys = set(value)
    missing = sorted(required - keys)
    extra = sorted(keys - allowed)

    if missing:
        fail(f"{label} missing required keys: {', '.join(missing)}")
    if extra:
        fail(f"{label} has unsupported keys: {', '.join(extra)}")


def require_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        fail(f"{label} must be an integer")
    return value


def require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        fail(f"{label} must be a boolean")
    return value


def require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        fail(f"{label} must be a non-empty string")
    if "\n" in value or "\r" in value:
        fail(f"{label} must not contain newlines")
    return value


def require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"[a-fA-F0-9]{64}",
        value,
    ):
        fail(f"invalid sha256 field: {label}")
    return value.lower()


def normalized_path_text(value: str) -> str:
    return os.path.normpath(str(expand_path(value)))


def require_absolute_path(value: Any, label: str) -> str:
    text = require_string(value, label)
    if any(component in {".", ".."} for component in text.split("/")):
        fail(f"{label} must not contain path alias components '.' or '..'")
    if "//" in text:
        fail(f"{label} must not contain repeated path separators")
    expanded = expand_path(text)

    if not expanded.is_absolute():
        fail(f"{label} must be an absolute path")

    return os.path.normpath(str(expanded))


def reject_existing_symlink_components(path: Path, label: str) -> None:
    current = Path(path.anchor)
    for component in path.parts[1:-1]:
        current = current / component
        if current.exists() and current.is_symlink():
            fail(f"{label} parent component is a symlink: {current}")


def path_is_strict_descendant(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return child != parent


def validate_v2_run_root_and_dirs(
    manifest: dict[str, Any],
    *,
    config: dict[str, Any],
) -> Path:
    run_root_text = manifest.get("run_root")
    if run_root_text is None:
        fail("manifest v2 missing required keys: run_root")

    run_root = Path(require_absolute_path(run_root_text, "run_root"))
    approved_root = Path(
        require_absolute_path(
            require_object(config.get("paths"), "config.paths").get("run_root"),
            "config.paths.run_root",
        )
    )
    repo_root = Path(
        require_absolute_path(
            require_object(config.get("paths"), "config.paths").get("repo_root"),
            "config.paths.repo_root",
        )
    )

    reject_existing_symlink_components(run_root, "run_root")
    reject_existing_symlink_components(approved_root, "config.paths.run_root")
    reject_existing_symlink_components(repo_root, "config.paths.repo_root")

    if run_root != approved_root:
        fail("manifest v2 run_root must match config.paths.run_root")
    if run_root == repo_root or path_is_strict_descendant(run_root, repo_root):
        fail("manifest v2 run_root must not be inside the Git repository")

    seen_run_dirs: set[str] = set()
    for position, raw_job in enumerate(manifest.get("jobs", [])):
        job = require_object(raw_job, f"jobs[{position}]")
        run_dir = Path(require_absolute_path(job.get("run_dir"), "run_dir"))
        reject_existing_symlink_components(run_dir, "run_dir")

        if not path_is_strict_descendant(run_dir, run_root):
            fail("manifest v2 job.run_dir must be a strict descendant of run_root")
        if run_dir == repo_root or path_is_strict_descendant(run_dir, repo_root):
            fail("manifest v2 job.run_dir must not be inside the Git repository")

        normalized = str(run_dir)
        if normalized in seen_run_dirs:
            fail(f"duplicate run_dir: {job.get('run_dir')}")
        seen_run_dirs.add(normalized)

    return run_root


def parse_walltime_seconds(value: Any) -> int:
    text = require_string(value, "slurm.time")
    match = re.fullmatch(
        r"(?:(\d+)-)?(\d{2}):(\d{2}):(\d{2})",
        text,
    )
    if not match:
        fail(
            "slurm.time must use HH:MM:SS or D-HH:MM:SS"
        )

    days_text, hours_text, minutes_text, seconds_text = match.groups()
    days = int(days_text or 0)
    hours = int(hours_text)
    minutes = int(minutes_text)
    seconds = int(seconds_text)

    if days_text is not None and hours >= 24:
        fail("day-qualified slurm.time requires hours < 24")
    if minutes >= 60 or seconds >= 60:
        fail("slurm.time minutes and seconds must be < 60")

    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def build_case_index(
    registry: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if registry.get("schema_version") != "hipac26_qe_case_registry_v1":
        fail("unsupported case registry schema_version")
    if registry.get("registry_status") != "preflight_role_freeze":
        fail("case registry status must be preflight_role_freeze")

    guards = require_object(
        registry.get("claim_guards"),
        "case registry claim_guards",
    )
    for key in (
        "benchmark_valid",
        "performance_claim_allowed",
        "optimization_claim_allowed",
    ):
        if guards.get(key) is not False:
            fail(f"case registry {key} must be false")

    policy = require_object(
        registry.get("qe_submit_eligibility_policy"),
        "case registry qe_submit_eligibility_policy",
    )
    if policy.get("required_lifecycle") != "verified":
        fail("case registry submit lifecycle must be verified")

    for key in (
        "require_case_identity_match",
        "require_input_path_match",
        "require_input_sha256_match",
        "require_pseudo_identity_match",
        "require_pseudo_sha256_match",
        "require_approved_runtime_role",
        "missing_identity_or_hash_fails_closed",
    ):
        if policy.get(key) is not True:
            fail(f"case registry policy {key} must be true")

    cases = registry.get("cases")
    if not isinstance(cases, list) or not cases:
        fail("case registry cases must be a non-empty list")

    allowed_lifecycle = {
        "verified",
        "needs_nano4_verification",
        "planned",
        "blocked",
    }
    index: dict[str, dict[str, Any]] = {}

    for position, raw_case in enumerate(cases):
        case = require_object(
            raw_case,
            f"case registry cases[{position}]",
        )
        case_id = require_string(
            case.get("case_id"),
            f"case registry cases[{position}].case_id",
        )
        if case_id in index:
            fail(f"duplicate case_id in registry: {case_id}")

        lifecycle = case.get("lifecycle")
        if lifecycle not in allowed_lifecycle:
            fail(f"invalid case lifecycle for {case_id}: {lifecycle}")

        eligible = require_bool(
            case.get("qe_submit_eligible"),
            f"case {case_id}.qe_submit_eligible",
        )
        if lifecycle == "verified" and eligible is not True:
            fail(f"verified case must be submit eligible: {case_id}")
        if lifecycle != "verified" and eligible is not False:
            fail(f"unverified case must not be submit eligible: {case_id}")

        roles = case.get("approved_runtime_roles")
        if not isinstance(roles, list) or not all(
            isinstance(role, str) and role for role in roles
        ):
            fail(f"invalid approved_runtime_roles for case: {case_id}")
        if len(set(roles)) != len(roles):
            fail(f"duplicate approved runtime role for case: {case_id}")

        input_identity = require_object(
            case.get("input"),
            f"case {case_id}.input",
        )
        pseudo_identity = require_object(
            case.get("pseudos"),
            f"case {case_id}.pseudos",
        )

        input_path = input_identity.get("path")
        input_hash = input_identity.get("sha256")
        pseudo_files = pseudo_identity.get("files")
        pseudo_hashes = pseudo_identity.get("sha256")

        if input_path is not None:
            require_absolute_path(
                input_path,
                f"case {case_id}.input.path",
            )
        if input_hash is not None:
            require_sha256(input_hash, f"case {case_id}.input.sha256")

        if not isinstance(pseudo_files, list) or not all(
            isinstance(item, str) and item for item in pseudo_files
        ):
            fail(f"invalid pseudo files for case: {case_id}")
        if len(set(pseudo_files)) != len(pseudo_files):
            fail(f"duplicate pseudo identity for case: {case_id}")

        for pseudo_file in pseudo_files:
            require_absolute_path(
                pseudo_file,
                f"case {case_id}.pseudo file",
            )

        if not isinstance(pseudo_hashes, dict):
            fail(f"invalid pseudo hash mapping for case: {case_id}")
        for pseudo_path, pseudo_hash in pseudo_hashes.items():
            require_absolute_path(
                pseudo_path,
                f"case {case_id}.pseudo hash key",
            )
            require_sha256(
                pseudo_hash,
                f"case {case_id}.pseudo sha256",
            )

        if lifecycle == "verified":
            if not input_path or input_hash is None:
                fail(f"verified case missing input identity: {case_id}")
            if input_identity.get("identity_status") != "verified":
                fail(f"verified case input status mismatch: {case_id}")
            if not pseudo_files or not pseudo_hashes:
                fail(f"verified case missing pseudo identity: {case_id}")
            if pseudo_identity.get("identity_status") != "verified":
                fail(f"verified case pseudo status mismatch: {case_id}")
            if not roles:
                fail(f"verified case has no approved runtime role: {case_id}")

        if "allowed_npools" in case:
            allowed_npools = case["allowed_npools"]
            if (
                not isinstance(allowed_npools, list)
                or not allowed_npools
                or any(
                    isinstance(value, bool) or not isinstance(value, int) or value < 1
                    for value in allowed_npools
                )
                or len(set(allowed_npools)) != len(allowed_npools)
            ):
                fail(f"invalid allowed_npools for case: {case_id}")

        if "benchmark_valid" in case and case["benchmark_valid"] is not False:
            fail(f"case benchmark_valid must be false: {case_id}")
        if (
            "performance_claim_allowed" in case
            and case["performance_claim_allowed"] is not False
        ):
            fail(f"case performance_claim_allowed must be false: {case_id}")
        if (
            "optimization_claim_allowed" in case
            and case["optimization_claim_allowed"] is not False
        ):
            fail(f"case optimization_claim_allowed must be false: {case_id}")

        if "runtime_binaries" in case:
            binaries = case["runtime_binaries"]
            if not isinstance(binaries, dict) or not binaries:
                fail(f"invalid runtime_binaries for case: {case_id}")
            for binary_label, binary_identity in binaries.items():
                require_string(binary_label, f"case {case_id}.runtime_binaries key")
                identity = require_object(
                    binary_identity,
                    f"case {case_id}.runtime_binaries.{binary_label}",
                )
                require_absolute_path(
                    identity.get("path"),
                    f"case {case_id}.runtime_binaries.{binary_label}.path",
                )
                require_sha256(
                    identity.get("sha256"),
                    f"case {case_id}.runtime_binaries.{binary_label}.sha256",
                )

        if lifecycle == "blocked":
            reason = case.get("blocked_reason")
            if not isinstance(reason, str) or not reason:
                fail(f"blocked case missing blocked_reason: {case_id}")

        index[case_id] = case

    return index


def manifest_uses_v2_only_fields(
    manifest: dict[str, Any],
) -> bool:
    if any(
        key in manifest
        for key in (
            "performance_claim_allowed",
            "optimization_claim_allowed",
        )
    ):
        return True

    jobs = manifest.get("jobs")
    if not isinstance(jobs, list):
        return False

    for raw_job in jobs:
        if not isinstance(raw_job, dict):
            continue

        if any(
            key in raw_job
            for key in (
                "job_kind",
                "case_id",
                "runtime_role",
                "probe_profile",
            )
        ):
            return True

        slurm = raw_job.get("slurm")
        if isinstance(slurm, dict) and any(
            key in slurm
            for key in (
                "ntasks_per_node",
                "gpus_per_node",
                "total_gpus",
            )
        ):
            return True

    return False


def validate_manifest(
    manifest: dict[str, Any],
    *,
    submit_mode: bool,
    strict_files: bool,
    config: dict[str, Any] | None = None,
    case_registry: dict[str, Any] | None = None,
) -> None:
    schema_version = manifest.get("schema_version")

    if schema_version == MANIFEST_V2:
        validate_manifest_v2(
            manifest,
            submit_mode=submit_mode,
            strict_files=strict_files,
            config=config or load_config(),
            case_registry=case_registry or load_case_registry(),
        )
        return

    if manifest_uses_v2_only_fields(manifest):
        fail(
            "manifest v2-only fields require "
            "schema_version=hipac26_qe_manifest_v2"
        )

    validate_manifest_v1(
        manifest,
        submit_mode=submit_mode,
        strict_files=strict_files,
    )


def validate_manifest_v1(
    manifest: dict[str, Any],
    *,
    submit_mode: bool,
    strict_files: bool,
) -> None:
    required = [
        "schema_version",
        "trial_id",
        "autonomy_level",
        "benchmark_valid",
        "approved_by_human",
        "allowed_submit",
        "max_retries",
        "jobs",
    ]
    for key in required:
        if key not in manifest:
            fail(f"manifest missing required key: {key}")

    if manifest["benchmark_valid"] is not False:
        fail("benchmark_valid must be false")
    if manifest["max_retries"] != 0:
        fail("max_retries must be 0")
    if manifest["autonomy_level"] not in {"L1", "L2", "L3", "L4"}:
        fail("autonomy_level must be L1/L2/L3/L4")
    if manifest["autonomy_level"] == "L4" and len(manifest["jobs"]) > 8:
        fail("L4 manifest cannot exceed 8 jobs in this clean controller")

    if submit_mode:
        if manifest["approved_by_human"] is not True:
            fail("submit denied: approved_by_human is not true")
        if manifest["allowed_submit"] is not True:
            fail("submit denied: allowed_submit is not true")
    else:
        if (
            manifest["allowed_submit"] is True
            and manifest["approved_by_human"] is not True
        ):
            fail("allowed_submit=true requires approved_by_human=true")

    jobs = manifest.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        fail("jobs must be a non-empty list")

    seen_config_ids: set[str] = set()
    seen_run_dirs: set[str] = set()

    for job in jobs:
        validate_job_v1(job, strict_files=strict_files)

        config_id = job["config_id"]
        if config_id in seen_config_ids:
            fail(f"duplicate config_id: {config_id}")
        seen_config_ids.add(config_id)

        run_identity = normalized_path_text(job["run_dir"])
        if run_identity in seen_run_dirs:
            fail(f"duplicate run_dir: {job['run_dir']}")
        seen_run_dirs.add(run_identity)


def validate_job_v1(
    job: dict[str, Any],
    *,
    strict_files: bool,
) -> None:
    for key in [
        "config_id",
        "run_dir",
        "binary_path",
        "binary_sha256",
        "input_path",
        "input_sha256",
        "pseudo_paths",
        "pseudo_sha256",
        "slurm",
        "runtime",
    ]:
        if key not in job:
            fail(f"job missing required key: {key}")

    if not re.match(
        r"^cfg[0-9]{3}[_A-Za-z0-9-]*$",
        job["config_id"],
    ):
        fail(f"invalid config_id: {job['config_id']}")

    for hash_key in ["binary_sha256", "input_sha256"]:
        if not re.match(r"^[a-fA-F0-9]{64}$", job[hash_key]):
            fail(f"invalid sha256 field: {hash_key}")

    if not isinstance(job["pseudo_paths"], list) or not job["pseudo_paths"]:
        fail("pseudo_paths must be non-empty list")
    if not isinstance(job["pseudo_sha256"], dict):
        fail("pseudo_sha256 must be object")

    slurm = job["slurm"]
    for key in [
        "account",
        "partition",
        "nodes",
        "ntasks",
        "cpus_per_task",
        "gres",
        "time",
    ]:
        if key not in slurm:
            fail(f"slurm missing key: {key}")

    if slurm["nodes"] != 1:
        fail("only nodes=1 is allowed")
    if not (1 <= int(slurm["ntasks"]) <= 8):
        fail("ntasks outside allowed range")
    if not (1 <= int(slurm["cpus_per_task"]) <= 16):
        fail("cpus_per_task outside allowed range")

    runtime = job["runtime"]
    for key in ["omp_num_threads", "npools"]:
        if key not in runtime:
            fail(f"runtime missing key: {key}")
    if int(runtime["omp_num_threads"]) != int(
        slurm["cpus_per_task"]
    ):
        fail("omp_num_threads must equal cpus_per_task")

    if strict_files:
        check_hash(
            expand_path(job["binary_path"]),
            job["binary_sha256"],
            "binary",
        )
        check_hash(
            expand_path(job["input_path"]),
            job["input_sha256"],
            "input",
        )
        for pseudo_path_value in job["pseudo_paths"]:
            pseudo_path = expand_path(pseudo_path_value)
            expected = (
                job["pseudo_sha256"].get(str(pseudo_path))
                or job["pseudo_sha256"].get(pseudo_path_value)
            )
            if not expected:
                fail(f"missing pseudo hash for {pseudo_path_value}")
            check_hash(pseudo_path, expected, "pseudo")


def validate_manifest_v2(
    manifest: dict[str, Any],
    *,
    submit_mode: bool,
    strict_files: bool,
    config: dict[str, Any],
    case_registry: dict[str, Any],
) -> None:
    required = {
        "schema_version",
        "trial_id",
        "autonomy_level",
        "benchmark_valid",
        "performance_claim_allowed",
        "optimization_claim_allowed",
        "approved_by_human",
        "allowed_submit",
        "max_retries",
        "run_root",
        "jobs",
    }
    allowed = set(required)

    require_exact_keys(
        manifest,
        required=required,
        allowed=allowed,
        label="manifest v2",
    )

    if manifest["schema_version"] != MANIFEST_V2:
        fail("unsupported manifest v2 schema_version")
    if not re.fullmatch(
        r"[A-Z0-9]+(?:-[A-Z0-9]+)*-(?:[TR][0-9]{3}|NP[0-9]+|PROFILE-NP[0-9]+)",
        require_string(manifest["trial_id"], "trial_id"),
    ):
        fail("invalid trial_id")

    if manifest["autonomy_level"] not in {"L1", "L2", "L3", "L4"}:
        fail("autonomy_level must be L1/L2/L3/L4")

    if manifest["benchmark_valid"] is not False:
        fail("benchmark_valid must be false")
    if manifest["performance_claim_allowed"] is not False:
        fail("performance_claim_allowed must be false")
    if manifest["optimization_claim_allowed"] is not False:
        fail("optimization_claim_allowed must be false")

    require_bool(
        manifest["approved_by_human"],
        "approved_by_human",
    )
    require_bool(
        manifest["allowed_submit"],
        "allowed_submit",
    )

    if require_int(manifest["max_retries"], "max_retries") != 0:
        fail("max_retries must be 0")

    if submit_mode:
        if manifest["approved_by_human"] is not True:
            fail("submit denied: approved_by_human is not true")
        if manifest["allowed_submit"] is not True:
            fail("submit denied: allowed_submit is not true")
    elif (
        manifest["allowed_submit"] is True
        and manifest["approved_by_human"] is not True
    ):
        fail("allowed_submit=true requires approved_by_human=true")

    validate_v2_run_root_and_dirs(manifest, config=config)

    jobs = manifest["jobs"]
    if not isinstance(jobs, list) or not jobs:
        fail("jobs must be a non-empty list")
    if len(jobs) > 8:
        fail("manifest v2 cannot exceed 8 jobs")

    case_index = build_case_index(case_registry)

    seen_config_ids: set[str] = set()
    seen_run_dirs: set[str] = set()
    job_kinds: set[str] = set()

    for position, raw_job in enumerate(jobs):
        job = require_object(raw_job, f"jobs[{position}]")
        kind = validate_job_v2(
            job,
            strict_files=strict_files,
            config=config,
            case_index=case_index,
        )
        job_kinds.add(kind)

        config_id = job["config_id"]
        if config_id in seen_config_ids:
            fail(f"duplicate config_id: {config_id}")
        seen_config_ids.add(config_id)

        run_identity = str(Path(require_absolute_path(job["run_dir"], "run_dir")))
        if run_identity in seen_run_dirs:
            fail(f"duplicate run_dir: {job['run_dir']}")
        seen_run_dirs.add(run_identity)

    if len(job_kinds) != 1:
        fail("manifest v2 must not mix QE and environment_probe jobs")

    if submit_mode:
        validate_v2_submission_guards(
            jobs=jobs,
            config=config,
        )
        for job in jobs:
            if job["job_kind"] == "qe":
                validate_case_submit_eligibility(
                    job,
                    case_index[job["case_id"]],
                )


def validate_job_v2(
    job: dict[str, Any],
    *,
    strict_files: bool,
    config: dict[str, Any],
    case_index: dict[str, dict[str, Any]],
) -> str:
    common_required = {
        "config_id",
        "job_kind",
        "run_dir",
        "slurm",
        "runtime",
    }

    kind = require_string(job.get("job_kind"), "job_kind")

    if kind == "qe":
        required = common_required | {
            "case_id",
            "runtime_role",
            "binary_path",
            "binary_sha256",
            "input_path",
            "input_sha256",
            "pseudo_paths",
            "pseudo_sha256",
        }
        allowed = required | {"profiler"}
    elif kind == "environment_probe":
        required = common_required | {"probe_profile"}
        allowed = required
    else:
        fail(f"unsupported job_kind: {kind}")

    require_exact_keys(
        job,
        required=required,
        allowed=allowed,
        label=f"{kind} job",
    )

    config_id = require_string(job["config_id"], "config_id")
    if not re.fullmatch(
        r"cfg[0-9]{3}[_A-Za-z0-9-]*",
        config_id,
    ):
        fail(f"invalid config_id: {config_id}")

    require_absolute_path(job["run_dir"], "run_dir")

    shape = validate_resource_shape(
        require_object(job["slurm"], "slurm"),
        config=config,
    )
    validate_v2_runtime(
        require_object(job["runtime"], "runtime"),
        job_kind=kind,
        shape=shape,
    )

    if kind == "environment_probe":
        if job["probe_profile"] != "basic_environment":
            fail("unsupported environment probe profile")
        return kind

    require_absolute_path(job["binary_path"], "binary_path")
    require_sha256(job["binary_sha256"], "binary_sha256")
    require_absolute_path(job["input_path"], "input_path")
    require_sha256(job["input_sha256"], "input_sha256")

    pseudo_paths = job["pseudo_paths"]
    pseudo_hashes = job["pseudo_sha256"]

    if not isinstance(pseudo_paths, list) or not pseudo_paths:
        fail("pseudo_paths must be a non-empty list")
    if not all(
        isinstance(item, str) and item for item in pseudo_paths
    ):
        fail("pseudo_paths must contain non-empty strings")
    if len(set(pseudo_paths)) != len(pseudo_paths):
        fail("pseudo_paths contains duplicate identities")

    for pseudo_path in pseudo_paths:
        require_absolute_path(pseudo_path, "pseudo_paths item")

    if not isinstance(pseudo_hashes, dict) or not pseudo_hashes:
        fail("pseudo_sha256 must be a non-empty object")

    normalized_paths = {
        normalized_path_text(item) for item in pseudo_paths
    }
    normalized_hashes: dict[str, str] = {}

    for pseudo_path, pseudo_hash in pseudo_hashes.items():
        require_absolute_path(pseudo_path, "pseudo_sha256 key")
        normalized_key = normalized_path_text(pseudo_path)
        if normalized_key in normalized_hashes:
            fail("pseudo_sha256 contains duplicate normalized paths")
        normalized_hashes[normalized_key] = require_sha256(
            pseudo_hash,
            f"pseudo_sha256[{pseudo_path}]",
        )

    if set(normalized_hashes) != normalized_paths:
        fail("pseudo_paths and pseudo_sha256 identities must match")

    validate_case_preflight(
        job,
        case_index=case_index,
    )

    if "profiler" in job:
        validate_profiler(job["profiler"])

    if strict_files:
        check_hash(
            expand_path(job["binary_path"]),
            job["binary_sha256"],
            "binary",
        )
        check_hash(
            expand_path(job["input_path"]),
            job["input_sha256"],
            "input",
        )
        for pseudo_path_value in pseudo_paths:
            normalized = normalized_path_text(pseudo_path_value)
            check_hash(
                expand_path(pseudo_path_value),
                normalized_hashes[normalized],
                "pseudo",
            )

    return kind


def validate_profiler(profiler: Any) -> None:
    value = require_object(profiler, "profiler")
    required = {"enabled", "tool", "output_prefix", "required_download", "optional_download", "remote_only"}
    require_exact_keys(
        value,
        required=required,
        allowed=required,
        label="profiler",
    )
    if value["enabled"] is not True:
        fail("profiler.enabled must be true when profiler is present")
    if value["tool"] != "nsys":
        fail("unsupported profiler tool")
    prefix = require_string(value["output_prefix"], "profiler.output_prefix")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", prefix):
        fail("profiler.output_prefix contains unsupported characters")
    for key in ("required_download", "optional_download", "remote_only"):
        require_bool(value[key], f"profiler.{key}")


def validate_resource_shape(
    slurm: dict[str, Any],
    *,
    config: dict[str, Any],
) -> dict[str, int]:
    required = {
        "account",
        "partition",
        "nodes",
        "ntasks",
        "ntasks_per_node",
        "cpus_per_task",
        "gpus_per_node",
        "total_gpus",
        "gres",
        "time",
    }

    require_exact_keys(
        slurm,
        required=required,
        allowed=required,
        label="slurm",
    )

    account = require_string(slurm["account"], "slurm.account")
    partition = require_string(
        slurm["partition"],
        "slurm.partition",
    )

    if not re.fullmatch(r"[A-Z0-9]+", account):
        fail("slurm.account contains unsupported characters")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", partition):
        fail("slurm.partition contains unsupported characters")

    nodes = require_int(slurm["nodes"], "slurm.nodes")
    ntasks = require_int(slurm["ntasks"], "slurm.ntasks")
    ntasks_per_node = require_int(
        slurm["ntasks_per_node"],
        "slurm.ntasks_per_node",
    )
    cpus_per_task = require_int(
        slurm["cpus_per_task"],
        "slurm.cpus_per_task",
    )
    gpus_per_node = require_int(
        slurm["gpus_per_node"],
        "slurm.gpus_per_node",
    )
    total_gpus = require_int(
        slurm["total_gpus"],
        "slurm.total_gpus",
    )

    hardware = require_object(
        config.get("hardware"),
        "config.hardware",
    )
    accounts = require_object(
        config.get("accounts"),
        "config.accounts",
    )
    partitions = require_object(
        config.get("partitions"),
        "config.partitions",
    )

    authorized_accounts = accounts.get("authorized")
    forbidden_accounts = accounts.get("forbidden")

    if not isinstance(authorized_accounts, list):
        fail("config authorized accounts must be a list")
    if not isinstance(forbidden_accounts, list):
        fail("config forbidden accounts must be a list")

    if account in forbidden_accounts:
        fail(f"Nano4 account is forbidden: {account}")
    if account not in authorized_accounts:
        fail(f"Nano4 account is not authorized: {account}")

    partition_policy = partitions.get(partition)
    if not isinstance(partition_policy, dict):
        fail(f"unknown Nano4 partition: {partition}")

    partition_accounts = partition_policy.get("authorized_accounts")
    if (
        not isinstance(partition_accounts, list)
        or account not in partition_accounts
    ):
        fail(
            f"account/partition mismatch: {account} / {partition}"
        )

    max_nodes = require_int(
        hardware.get("maximum_supported_nodes_for_preflight"),
        "config.hardware.maximum_supported_nodes_for_preflight",
    )
    gpus_available = require_int(
        hardware.get("gpus_per_node"),
        "config.hardware.gpus_per_node",
    )
    allocatable_cpu = require_int(
        hardware.get("allocatable_cpu_tres_per_node"),
        "config.hardware.allocatable_cpu_tres_per_node",
    )
    max_cpu_per_gpu = require_int(
        hardware.get("max_cpu_cores_per_requested_gpu"),
        "config.hardware.max_cpu_cores_per_requested_gpu",
    )

    if not (1 <= nodes <= max_nodes):
        fail("nodes outside supported preflight range")
    if ntasks_per_node < 1:
        fail("ntasks_per_node must be positive")
    if not (1 <= gpus_per_node <= gpus_available):
        fail("gpus_per_node outside Nano4 node capacity")
    if cpus_per_task < 1:
        fail("cpus_per_task must be positive")

    if ntasks != nodes * ntasks_per_node:
        fail("ntasks must equal nodes * ntasks_per_node")
    if total_gpus != nodes * gpus_per_node:
        fail("total_gpus must equal nodes * gpus_per_node")

    # Current controlled preflight contract is one MPI rank per GPU.
    if ntasks_per_node != gpus_per_node:
        fail(
            "v2 preflight requires ntasks_per_node "
            "to equal gpus_per_node"
        )
    if ntasks != total_gpus:
        fail("v2 preflight requires one MPI task per requested GPU")

    expected_gres = f"gpu:{gpus_per_node}"
    if slurm["gres"] != expected_gres:
        fail(
            f"gres must exactly match per-node GPU request: "
            f"{expected_gres}"
        )

    cpu_per_node = ntasks_per_node * cpus_per_task
    if cpu_per_node > allocatable_cpu:
        fail("CPU request exceeds allocatable CPU TRES per node")
    if cpu_per_node > gpus_per_node * max_cpu_per_gpu:
        fail("CPU request exceeds Nano4 CPU-per-GPU ceiling")

    minimum_total_gpus = require_int(
        partition_policy.get("minimum_total_gpus"),
        f"partition {partition}.minimum_total_gpus",
    )
    if total_gpus < minimum_total_gpus:
        fail(
            f"partition {partition} requires at least "
            f"{minimum_total_gpus} GPUs"
        )

    maximum_by_account = require_object(
        partition_policy.get("maximum_total_gpus_by_account"),
        f"partition {partition}.maximum_total_gpus_by_account",
    )
    maximum_total_gpus = maximum_by_account.get(account)
    if isinstance(maximum_total_gpus, bool) or not isinstance(
        maximum_total_gpus,
        int,
    ):
        fail(
            f"partition {partition} has no valid GPU limit "
            f"for account {account}"
        )
    if total_gpus > maximum_total_gpus:
        fail(
            f"GPU request exceeds {partition}/{account} limit "
            f"of {maximum_total_gpus}"
        )

    walltime_seconds = parse_walltime_seconds(slurm["time"])
    maximum_walltime = require_int(
        partition_policy.get("maximum_walltime_seconds"),
        f"partition {partition}.maximum_walltime_seconds",
    )
    if walltime_seconds > maximum_walltime:
        fail(
            f"walltime exceeds partition {partition} limit"
        )

    return {
        "nodes": nodes,
        "ntasks": ntasks,
        "ntasks_per_node": ntasks_per_node,
        "cpus_per_task": cpus_per_task,
        "gpus_per_node": gpus_per_node,
        "total_gpus": total_gpus,
        "walltime_seconds": walltime_seconds,
    }


def validate_v2_runtime(
    runtime: dict[str, Any],
    *,
    job_kind: str,
    shape: dict[str, int],
) -> None:
    if job_kind == "environment_probe":
        required = {"omp_num_threads"}
        require_exact_keys(
            runtime,
            required=required,
            allowed=required,
            label="environment_probe runtime",
        )
    else:
        required = {"omp_num_threads", "npools"}
        allowed = required | {
            "extra_args",
            "launcher",
            "mpirun_np",
        }
        require_exact_keys(
            runtime,
            required=required,
            allowed=allowed,
            label="QE runtime",
        )

    omp_threads = require_int(
        runtime["omp_num_threads"],
        "runtime.omp_num_threads",
    )
    if omp_threads != shape["cpus_per_task"]:
        fail("omp_num_threads must equal cpus_per_task")

    if job_kind == "environment_probe":
        return

    npools = require_int(runtime["npools"], "runtime.npools")
    if not (1 <= npools <= shape["ntasks"]):
        fail("npools must be between 1 and ntasks")
    if shape["ntasks"] % npools != 0:
        fail("ntasks must be divisible by npools")

    launcher = runtime.get("launcher", "mpirun --bind-to none")
    if launcher != "mpirun --bind-to none":
        fail(
            "manifest v2 launcher must be "
            "'mpirun --bind-to none'"
        )

    mpirun_np = runtime.get("mpirun_np", shape["ntasks"])
    if require_int(mpirun_np, "runtime.mpirun_np") != shape["ntasks"]:
        fail("mpirun_np must equal ntasks")

    extra_args = runtime.get("extra_args", [])
    if not isinstance(extra_args, list):
        fail("runtime.extra_args must be an array")
    for argument in extra_args:
        if not isinstance(argument, str) or not re.fullmatch(
            r"[A-Za-z0-9_./:=+,-]+",
            argument,
        ):
            fail(f"unsafe or invalid QE extra argument: {argument!r}")


def validate_case_preflight(
    job: dict[str, Any],
    *,
    case_index: dict[str, dict[str, Any]],
) -> None:
    case_id = require_string(job["case_id"], "case_id")
    runtime_role = require_string(
        job["runtime_role"],
        "runtime_role",
    )

    case = case_index.get(case_id)
    if case is None:
        fail(f"case absent from registry: {case_id}")

    if case["lifecycle"] == "blocked":
        fail(
            f"case is blocked: {case_id}: "
            f"{case.get('blocked_reason')}"
        )

    approved_roles = case["approved_runtime_roles"]
    if runtime_role not in approved_roles:
        fail(
            f"runtime role is not approved for case "
            f"{case_id}: {runtime_role}"
        )

    registry_input = case["input"]
    registered_input_path = registry_input.get("path")
    registered_input_hash = registry_input.get("sha256")

    if registered_input_path is not None:
        if normalized_path_text(job["input_path"]) != normalized_path_text(
            registered_input_path
        ):
            fail(f"input path mismatch for case: {case_id}")

    if registered_input_hash is not None:
        if job["input_sha256"].lower() != registered_input_hash.lower():
            fail(f"input sha256 mismatch for case: {case_id}")

    registry_pseudos = case["pseudos"]
    registered_files = registry_pseudos.get("files", [])
    registered_hashes = registry_pseudos.get("sha256", {})

    if registered_files:
        manifest_files = {
            normalized_path_text(value)
            for value in job["pseudo_paths"]
        }
        expected_files = {
            normalized_path_text(value)
            for value in registered_files
        }
        if manifest_files != expected_files:
            fail(f"pseudo identity mismatch for case: {case_id}")

    if registered_hashes:
        manifest_hashes = {
            normalized_path_text(key): value.lower()
            for key, value in job["pseudo_sha256"].items()
        }
        expected_hashes = {
            normalized_path_text(key): value.lower()
            for key, value in registered_hashes.items()
        }
        if manifest_hashes != expected_hashes:
            fail(f"pseudo sha256 mismatch for case: {case_id}")

    allowed_npools = case.get("allowed_npools")
    if allowed_npools is not None:
        npools = require_int(job["runtime"].get("npools"), "runtime.npools")
        if npools not in allowed_npools:
            fail(f"npools is not allowed for case {case_id}: {npools}")

    binaries = case.get("runtime_binaries")
    if binaries:
        matching = [
            identity
            for identity in binaries.values()
            if normalized_path_text(identity["path"]) == normalized_path_text(job["binary_path"])
            and identity["sha256"].lower() == job["binary_sha256"].lower()
        ]
        if not matching:
            fail(f"binary identity mismatch for case: {case_id}")


def validate_case_submit_eligibility(
    job: dict[str, Any],
    case: dict[str, Any],
) -> None:
    case_id = job["case_id"]

    if case["lifecycle"] != "verified":
        fail(
            f"QE submit denied: case lifecycle is not verified: "
            f"{case_id}"
        )
    if case["qe_submit_eligible"] is not True:
        fail(
            f"QE submit denied: case is not submit eligible: "
            f"{case_id}"
        )

    input_identity = case["input"]
    pseudo_identity = case["pseudos"]

    if input_identity.get("identity_status") != "verified":
        fail(
            f"QE submit denied: input identity is not verified: "
            f"{case_id}"
        )
    if pseudo_identity.get("identity_status") != "verified":
        fail(
            f"QE submit denied: pseudo identity is not verified: "
            f"{case_id}"
        )

    if not input_identity.get("path") or not input_identity.get("sha256"):
        fail(
            f"QE submit denied: input identity is incomplete: "
            f"{case_id}"
        )
    if not pseudo_identity.get("files") or not pseudo_identity.get(
        "sha256"
    ):
        fail(
            f"QE submit denied: pseudo identity is incomplete: "
            f"{case_id}"
        )

    # Re-run exact comparisons; verified registry data must match manifest.
    validate_case_preflight(
        job,
        case_index={case_id: case},
    )


def validate_v2_submission_guards(
    *,
    jobs: list[dict[str, Any]],
    config: dict[str, Any],
) -> None:
    policy = require_object(
        config.get("policy"),
        "config.policy",
    )

    if policy.get("submit_requires_human_approval") is not True:
        fail("config must require human approval")
    if policy.get("submit_wrapper_only") is not True:
        fail("config must require wrapper-only submission")
    if policy.get("max_retries_default") != 0:
        fail("config max_retries_default must be 0")

    for job in jobs:
        kind = job["job_kind"]

        if kind == "environment_probe":
            if policy.get("environment_probe_submit_enabled") is not True:
                fail(
                    "environment_probe submit denied: "
                    "environment_probe_submit_enabled=false"
                )
            continue

        if policy.get("two_node_qe_submit_enabled") is not True:
            fail(
                "QE submit denied: "
                "two_node_qe_submit_enabled=false"
            )

        if int(job["slurm"]["nodes"]) > 1:
            if policy.get("two_node_environment_verified") is not True:
                fail(
                    "2-node QE submit denied: "
                    "two_node_environment_verified=false"
                )


def check_hash(path: Path, expected: str, label: str) -> None:
    if not path.exists():
        fail(f"{label} path missing: {path}")
    actual = sha256_file(path)
    if actual.lower() != expected.lower():
        fail(f"{label} sha256 mismatch: {path}: {actual} != {expected}")


def expected_permit_path(manifest_path: Path) -> Path:
    return manifest_path.parent / "permit_record.json"


def manifest_resource_identity(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("schema_version") != MANIFEST_V2:
        return {}
    if len(manifest.get("jobs", [])) != 1:
        fail("one-time permit submit supports exactly one job per manifest")
    job = require_object(manifest["jobs"][0], "jobs[0]")
    pseudo_hashes = require_object(job.get("pseudo_sha256"), "pseudo_sha256")
    return {
        "trial_id": manifest["trial_id"],
        "build_sha256": job.get("binary_sha256"),
        "input_sha256": job.get("input_sha256"),
        "pseudo_sha256": dict(sorted((str(k), str(v)) for k, v in pseudo_hashes.items())),
        "resources": job.get("slurm"),
        "job_kind": job.get("job_kind"),
        "case_id": job.get("case_id"),
        "runtime_role": job.get("runtime_role"),
    }


def load_and_validate_submit_permit(
    *,
    manifest_path: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    if manifest.get("schema_version") != MANIFEST_V2:
        return {}

    permit_path = expected_permit_path(manifest_path)
    if not permit_path.is_file() or permit_path.is_symlink():
        fail(f"submit permit missing or invalid: {permit_path}")
    permit = read_json(permit_path)
    required = {
        "schema_version",
        "phase_identifier",
        "trial_id",
        "manifest_sha256",
        "build_sha256",
        "input_sha256",
        "pseudo_sha256",
        "resources",
        "maximum_attempts",
        "ledger_path",
    }
    require_exact_keys(
        permit,
        required=required,
        allowed=required,
        label="submit permit",
    )
    if permit["schema_version"] != PERMIT_SCHEMA:
        fail("unsupported submit permit schema_version")
    if permit["trial_id"] != manifest["trial_id"]:
        fail("submit permit trial_id does not match manifest")
    actual_manifest_hash = manifest_sha256(manifest_path)
    if require_sha256(permit["manifest_sha256"], "permit.manifest_sha256") != actual_manifest_hash:
        fail("submit permit manifest sha256 mismatch")
    if require_int(permit["maximum_attempts"], "permit.maximum_attempts") != 1:
        fail("submit permit maximum_attempts must be 1")

    identity = manifest_resource_identity(manifest)
    if permit["build_sha256"] != identity["build_sha256"]:
        fail("submit permit build sha256 mismatch")
    if permit["input_sha256"] != identity["input_sha256"]:
        fail("submit permit input sha256 mismatch")
    if permit["pseudo_sha256"] != identity["pseudo_sha256"]:
        fail("submit permit pseudo sha256 mismatch")
    if permit["resources"] != identity["resources"]:
        fail("submit permit resource shape mismatch")

    ledger_path = require_controller_local_path(
        Path(require_absolute_path(permit["ledger_path"], "permit.ledger_path")),
        "permit.ledger_path",
    )
    validate_controller_directory(ledger_path.parent, "permit ledger parent", create=True)
    permit["_path"] = str(permit_path)
    permit["_ledger_path"] = str(ledger_path)
    permit["_manifest_sha256"] = actual_manifest_hash
    return permit


def acquire_ledger_lock(ledger_path: Path) -> Path:
    lock_path = ledger_path.with_suffix(ledger_path.suffix + ".lock")
    deadline = time.monotonic() + 10
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            return lock_path
        except FileExistsError:
            if time.monotonic() >= deadline:
                fail(f"timeout acquiring submit ledger lock: {lock_path}")
            time.sleep(0.1)


def read_ledger(ledger_path: Path) -> dict[str, Any]:
    if not ledger_path.exists():
        return {"schema_version": LEDGER_SCHEMA, "entries": {}}
    if ledger_path.is_symlink() or not ledger_path.is_file():
        fail(f"submit ledger must be a regular file: {ledger_path}")
    ledger = read_json(ledger_path)
    if ledger.get("schema_version") != LEDGER_SCHEMA:
        fail("submit ledger schema_version mismatch or tampering detected")
    if not isinstance(ledger.get("entries"), dict):
        fail("submit ledger entries must be object")
    return ledger


def atomic_write_ledger(ledger_path: Path, ledger: dict[str, Any]) -> None:
    tmp = ledger_path.with_name(ledger_path.name + f".tmp.{os.getpid()}")
    with tmp.open("wb") as f:
        f.write(canonical_json_bytes(ledger))
    os.replace(tmp, ledger_path)


def consume_submit_permit(
    *,
    manifest_path: Path,
    manifest: dict[str, Any],
    permit: dict[str, Any],
) -> dict[str, Any]:
    if manifest.get("schema_version") != MANIFEST_V2:
        return {}
    ledger_path = Path(permit["_ledger_path"])
    lock_path = acquire_ledger_lock(ledger_path)
    try:
        ledger = read_ledger(ledger_path)
        entries = ledger["entries"]
        trial_id = permit["trial_id"]
        existing = entries.get(trial_id)
        identity = manifest_resource_identity(manifest)
        entry_identity = {
            "phase_identifier": permit["phase_identifier"],
            "trial_id": trial_id,
            "manifest_sha256": permit["_manifest_sha256"],
            "build_sha256": permit["build_sha256"],
            "input_sha256": permit["input_sha256"],
            "pseudo_sha256": permit["pseudo_sha256"],
            "exact_resources": permit["resources"],
            "maximum_attempts": 1,
            "job_kind": identity["job_kind"],
            "case_id": identity["case_id"],
            "runtime_role": identity["runtime_role"],
        }
        if existing is not None:
            comparable = {key: existing.get(key) for key in entry_identity}
            if comparable != entry_identity:
                fail("submit ledger trial identity mismatch or tampering detected")
            if existing.get("attempts_consumed") != 0:
                fail("submit permit already consumed")
        attempt = {
            "attempt_index": 1,
            "attempt_timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "manifest_path": str(manifest_path),
            "permit_path": permit["_path"],
            "wrapper_exit_status": None,
            "scheduler_contacted": False,
            "job_id": None,
            "final_state": "consumed_before_scheduler_contact",
        }
        entry = dict(entry_identity)
        entry.update({"attempts_consumed": 1, "attempts": [attempt]})
        entries[trial_id] = entry
        atomic_write_ledger(ledger_path, ledger)
        return {"ledger_path": str(ledger_path), "trial_id": trial_id, "attempt_index": 1}
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def update_consumed_attempt(
    permit_audit: dict[str, Any],
    *,
    wrapper_exit_status: int | None,
    scheduler_contacted: bool,
    job_id: str | None,
    final_state: str,
) -> None:
    if not permit_audit:
        return
    ledger_path = Path(permit_audit["ledger_path"])
    lock_path = acquire_ledger_lock(ledger_path)
    try:
        ledger = read_ledger(ledger_path)
        entry = ledger["entries"].get(permit_audit["trial_id"])
        if entry is None or not entry.get("attempts"):
            fail("submit ledger consumed attempt missing")
        attempt = entry["attempts"][-1]
        attempt.update(
            {
                "wrapper_exit_status": wrapper_exit_status,
                "scheduler_contacted": scheduler_contacted,
                "job_id": job_id,
                "final_state": final_state,
                "update_timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        )
        atomic_write_ledger(ledger_path, ledger)
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def create_attempt_directory(manifest_hash: str, trial_id: str) -> Path:
    root = require_controller_local_path(approved_local_root() / "runctl_attempts", "attempt root")
    validate_controller_directory(root, "attempt root", create=True)
    safe_trial = re.sub(r"[^A-Za-z0-9_.-]", "_", trial_id)
    attempt_name = f"{safe_trial}_{manifest_hash[:16]}_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}_{os.getpid()}"
    attempt_dir = root / attempt_name
    attempt_dir.mkdir(mode=0o700, exist_ok=False)
    validate_controller_directory(attempt_dir, "attempt directory")
    return attempt_dir


def render_slurm_directives(
    slurm: dict[str, Any],
    *,
    stdout_name: str,
    stderr_name: str,
) -> str:
    directive = "#" + "SBATCH"

    lines = [
        f"{directive} -A {slurm['account']}",
        f"{directive} -p {slurm['partition']}",
        f"{directive} -N {slurm['nodes']}",
        f"{directive} --ntasks={slurm['ntasks']}",
    ]

    if "ntasks_per_node" in slurm:
        lines.append(
            f"{directive} --ntasks-per-node="
            f"{slurm['ntasks_per_node']}"
        )

    lines.extend(
        [
            f"{directive} --cpus-per-task={slurm['cpus_per_task']}",
            f"{directive} --gres={slurm['gres']}",
            f"{directive} -t {slurm['time']}",
            f"{directive} -o {stdout_name}",
            f"{directive} -e {stderr_name}",
        ]
    )

    return "\n".join(lines)


def render_qe_job_script(job: dict[str, Any]) -> str:
    slurm = job["slurm"]
    runtime = job["runtime"]

    directives = render_slurm_directives(
        slurm,
        stdout_name="slurm.out",
        stderr_name="slurm.err",
    )

    extra_args = " ".join(
        shlex.quote(argument)
        for argument in runtime.get("extra_args", [])
    )
    launcher = runtime.get("launcher", "mpirun --bind-to none")
    mpi_ranks = runtime.get("mpirun_np", slurm["ntasks"])

    binary_path = shlex.quote(str(expand_path(job["binary_path"])))
    input_path = shlex.quote(str(expand_path(job["input_path"])))

    if "ntasks_per_node" not in slurm:
        command_parts = [
            launcher,
            "-np",
            str(mpi_ranks),
            '"$QE_BIN"',
            "-nk",
            str(runtime["npools"]),
        ]
        if extra_args:
            command_parts.append(extra_args)
        command_parts.extend(["-in", '"$QE_INPUT"', ">", "qe.out"])
        return f"""#!/usr/bin/env bash
{directives}
set -euo pipefail

export OMP_NUM_THREADS={runtime['omp_num_threads']}
export QE_BIN={binary_path}
export QE_INPUT={input_path}

{' '.join(command_parts)}
"""

    run_dir = shlex.quote(str(expand_path(job["run_dir"])))
    pseudo_exports = "\n".join(
        f"PSEUDO_{idx}={shlex.quote(str(expand_path(path)))}; PSEUDO_SHA_{idx}={shlex.quote(job['pseudo_sha256'][path])}; export PSEUDO_{idx} PSEUDO_SHA_{idx}"
        for idx, path in enumerate(job["pseudo_paths"], 1)
    )
    pseudo_checks = "\n".join(
        f"check_hash \"$PSEUDO_{idx}\" \"$PSEUDO_SHA_{idx}\" pseudo_{idx}"
        for idx, _path in enumerate(job["pseudo_paths"], 1)
    )

    map_by = f"--map-by ppr:{slurm['ntasks_per_node']}:node"
    command_parts = [
        launcher,
        "-np",
        str(mpi_ranks),
        map_by,
        '"$RANK_WRAPPER_BIN"',
        ">",
        "qe.out",
    ]

    qe_command = " ".join(command_parts)
    profiler = job.get("profiler")
    if profiler:
        prefix = shlex.quote(profiler["output_prefix"])
        qe_command = (
            f"nsys profile --force-overwrite=true --trace=mpi,cuda,nvtx "
            f"--sample=none --output=\"$RUN_DIR\"/{prefix} {qe_command}"
        )
        profiler_stats = f"""
if command -v nsys >/dev/null 2>&1; then
    nsys stats --report cuda_api,cuda_gpu_trace,mpi_sum \"$RUN_DIR\"/{prefix}.nsys-rep > \"$RUN_DIR\"/nsys_stats.txt 2>&1 || true
fi
"""
    else:
        profiler_stats = ""

    return f"""#!/usr/bin/env bash
{directives}
set -euo pipefail

export OMP_NUM_THREADS={runtime['omp_num_threads']}
export QE_BIN={binary_path}
export QE_INPUT={input_path}
export QE_BIN_SHA256={shlex.quote(job['binary_sha256'])}
export QE_INPUT_SHA256={shlex.quote(job['input_sha256'])}
export RUN_DIR={run_dir}
export HIPAC_EXPECTED_RANKS={slurm['ntasks']}
export HIPAC_EXPECTED_NODES={slurm['nodes']}
export HIPAC_EXPECTED_RANKS_PER_NODE={slurm['ntasks_per_node']}
export HIPAC_EXPECTED_GPUS_PER_NODE={slurm['gpus_per_node']}
export HIPAC_QE_NPOOLS={runtime['npools']}
export HIPAC_QE_EXTRA_ARGS={shlex.quote(' '.join(runtime.get('extra_args', [])))}
export HIPAC_MAPPING_TIMEOUT_SECONDS=120
export HIPAC_MAPPING_RECORDS_DIR="$RUN_DIR/mapping_raw"
export HIPAC_MAPPING_STATE_DIR="$RUN_DIR/mapping_state"
export HIPAC_MAPPING_VALIDATOR={shlex.quote(str(REPO_ROOT / 'scripts' / 'qe_mapping_validator.py'))}
{pseudo_exports}

mkdir -p "$RUN_DIR" "$HIPAC_MAPPING_RECORDS_DIR" "$HIPAC_MAPPING_STATE_DIR"

check_hash() {{
    path="$1"
    expected="$2"
    label="$3"
    test -r "$path"
    actual=$(sha256sum "$path" | awk '{{print $1}}')
    if [ "$actual" != "$expected" ]; then
        echo "ERROR: $label sha256 mismatch: $actual != $expected" >&2
        exit 20
    fi
    printf '%s_path=%s\n' "$label" "$path"
    printf '%s_sha256=%s\n' "$label" "$actual"
}}

PROFILE_PATH={shlex.quote(str(REPO_ROOT / 'profiles' / 'nano4_h200_nvhpc259.sh'))}
if [ ! -r "$PROFILE_PATH" ]; then
    echo "ERROR: approved Nano4 profile is not readable: $PROFILE_PATH" >&2
    exit 21
fi
set +u
# shellcheck source=/dev/null
. "$PROFILE_PATH"
set -u

check_hash "$QE_BIN" "$QE_BIN_SHA256" qe_binary
check_hash "$QE_INPUT" "$QE_INPUT_SHA256" qe_input
{pseudo_checks}

MPIRUN_PATH=$(command -v mpirun || true)
if [ -z "$MPIRUN_PATH" ]; then
    echo 'ERROR: mpirun not resolved after profile load' >&2
    exit 22
fi
MPIRUN_REALPATH=$(realpath "$MPIRUN_PATH")
printf 'resolved_mpirun=%s\n' "$MPIRUN_PATH"
printf 'realpath_mpirun=%s\n' "$MPIRUN_REALPATH"
MPI_ROUTE_IDENTITY="$MPIRUN_REALPATH ${{OPAL_PREFIX:-}} ${{NVCOMPILER:-}} ${{NVHPC_ROOT:-}} ${{LOADEDMODULES:-}} ${{HIPAC_BUILD_ROUTE:-}}"
case "$MPI_ROUTE_IDENTITY" in
    *hpcx*|*HPCX*|*HPC-X*|*nvhpc*|*NVHPC*|*x86-nvhpc*) ;;
    *) echo 'ERROR: resolved MPI route is not identifiable as approved NVHPC/HPC-X after profile load' >&2; exit 23 ;;
esac
export HIPAC_MPI_ROUTE_IDENTITY="$MPI_ROUTE_IDENTITY"

WRAPPER_SRC={shlex.quote(str(REPO_ROOT / 'scripts' / 'qe_rank_wrapper.cu'))}
RANK_WRAPPER_BIN="$RUN_DIR/qe_rank_wrapper"
export RANK_WRAPPER_BIN
if [ ! -r "$WRAPPER_SRC" ] || [ ! -r "$HIPAC_MAPPING_VALIDATOR" ]; then
    echo 'ERROR: controller-owned rank wrapper or validator is not readable' >&2
    exit 24
fi
HIPAC_WRAPPER_SOURCE_SHA256=$(sha256sum "$WRAPPER_SRC" | awk '{{print $1}}')
HIPAC_MAPPING_VALIDATOR_SHA256=$(sha256sum "$HIPAC_MAPPING_VALIDATOR" | awk '{{print $1}}')
export HIPAC_WRAPPER_SOURCE_SHA256 HIPAC_MAPPING_VALIDATOR_SHA256
printf 'rank_wrapper_source=%s\n' "$WRAPPER_SRC"
printf 'rank_wrapper_source_sha256=%s\n' "$HIPAC_WRAPPER_SOURCE_SHA256"
printf 'mapping_validator=%s\n' "$HIPAC_MAPPING_VALIDATOR"
printf 'mapping_validator_sha256=%s\n' "$HIPAC_MAPPING_VALIDATOR_SHA256"

CUDA_WRAPPER_COMPILER=$(command -v nvcc || true)
if [ -n "$CUDA_WRAPPER_COMPILER" ]; then
    "$CUDA_WRAPPER_COMPILER" "$WRAPPER_SRC" -o "$RANK_WRAPPER_BIN"
else
    CUDA_WRAPPER_COMPILER=$(command -v nvc++ || true)
    if [ -z "$CUDA_WRAPPER_COMPILER" ]; then
        echo 'ERROR: approved NVHPC/CUDA compiler not resolved for rank wrapper' >&2
        exit 25
    fi
    "$CUDA_WRAPPER_COMPILER" -cuda "$WRAPPER_SRC" -o "$RANK_WRAPPER_BIN"
fi
chmod 750 "$RANK_WRAPPER_BIN"
printf 'rank_wrapper_compiler=%s\n' "$CUDA_WRAPPER_COMPILER"
printf 'launcher_matched_rank_wrapper=true\n'
printf 'qe_exec_pre_mapping_guard=forbidden\n'

{qe_command}
{profiler_stats}
"""


def build_job_metadata(
    manifest: dict[str, Any],
    job: dict[str, Any],
) -> dict[str, Any]:
    kind = job.get("job_kind", "qe")
    metadata: dict[str, Any] = {
        "schema_version": manifest["schema_version"],
        "trial_id": manifest["trial_id"],
        "config_id": job["config_id"],
        "job_kind": kind,
        "benchmark_valid": False,
        "performance_claim_allowed": False,
        "optimization_claim_allowed": False,
        "slurm": job["slurm"],
        "runtime": job["runtime"],
    }

    if manifest.get("schema_version") == MANIFEST_V2:
        metadata["run_root"] = manifest["run_root"]

    if kind == "qe":
        metadata.update(
            {
                "case_id": job.get("case_id"),
                "runtime_role": job.get("runtime_role"),
                "binary_path": job["binary_path"],
                "binary_sha256": job["binary_sha256"],
                "input_path": job["input_path"],
                "input_sha256": job["input_sha256"],
                "pseudo_paths": job["pseudo_paths"],
                "pseudo_sha256": job["pseudo_sha256"],
            }
        )
        if "profiler" in job:
            metadata["profiler"] = job["profiler"]
    elif kind == "environment_probe":
        metadata.update(
            {
                "probe_profile": job["probe_profile"],
                "probe_execution_status": "not_executed",
            }
        )
    else:
        fail(f"unsupported metadata job_kind: {kind}")

    return metadata


def render_environment_probe_script(
    job: dict[str, Any],
    *,
    manifest: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> str:
    slurm = job["slurm"]
    runtime = job["runtime"]
    config_data = config or load_config()
    paths = require_object(config_data.get("paths"), "config.paths")
    current_binary = require_object(
        config_data.get("current_binary"),
        "config.current_binary",
    )

    run_dir = require_absolute_path(job["run_dir"], "run_dir")
    run_root = require_absolute_path(
        manifest.get("run_root") if manifest else paths.get("run_root"),
        "run_root",
    )
    profile_path = require_absolute_path(
        paths.get("profile"),
        "config.paths.profile",
    )
    configured_binary_path = require_absolute_path(
        current_binary.get("path"),
        "config.current_binary.path",
    )
    accepted_g1_path = require_absolute_path(
        current_binary.get("path"),
        "config.current_binary.path",
    )

    directives = render_slurm_directives(
        slurm,
        stdout_name="slurm.out",
        stderr_name="slurm.err",
    )

    probe_body = r"""set -euo pipefail

printf 'task_hostname=%s\n' "$(hostname)"
printf 'task_date_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'SLURM_JOB_ID=%s\n' "${SLURM_JOB_ID:-}"
printf 'SLURM_NNODES=%s\n' "${SLURM_NNODES:-}"
printf 'SLURM_NODEID=%s\n' "${SLURM_NODEID:-}"
printf 'SLURM_PROCID=%s\n' "${SLURM_PROCID:-}"
printf 'SLURM_LOCALID=%s\n' "${SLURM_LOCALID:-}"
printf 'SLURM_CPU_BIND=%s\n' "${SLURM_CPU_BIND:-}"
printf 'SLURM_CPU_BIND_LIST=%s\n' "${SLURM_CPU_BIND_LIST:-}"
taskset -pc $$ || true
grep '^Cpus_allowed_list:' /proc/self/status || true
printf 'CUDA_VISIBLE_DEVICES=%s\n' "${CUDA_VISIBLE_DEVICES:-}"
"${CUDA_PROBE_BIN}"

test -r "${PROBE_MARKER}"
printf 'shared_marker_path=%s\n' "${PROBE_MARKER}"
sha256sum "${PROBE_MARKER}"
"""

    quoted_probe_body = shlex.quote(probe_body)
    cuda_source = r'''#include <cuda_runtime.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

static void die_cuda(const char *label, cudaError_t err) {
    if (err != cudaSuccess) {
        fprintf(stderr, "ERROR: %s: %s\n", label, cudaGetErrorString(err));
        exit(20);
    }
}

int main(void) {
    int count = -1;
    char host[256];
    die_cuda("cudaGetDeviceCount", cudaGetDeviceCount(&count));
    if (gethostname(host, sizeof(host)) != 0) {
        snprintf(host, sizeof(host), "unknown");
    }
    printf("cuda_runtime_visible_device_count=%d\n", count);
    printf("cuda_selected_visible_device_ordinal=0\n");
    printf("cuda_probe_hostname=%s\n", host);
    printf("cuda_probe_SLURM_PROCID=%s\n", getenv("SLURM_PROCID") ? getenv("SLURM_PROCID") : "");
    printf("cuda_probe_SLURM_LOCALID=%s\n", getenv("SLURM_LOCALID") ? getenv("SLURM_LOCALID") : "");
    printf("cuda_probe_CUDA_VISIBLE_DEVICES=%s\n", getenv("CUDA_VISIBLE_DEVICES") ? getenv("CUDA_VISIBLE_DEVICES") : "");
    if (count != 1) {
        fprintf(stderr, "ERROR: cuda visible device count must equal 1; observed %d\n", count);
        return 21;
    }
    cudaDeviceProp prop;
    die_cuda("cudaSetDevice", cudaSetDevice(0));
    die_cuda("cudaGetDeviceProperties", cudaGetDeviceProperties(&prop, 0));
    printf("cuda_visible_gpu_uuid=GPU-");
    for (int i = 0; i < 16; ++i) {
        printf("%02x", (unsigned char)prop.uuid.bytes[i]);
    }
    printf("\n");
    printf("cuda_visible_gpu_pci_bus_id=%04x:%02x:%02x.0\n", prop.pciDomainID, prop.pciBusID, prop.pciDeviceID);
    printf("cuda_visible_gpu_name=%s\n", prop.name);
    return 0;
}
'''
    quoted_cuda_source = shlex.quote(cuda_source)
    mpi_source = r'''#include <mpi.h>
#include <stdio.h>
#include <unistd.h>
int main(int argc, char **argv) {
    MPI_Init(&argc, &argv);
    int rank = -1, size = -1, sum = 0;
    char host[256];
    gethostname(host, sizeof(host));
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);
    MPI_Allreduce(&rank, &sum, 1, MPI_INT, MPI_SUM, MPI_COMM_WORLD);
    printf("mpi_rank=%d mpi_size=%d mpi_hostname=%s mpi_rank_sum=%d\n", rank, size, host, sum);
    MPI_Finalize();
    return 0;
}
'''
    quoted_mpi_source = shlex.quote(mpi_source)
    probe_trial_id = require_string(
        manifest.get("trial_id", "P1A-T001") if manifest else "P1A-T001",
        "trial_id",
    )

    return f"""#!/usr/bin/env bash
{directives}
set -euo pipefail

export OMP_NUM_THREADS={runtime['omp_num_threads']}
RUN_ROOT={shlex.quote(run_root)}
RUN_DIR={shlex.quote(run_dir)}
PROFILE_PATH={shlex.quote(profile_path)}
CONFIGURED_BINARY_PATH={shlex.quote(configured_binary_path)}
ACCEPTED_G1_SMOKE_PATH={shlex.quote(accepted_g1_path)}
EXPECTED_NODES={slurm['nodes']}
EXPECTED_TASKS={slurm['ntasks']}
EXPECTED_TASKS_PER_NODE={slurm['ntasks_per_node']}
EXPECTED_GPUS={slurm['total_gpus']}
export RUN_ROOT RUN_DIR PROFILE_PATH CONFIGURED_BINARY_PATH ACCEPTED_G1_SMOKE_PATH
export EXPECTED_NODES EXPECTED_TASKS EXPECTED_TASKS_PER_NODE EXPECTED_GPUS

printf 'probe_kind=environment_probe\n'
printf 'probe_profile={job['probe_profile']}\n'
printf 'allocation_host=%s\n' "$(hostname)"
printf 'allocation_nodelist=%s\n' "${{SLURM_JOB_NODELIST:-}}"
printf 'SLURM_JOB_ID=%s\n' "${{SLURM_JOB_ID:-}}"
printf 'SLURM_NNODES=%s\n' "${{SLURM_NNODES:-}}"
printf 'requested_nodes={slurm['nodes']}\n'
printf 'requested_tasks={slurm['ntasks']}\n'
printf 'requested_gpus={slurm['total_gpus']}\n'

mkdir -p "$RUN_DIR"
PROBE_MARKER="$RUN_DIR/p1a_t001_shared_fs_marker.txt"
export PROBE_MARKER
printf 'hipac26-p1a-t001-shared-marker trial={probe_trial_id} config={job['config_id']}\n' > "$PROBE_MARKER"
printf 'shared_marker_path=%s\n' "$PROBE_MARKER"
sha256sum "$PROBE_MARKER"

if [ ! -r "$PROFILE_PATH" ]; then
    echo "ERROR: approved Nano4 profile is not readable: $PROFILE_PATH" >&2
    exit 4
fi
set +u
# shellcheck source=/dev/null
. "$PROFILE_PATH"
set -u

safe_env_name_allowed() {{
    name="$1"
    upper="${{name^^}}"
    case "$upper" in
        *TOKEN*|*SECRET*|*PASSWORD*|*PASSWD*|*API_KEY*|*PRIVATE_KEY*|*CREDENTIAL*|*AUTH*) return 1 ;;
    esac
    case "$name" in
        PATH|LD_LIBRARY_PATH|MODULEPATH|LOADEDMODULES|OMP_NUM_THREADS|CUDA_VISIBLE_DEVICES|OPAL_PREFIX|NVCOMPILER|NVHPC_ROOT|HPCX_HOME|UCX_HOME|PMIX_RANK|PMIX_NAMESPACE|PMIX_SERVER_URI2|OMPI_COMM_WORLD_RANK|OMPI_COMM_WORLD_LOCAL_RANK|OMPI_COMM_WORLD_SIZE|OMPI_MCA_orte_hnp_uri|SLURM_JOB_ID|SLURM_JOB_NAME|SLURM_JOB_NODELIST|SLURM_NNODES|SLURM_NODEID|SLURM_PROCID|SLURM_LOCALID|SLURM_STEP_ID|SLURM_STEP_NUM_TASKS|SLURM_CPUS_PER_TASK|SLURM_CPU_BIND|SLURM_CPU_BIND_LIST|SLURM_TASKS_PER_NODE|SLURM_GPUS_ON_NODE|SLURM_JOB_GPUS|HIPAC_SITE|HIPAC_PLATFORM|HIPAC_GPU_TARGET|HIPAC_CUDA_CC_CANDIDATE|HIPAC_BUILD_ROUTE) return 0 ;;
        NVHPC_*|HPCX_*|UCX_*|OMPI_*|PMIX_*|SLURM_*) return 0 ;;
        *) return 1 ;;
    esac
}}
{{
    printf '%s\n' PATH LD_LIBRARY_PATH MODULEPATH LOADEDMODULES OMP_NUM_THREADS CUDA_VISIBLE_DEVICES OPAL_PREFIX NVCOMPILER NVHPC_ROOT HPCX_HOME UCX_HOME HIPAC_SITE HIPAC_PLATFORM HIPAC_GPU_TARGET HIPAC_CUDA_CC_CANDIDATE HIPAC_BUILD_ROUTE
    compgen -e
}} | sort -u | while IFS= read -r name; do
    if safe_env_name_allowed "$name"; then
        printf '%s=%s\n' "$name" "${{!name-}}"
    fi
done > "$RUN_DIR/environment_snapshot.txt"
if command -v module >/dev/null 2>&1; then
    module list > "$RUN_DIR/module_snapshot.txt" 2>&1 || true
else
    printf 'module command unavailable\n' > "$RUN_DIR/module_snapshot.txt"
fi

MPIRUN_PATH=$(command -v mpirun || true)
MPICC_PATH=$(command -v mpicc || true)
if [ -z "$MPIRUN_PATH" ] || [ -z "$MPICC_PATH" ]; then
    echo 'ERROR: approved MPI launcher/compiler not resolved after profile load' >&2
    exit 5
fi
MPIRUN_REALPATH=$(realpath "$MPIRUN_PATH")
MPICC_REALPATH=$(realpath "$MPICC_PATH")
printf 'resolved_mpirun=%s\n' "$MPIRUN_PATH"
printf 'resolved_mpicc=%s\n' "$MPICC_PATH"
printf 'realpath_mpirun=%s\n' "$MPIRUN_REALPATH"
printf 'realpath_mpicc=%s\n' "$MPICC_REALPATH"
MPI_ROUTE_IDENTITY="$MPIRUN_REALPATH $MPICC_REALPATH ${{OPAL_PREFIX:-}} ${{NVCOMPILER:-}} ${{NVHPC_ROOT:-}} ${{LOADEDMODULES:-}} ${{HIPAC_BUILD_ROUTE:-}}"
case "$MPI_ROUTE_IDENTITY" in
    *hpcx*|*HPCX*|*HPC-X*|*nvhpc*|*NVHPC*|*x86-nvhpc*) ;;
    *) echo 'ERROR: resolved MPI route is not identifiable as approved NVHPC/HPC-X after profile load' >&2; exit 6 ;;
esac
mpirun --version | head -n 5
mpicc --showme:version 2>/dev/null || mpicc --version | head -n 5
mpicc --showme:link 2>/dev/null || true
ldd "$MPIRUN_REALPATH" || true
ldd "$MPICC_REALPATH" || true

inspect_binary_identity() {{
    label="$1"
    target="$2"
    printf 'binary_identity_label=%s\n' "$label"
    printf 'binary_identity_path=%s\n' "$target"
    if [ -e "$target" ]; then
        realpath "$target"
        readlink -f "$target"
        sha256sum "$target"
        file "$target"
        ldd "$target" || true
    else
        printf 'binary_identity_exists=false\n'
    fi
}}
inspect_binary_identity configured_current_binary "$CONFIGURED_BINARY_PATH"
inspect_binary_identity accepted_g1_smoke_binary "$ACCEPTED_G1_SMOKE_PATH"
printf 'binary_identity_status=accepted_g1_production_binary_no_performance_claim\n'

command -v srun >/dev/null 2>&1 || {{
    echo 'ERROR: srun unavailable inside allocation' >&2
    exit 2
}}

printf %s {quoted_cuda_source} > "$RUN_DIR/p1a_t001_cuda_probe.cu"
CUDA_PROBE_BIN="$RUN_DIR/p1a_t001_cuda_probe"
export CUDA_PROBE_BIN
CUDA_COMPILER=$(command -v nvcc || true)
if [ -n "$CUDA_COMPILER" ]; then
    "$CUDA_COMPILER" "$RUN_DIR/p1a_t001_cuda_probe.cu" -o "$CUDA_PROBE_BIN"
else
    CUDA_COMPILER=$(command -v nvc++ || true)
    if [ -z "$CUDA_COMPILER" ]; then
        echo 'ERROR: approved NVHPC/CUDA compiler not resolved for CUDA task probe' >&2
        exit 9
    fi
    "$CUDA_COMPILER" -cuda "$RUN_DIR/p1a_t001_cuda_probe.cu" -o "$CUDA_PROBE_BIN"
fi
printf 'cuda_probe_compiler=%s\n' "$CUDA_COMPILER"
chmod 750 "$CUDA_PROBE_BIN"

srun \
    --nodes={slurm['nodes']} \
    --ntasks={slurm['ntasks']} \
    --ntasks-per-node={slurm['ntasks_per_node']} \
    --gpus-per-task=1 \
    --gpu-bind=single:1 \
    bash -lc {quoted_probe_body}

printf %s {quoted_mpi_source} > "$RUN_DIR/p1a_t001_mpi_probe.c"
mpicc "$RUN_DIR/p1a_t001_mpi_probe.c" -o "$RUN_DIR/p1a_t001_mpi_probe"
mpirun --bind-to none -np {slurm['ntasks']} "$RUN_DIR/p1a_t001_mpi_probe" \
    | tee "$RUN_DIR/p1a_t001_mpi_probe.out"
rank_count=$(grep -c '^mpi_rank=' "$RUN_DIR/p1a_t001_mpi_probe.out")
node_count=$(awk '/^mpi_rank=/ {{print $3}}' "$RUN_DIR/p1a_t001_mpi_probe.out" | sort -u | wc -l)
if [ "$rank_count" -ne {slurm['ntasks']} ]; then
    echo "ERROR: MPI rank count mismatch: $rank_count != {slurm['ntasks']}" >&2
    exit 7
fi
if [ "$node_count" -ne {slurm['nodes']} ]; then
    echo "ERROR: MPI node count mismatch: $node_count != {slurm['nodes']}" >&2
    exit 8
fi
"""


def render_job_script(
    job: dict[str, Any],
    *,
    manifest: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> str:
    kind = job.get("job_kind", "qe")

    if kind == "qe":
        return render_qe_job_script(job)
    if kind == "environment_probe":
        return render_environment_probe_script(
            job,
            manifest=manifest,
            config=config,
        )

    fail(f"unsupported render job_kind: {kind}")


def validate_rendered_script_for_job(
    job: dict[str, Any],
    script: str,
) -> None:
    if not script.startswith("#!/usr/bin/env bash\n"):
        fail("rendered job script has invalid shebang")
    if "set -euo pipefail" not in script:
        fail("rendered job script lacks fail-closed shell options")

    kind = job.get("job_kind", "qe")

    if kind == "environment_probe":
        forbidden_patterns = {
            "QE_BIN": r"\bQE_BIN\b",
            "QE_INPUT": r"\bQE_INPUT\b",
            "QE input flag": r"\s-in\s",
            "qe.out": r"\bqe\.out\b",
        }

        for label, pattern in forbidden_patterns.items():
            if re.search(pattern, script):
                fail(
                    "environment_probe rendered script contains "
                    f"forbidden QE token: {label}"
                )

        required_tokens = (
            "probe_kind=environment_probe",
            "srun",
            "--gpus-per-task=1",
            "--gpu-bind=single:1",
            "hostname",
            "p1a_t001_cuda_probe.cu",
            "cudaGetDeviceCount",
            "cuda_runtime_visible_device_count",
            "cuda_selected_visible_device_ordinal",
            "cuda_visible_gpu_uuid",
            "cuda_visible_gpu_pci_bus_id",
            "taskset -pc $$",
            "Cpus_allowed_list",
            "CUDA_VISIBLE_DEVICES",
            "p1a_t001_shared_fs_marker.txt",
            "sha256sum \"${PROBE_MARKER}\"",
            "resolved_mpirun",
            "resolved_mpicc",
            "realpath_mpirun",
            "realpath_mpicc",
            "mpicc --showme:link",
            "MPI_Allreduce",
            "mpirun --bind-to none",
            "CONFIGURED_BINARY_PATH",
            "ACCEPTED_G1_SMOKE_PATH",
            "binary_identity_status=accepted_g1_production_binary_no_performance_claim",
        )
        for token in required_tokens:
            if token not in script:
                fail(
                    "environment_probe rendered script missing "
                    f"required token: {token}"
                )
        return

    if kind != "qe":
        fail(f"unsupported rendered job_kind: {kind}")

    if "ntasks_per_node" not in job.get("slurm", {}):
        for token in ('"$QE_BIN"', '"$QE_INPUT"', "qe.out"):
            if token not in script:
                fail(f"legacy QE rendered script missing required token: {token}")
        return

    required_tokens = (
        "mpirun --bind-to none",
        '"$RANK_WRAPPER_BIN"',
        "qe_rank_wrapper.cu",
        "qe_mapping_validator.py",
        "launcher_matched_rank_wrapper=true",
        "HIPAC_MAPPING_RECORDS_DIR",
        "HIPAC_MAPPING_STATE_DIR",
        "HIPAC_EXPECTED_RANKS",
        "HIPAC_EXPECTED_RANKS_PER_NODE",
        "HIPAC_EXPECTED_GPUS_PER_NODE",
        "HIPAC_MPI_ROUTE_IDENTITY",
        "qe.out",
    )
    for token in required_tokens:
        if token not in script:
            fail(f"QE rendered script missing required token: {token}")
    forbidden_patterns = {
        "independent srun mapping proof": r"\bsrun\b.*mapping",
        "manifest-provided wrapper": r"\$\{?MANIFEST_.*WRAPPER",
    }
    for label, pattern in forbidden_patterns.items():
        if re.search(pattern, script):
            fail(f"QE rendered script contains forbidden token: {label}")


def cmd_render(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    manifest = load_manifest(manifest_path)
    validate_manifest(
        manifest,
        submit_mode=False,
        strict_files=args.strict_files,
    )

    is_v2 = manifest.get("schema_version") == MANIFEST_V2

    for job in manifest["jobs"]:
        run_dir = expand_path(job["run_dir"])

        if is_v2 and run_dir.exists():
            fail(
                "manifest v2 render refuses existing run_dir: "
                f"{run_dir}"
            )

        run_dir.mkdir(
            parents=True,
            exist_ok=False if args.no_overwrite or is_v2 else True,
        )

        metadata = build_job_metadata(manifest, job)

        write_json(run_dir / "metadata.json", metadata)

        script = render_job_script(job, manifest=manifest)
        validate_rendered_script_for_job(job, script)

        job_sh = run_dir / "job.sh"
        job_sh.write_text(script, encoding="utf-8")
        job_sh.chmod(0o640)

    print(f"render PASS: {len(manifest['jobs'])} jobs")
    return 0


def validate_rendered_files(
    manifest: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> None:
    forbidden = [
        "qe.out",
        "job_id.txt",
        "submission_record.txt",
        "submission_record.json",
        "env_snapshot.txt",
        "module_snapshot.txt",
    ]

    for job in manifest["jobs"]:
        run_dir = expand_path(job["run_dir"])
        job_sh = run_dir / "job.sh"
        metadata_path = run_dir / "metadata.json"

        if not run_dir.is_dir():
            fail(f"run_dir missing: {run_dir}")
        if job_sh.is_symlink():
            fail(f"job.sh must not be a symlink: {job_sh}")
        if not job_sh.is_file():
            fail(f"job.sh missing: {job_sh}")
        if metadata_path.is_symlink():
            fail(f"metadata.json must not be a symlink: {metadata_path}")
        if not metadata_path.is_file():
            fail(f"metadata.json missing: {metadata_path}")

        mode = stat.S_IMODE(job_sh.stat().st_mode)
        if mode != 0o640:
            fail(
                f"job.sh mode must be 0640: "
                f"{job_sh}: {oct(mode)}"
            )
        if os.access(job_sh, os.X_OK):
            fail(f"job.sh must not be executable: {job_sh}")

        script = job_sh.read_text(
            encoding="utf-8",
            errors="strict",
        )
        expected_script = render_job_script(
            job,
            manifest=manifest,
            config=config,
        )
        if script != expected_script:
            fail(f"rendered job.sh differs from manifest: {job_sh}")
        validate_rendered_script_for_job(job, script)

        metadata = read_json(metadata_path)
        expected_metadata = build_job_metadata(manifest, job)
        if metadata != expected_metadata:
            fail(f"metadata.json differs from manifest: {metadata_path}")

        for name in forbidden:
            if (run_dir / name).exists():
                fail(
                    f"forbidden render output exists: "
                    f"{run_dir / name}"
                )

        if (run_dir / "tmp").exists():
            fail(
                f"forbidden tmp directory exists: "
                f"{run_dir / 'tmp'}"
            )


def cmd_dry_run(args: argparse.Namespace) -> int:
    manifest = load_manifest(Path(args.manifest))
    validate_manifest(
        manifest,
        submit_mode=False,
        strict_files=args.strict_files,
    )

    rendered: list[dict[str, Any]] = []

    for job in manifest["jobs"]:
        script = render_job_script(job, manifest=manifest)
        validate_rendered_script_for_job(job, script)

        rendered.append(
            {
                "config_id": job["config_id"],
                "job_kind": job.get("job_kind", "qe"),
                "run_dir": normalized_path_text(job["run_dir"]),
                "script_sha256": hashlib.sha256(
                    script.encode("utf-8")
                ).hexdigest(),
            }
        )

    result = {
        "dry_run": "PASS",
        "scheduler_contacted": False,
        "files_created": False,
        "jobs": rendered,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    manifest = load_manifest(Path(args.manifest))
    validate_manifest(manifest, submit_mode=False, strict_files=args.strict_files)
    if args.rendered:
        validate_rendered_files(manifest)
    print("validate PASS")
    return 0


def cmd_submit(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    manifest = load_manifest(manifest_path)
    validate_manifest(manifest, submit_mode=True, strict_files=args.strict_files)
    validate_rendered_files(manifest)
    permit = load_and_validate_submit_permit(
        manifest_path=manifest_path,
        manifest=manifest,
    )
    permit_audit = consume_submit_permit(
        manifest_path=manifest_path,
        manifest=manifest,
        permit=permit,
    )

    attempt_dir = create_attempt_directory(
        permit.get("_manifest_sha256", manifest_sha256(manifest_path)) if permit else manifest_sha256(manifest_path),
        manifest["trial_id"],
    )
    write_json(attempt_dir / "submit_attempt.json", {
        "trial_id": manifest["trial_id"],
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_sha256(manifest_path),
        "scheduler_contacted": False,
        "retention": "controller_audit_no_secrets",
    })

    submit_cmd = production_submit_command()
    submitted: list[dict[str, str]] = []
    for job in manifest["jobs"]:
        run_dir = expand_path(job["run_dir"])
        job_sh = run_dir / "job.sh"
        result = subprocess.run(
            [submit_cmd, str(job_sh)],
            cwd=str(run_dir),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        write_json(attempt_dir / "scheduler_result.json", {
            "trial_id": manifest["trial_id"],
            "config_id": job["config_id"],
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "scheduler_contacted": True,
        })
        if result.returncode != 0:
            update_consumed_attempt(
                permit_audit,
                wrapper_exit_status=result.returncode,
                scheduler_contacted=True,
                job_id=None,
                final_state="scheduler_rejected",
            )
            fail(f"submit failed for {job['config_id']}: {result.stderr.strip()}")
        match = re.search(r"(\d+)", result.stdout)
        if not match:
            update_consumed_attempt(
                permit_audit,
                wrapper_exit_status=result.returncode,
                scheduler_contacted=True,
                job_id=None,
                final_state="job_id_parse_failed_after_scheduler_contact",
            )
            fail(f"cannot parse job id for {job['config_id']}: {result.stdout.strip()}")
        job_id = match.group(1)
        (run_dir / "job_id.txt").write_text(job_id + "\n", encoding="utf-8")
        write_json(run_dir / "submission_record.json", {
            "trial_id": manifest["trial_id"],
            "config_id": job["config_id"],
            "job_id": job_id,
            "benchmark_valid": False,
            "submitter": "qe_runctl.py",
            "manifest_sha256": manifest_sha256(manifest_path),
            "permit_consumed": True,
            "attempt_index": permit_audit.get("attempt_index") if permit_audit else None,
        })
        update_consumed_attempt(
            permit_audit,
            wrapper_exit_status=result.returncode,
            scheduler_contacted=True,
            job_id=job_id,
            final_state="submitted",
        )
        submitted.append({"config_id": job["config_id"], "job_id": job_id})
    print(json.dumps({"submitted": submitted}, indent=2))
    return 0


def parse_qe_output(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    energy_matches = re.findall(
        r"^\s*!?\s*total energy\s+=\s+(-?\d+\.\d+)\s+Ry",
        text,
        re.MULTILINE,
    )
    accuracy_matches = re.findall(
        r"estimated\s+scf\s+accuracy\s+<\s+([0-9.+\-Ee]+)\s+Ry",
        text,
        re.IGNORECASE,
    )
    iteration_count = len(re.findall(r"^\s*iteration\s+#", text, re.MULTILINE))
    converged = "convergence has been achieved" in text.lower()
    maxstep_stop = "convergence not achieved after" in text.lower()
    job_done = "JOB DONE" in text

    def int_match(pattern: str) -> int | None:
        match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
        return int(match.group(1)) if match else None

    def float_match(pattern: str) -> float | None:
        match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
        return float(match.group(1)) if match else None

    dense_grid = None
    dense_match = re.search(
        r"Dense\s+grid:\s+\d+\s+G-vectors\s+FFT dimensions:\s+\(\s*(\d+),\s*(\d+),\s*(\d+)\)",
        text,
    )
    if dense_match:
        dense_grid = [int(value) for value in dense_match.groups()]

    smooth_grid = None
    smooth_match = re.search(
        r"Smooth\s+grid:\s+\d+\s+G-vectors\s+FFT dimensions:\s+\(\s*(\d+),\s*(\d+),\s*(\d+)\)",
        text,
    )
    if smooth_match:
        smooth_grid = [int(value) for value in smooth_match.groups()]

    wall_seconds = None
    m = re.search(r"PWSCF\s+:.*?CPU.*?(\d+)h(\d+)m([0-9.]+)s\s+WALL", text)
    if m:
        wall_seconds = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    else:
        m2 = re.search(r"PWSCF\s+:.*?([0-9.]+)s\s+WALL", text)
        if m2:
            wall_seconds = float(m2.group(1))

    return {
        "qe_output": str(path),
        "benchmark_valid": False,
        "job_done": job_done,
        "converged": converged,
        "maxstep_stop": maxstep_stop,
        "final_energy_ry": float(energy_matches[-1]) if energy_matches else None,
        "total_energy_sequence_ry": [float(value) for value in energy_matches],
        "estimated_scf_accuracy_sequence_ry": [float(value) for value in accuracy_matches],
        "final_estimated_scf_accuracy_ry": float(accuracy_matches[-1]) if accuracy_matches else None,
        "scf_iterations": iteration_count if iteration_count else None,
        "atoms": int_match(r"number of atoms/cell\s+=\s+(\d+)"),
        "electrons": float_match(r"number of electrons\s+=\s+([0-9.]+)"),
        "bands": int_match(r"number of Kohn-Sham states\s*=\s+(\d+)"),
        "observed_k_points": int_match(r"number of k points\s*=\s+(\d+)"),
        "dense_fft_grid": dense_grid,
        "smooth_fft_grid": smooth_grid,
        "pwscf_wall_seconds": wall_seconds,
    }


def require_qe_jobs(
    manifest: dict[str, Any],
    operation: str,
) -> None:
    for job in manifest["jobs"]:
        if job.get("job_kind", "qe") != "qe":
            fail(
                f"{operation} supports QE jobs only; "
                f"found {job.get('job_kind')}"
            )


def cmd_parse(args: argparse.Namespace) -> int:
    manifest = load_manifest(Path(args.manifest))
    validate_manifest(manifest, submit_mode=False, strict_files=False)
    require_qe_jobs(manifest, "parse")
    for job in manifest["jobs"]:
        run_dir = expand_path(job["run_dir"])
        qe_out = run_dir / "qe.out"
        if not qe_out.exists():
            if args.allow_missing:
                continue
            fail(f"qe.out missing: {qe_out}")
        parsed = parse_qe_output(qe_out)
        parsed.update({
            "trial_id": manifest["trial_id"],
            "config_id": job["config_id"],
            "runtime": job["runtime"],
            "slurm": job["slurm"],
        })
        write_json(run_dir / "parsed.json", parsed)
    print("parse PASS")
    return 0


def cmd_summarize(args: argparse.Namespace) -> int:
    manifest = load_manifest(Path(args.manifest))
    require_qe_jobs(manifest, "summarize")
    rows: list[dict[str, Any]] = []
    for job in manifest["jobs"]:
        run_dir = expand_path(job["run_dir"])
        parsed_path = run_dir / "parsed.json"
        if not parsed_path.exists():
            continue
        parsed = read_json(parsed_path)
        rows.append({
            "config_id": job["config_id"],
            "benchmark_valid": False,
            "job_done": parsed.get("job_done"),
            "converged": parsed.get("converged"),
            "final_energy_ry": parsed.get("final_energy_ry"),
            "scf_iterations": parsed.get("scf_iterations"),
            "pwscf_wall_seconds": parsed.get("pwscf_wall_seconds"),
            "ntasks": job["slurm"].get("ntasks"),
            "omp_num_threads": job["runtime"].get("omp_num_threads"),
            "npools": job["runtime"].get("npools"),
        })
    summary = {
        "trial_id": manifest["trial_id"],
        "benchmark_valid": False,
        "rows": rows,
        "note": "Observed runtime summary only; not a benchmark or optimization claim.",
    }
    out = Path(args.output) if args.output else Path("summary.json")
    write_json(out, summary)
    print(f"summary written: {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Clean QE automation controller")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("render")
    r.add_argument("--manifest", required=True)
    r.add_argument("--strict-files", action="store_true")
    r.add_argument("--no-overwrite", action="store_true")
    r.set_defaults(func=cmd_render)

    v = sub.add_parser("validate")
    v.add_argument("--manifest", required=True)
    v.add_argument("--strict-files", action="store_true")
    v.add_argument("--rendered", action="store_true")
    v.set_defaults(func=cmd_validate)

    d = sub.add_parser("dry-run")
    d.add_argument("--manifest", required=True)
    d.add_argument("--strict-files", action="store_true")
    d.set_defaults(func=cmd_dry_run)

    s = sub.add_parser("submit")
    s.add_argument("--manifest", required=True)
    s.add_argument("--strict-files", action="store_true")
    s.set_defaults(func=cmd_submit)

    pa = sub.add_parser("parse")
    pa.add_argument("--manifest", required=True)
    pa.add_argument("--allow-missing", action="store_true")
    pa.set_defaults(func=cmd_parse)

    sm = sub.add_parser("summarize")
    sm.add_argument("--manifest", required=True)
    sm.add_argument("--output")
    sm.set_defaults(func=cmd_summarize)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except RunCtlError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
