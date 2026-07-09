#!/usr/bin/env python3
"""Minimal QE automation controller for hipac26-qe.

Subcommands:
  render     Create run directories and non-executable job scripts.
  validate   Fail-closed manifest/render validation.
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
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "config" / "nano4.json"


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


def fail(msg: str) -> None:
    raise RunCtlError(msg)


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = read_json(path)
    validate_manifest(manifest, submit_mode=False, strict_files=False)
    return manifest


def validate_manifest(manifest: dict[str, Any], *, submit_mode: bool, strict_files: bool) -> None:
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
        if manifest["allowed_submit"] is True and manifest["approved_by_human"] is not True:
            fail("allowed_submit=true requires approved_by_human=true")

    jobs = manifest.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        fail("jobs must be a non-empty list")

    seen: set[str] = set()
    for job in jobs:
        validate_job(job, strict_files=strict_files)
        cid = job["config_id"]
        if cid in seen:
            fail(f"duplicate config_id: {cid}")
        seen.add(cid)


def validate_job(job: dict[str, Any], *, strict_files: bool) -> None:
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

    if not re.match(r"^cfg[0-9]{3}[_A-Za-z0-9-]*$", job["config_id"]):
        fail(f"invalid config_id: {job['config_id']}")

    for hash_key in ["binary_sha256", "input_sha256"]:
        if not re.match(r"^[a-fA-F0-9]{64}$", job[hash_key]):
            fail(f"invalid sha256 field: {hash_key}")

    if not isinstance(job["pseudo_paths"], list) or not job["pseudo_paths"]:
        fail("pseudo_paths must be non-empty list")
    if not isinstance(job["pseudo_sha256"], dict):
        fail("pseudo_sha256 must be object")

    slurm = job["slurm"]
    for key in ["account", "partition", "nodes", "ntasks", "cpus_per_task", "gres", "time"]:
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
    if int(runtime["omp_num_threads"]) != int(slurm["cpus_per_task"]):
        fail("omp_num_threads must equal cpus_per_task")

    if strict_files:
        check_hash(expand_path(job["binary_path"]), job["binary_sha256"], "binary")
        check_hash(expand_path(job["input_path"]), job["input_sha256"], "input")
        for p in job["pseudo_paths"]:
            pseudo_path = expand_path(p)
            expected = job["pseudo_sha256"].get(str(pseudo_path)) or job["pseudo_sha256"].get(p)
            if not expected:
                fail(f"missing pseudo hash for {p}")
            check_hash(pseudo_path, expected, "pseudo")


def check_hash(path: Path, expected: str, label: str) -> None:
    if not path.exists():
        fail(f"{label} path missing: {path}")
    actual = sha256_file(path)
    if actual.lower() != expected.lower():
        fail(f"{label} sha256 mismatch: {path}: {actual} != {expected}")


def render_job_script(job: dict[str, Any]) -> str:
    s = job["slurm"]
    r = job["runtime"]
    extra_args = " ".join(r.get("extra_args", []))
    launcher = r.get("launcher", "mpirun --bind-to none")
    np = r.get("mpirun_np", s["ntasks"])
    directive = "#" + "SBATCH"
    return f"""#!/usr/bin/env bash
set -euo pipefail
{directive} -A {s['account']}
{directive} -p {s['partition']}
{directive} -N {s['nodes']}
{directive} --ntasks={s['ntasks']}
{directive} --cpus-per-task={s['cpus_per_task']}
{directive} --gres={s['gres']}
{directive} -t {s['time']}
{directive} -o slurm.out
{directive} -e slurm.err

export OMP_NUM_THREADS={r['omp_num_threads']}
export QE_BIN={job['binary_path']}
export QE_INPUT={job['input_path']}

{launcher} -np {np} "$QE_BIN" -nk {r['npools']} {extra_args} -in "$QE_INPUT" > qe.out
"""


def cmd_render(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    manifest = load_manifest(manifest_path)
    validate_manifest(manifest, submit_mode=False, strict_files=args.strict_files)

    for job in manifest["jobs"]:
        run_dir = expand_path(job["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=False if args.no_overwrite else True)
        write_json(run_dir / "metadata.json", {
            "trial_id": manifest["trial_id"],
            "config_id": job["config_id"],
            "benchmark_valid": False,
            "binary_path": job["binary_path"],
            "binary_sha256": job["binary_sha256"],
            "input_path": job["input_path"],
            "input_sha256": job["input_sha256"],
            "pseudo_paths": job["pseudo_paths"],
            "pseudo_sha256": job["pseudo_sha256"],
            "slurm": job["slurm"],
            "runtime": job["runtime"],
        })
        job_sh = run_dir / "job.sh"
        job_sh.write_text(render_job_script(job), encoding="utf-8")
        job_sh.chmod(0o640)
    print(f"render PASS: {len(manifest['jobs'])} jobs")
    return 0


def validate_rendered_files(manifest: dict[str, Any]) -> None:
    forbidden = [
        "qe.out",
        "job_id.txt",
        "submission_record.txt",
        "env_snapshot.txt",
        "module_snapshot.txt",
    ]
    for job in manifest["jobs"]:
        run_dir = expand_path(job["run_dir"])
        job_sh = run_dir / "job.sh"
        metadata = run_dir / "metadata.json"
        if not run_dir.is_dir():
            fail(f"run_dir missing: {run_dir}")
        if not job_sh.exists():
            fail(f"job.sh missing: {job_sh}")
        if not metadata.exists():
            fail(f"metadata.json missing: {metadata}")
        mode = stat.S_IMODE(job_sh.stat().st_mode)
        if mode != 0o640:
            fail(f"job.sh mode must be 0640: {job_sh}: {oct(mode)}")
        if os.access(job_sh, os.X_OK):
            fail(f"job.sh must not be executable: {job_sh}")
        for name in forbidden:
            if (run_dir / name).exists():
                fail(f"forbidden render output exists: {run_dir / name}")
        if (run_dir / "tmp").exists():
            fail(f"forbidden tmp directory exists: {run_dir / 'tmp'}")


def cmd_validate(args: argparse.Namespace) -> int:
    manifest = load_manifest(Path(args.manifest))
    validate_manifest(manifest, submit_mode=False, strict_files=args.strict_files)
    if args.rendered:
        validate_rendered_files(manifest)
    print("validate PASS")
    return 0


def cmd_submit(args: argparse.Namespace) -> int:
    manifest = load_manifest(Path(args.manifest))
    validate_manifest(manifest, submit_mode=True, strict_files=args.strict_files)
    validate_rendered_files(manifest)

    submit_cmd = os.environ.get("HIPAC_SUBMIT_CMD", "sbatch")
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
        if result.returncode != 0:
            fail(f"submit failed for {job['config_id']}: {result.stderr.strip()}")
        match = re.search(r"(\d+)", result.stdout)
        if not match:
            fail(f"cannot parse job id for {job['config_id']}: {result.stdout.strip()}")
        job_id = match.group(1)
        (run_dir / "job_id.txt").write_text(job_id + "\n", encoding="utf-8")
        write_json(run_dir / "submission_record.json", {
            "trial_id": manifest["trial_id"],
            "config_id": job["config_id"],
            "job_id": job_id,
            "benchmark_valid": False,
            "submitter": "qe_runctl.py",
        })
        submitted.append({"config_id": job["config_id"], "job_id": job_id})
    print(json.dumps({"submitted": submitted}, indent=2))
    return 0


def parse_qe_output(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    energy_matches = re.findall(r"!\s+total energy\s+=\s+(-?\d+\.\d+)\s+Ry", text)
    iteration_count = len(re.findall(r"^\s*iteration\s+#", text, re.MULTILINE))
    converged = "convergence has been achieved" in text.lower()
    job_done = "JOB DONE" in text

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
        "final_energy_ry": float(energy_matches[-1]) if energy_matches else None,
        "scf_iterations": iteration_count if iteration_count else None,
        "pwscf_wall_seconds": wall_seconds,
    }


def cmd_parse(args: argparse.Namespace) -> int:
    manifest = load_manifest(Path(args.manifest))
    validate_manifest(manifest, submit_mode=False, strict_files=False)
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
