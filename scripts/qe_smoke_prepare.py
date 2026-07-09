#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import time
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_atomic_species(input_path: Path) -> list[str]:
    lines = input_path.read_text(errors="replace").splitlines()
    pseudos: list[str] = []
    inside = False

    for line in lines:
        s = line.strip()
        if s == "ATOMIC_SPECIES":
            inside = True
            continue
        if inside:
            if not s:
                continue
            if s.startswith(("CELL_PARAMETERS", "ATOMIC_POSITIONS", "K_POINTS", "&")):
                break
            parts = s.split()
            if len(parts) >= 3:
                pseudos.append(parts[2])

    return pseudos


def patch_outdir(input_path: Path) -> None:
    text = input_path.read_text()
    text = re.sub(
        r"outdir\s*=\s*['\"]\./out['\"]",
        "outdir      = './outdir'",
        text,
    )
    input_path.write_text(text)


def shell_env_line(key: str, value: str) -> str:
    return f"export {key}={shlex.quote(value)}\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Prepare a controlled QE smoke run directory.")
    ap.add_argument("--workroot", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--buildroot", required=True)
    ap.add_argument("--caseroot", required=True)
    ap.add_argument("--pseudoroot", required=True)
    ap.add_argument("--runroot", required=True)
    ap.add_argument("--gate-id", default="BUILD-SMOKE-T001")
    ap.add_argument("--run-type", default="smoke")
    ap.add_argument("--build-id", default="G1-qe75-nvhpc259-gpu-base")
    ap.add_argument("--case-name", default="smoke-si8")
    ap.add_argument("--build-hash", required=True)
    ap.add_argument("--pwx", default="")
    ap.add_argument("--slurm-job-id", default="")
    ap.add_argument("--partition", default="dev")
    ap.add_argument("--nodes", default="1")
    ap.add_argument("--ntasks", default="1")
    ap.add_argument("--ntasks-per-node", default="1")
    ap.add_argument("--cpus-per-task", default="12")
    ap.add_argument("--gres", default="gpu:1")
    ap.add_argument("--time-limit", default="00:20:00")
    args = ap.parse_args()

    workroot = Path(args.workroot)
    repo = Path(args.repo)
    buildroot = Path(args.buildroot)
    caseroot = Path(args.caseroot)
    pseudoroot = Path(args.pseudoroot)
    runroot = Path(args.runroot)

    pwx = Path(args.pwx) if args.pwx else buildroot / args.build_id / "install/bin/pw.x"
    src_input = caseroot / args.case_name / "pw.in"

    if not pwx.exists() or not os.access(pwx, os.X_OK):
        raise SystemExit(f"ERROR: pw.x missing or not executable: {pwx}")

    if not src_input.exists():
        raise SystemExit(f"ERROR: input missing: {src_input}")

    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    job_id = args.slurm_job_id or "nojob"
    run_id = f"{args.gate_id}__{args.build_id}__{args.case_name}__job{job_id}__{timestamp}"
    run_dir = runroot / args.gate_id / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "outdir").mkdir(parents=True, exist_ok=True)

    copied_input = run_dir / "pw.in"
    copied_input.write_text(src_input.read_text())
    patch_outdir(copied_input)

    resolved_sbatch = run_dir / "resolved_sbatch.sh"
    resolved_sbatch.write_text((repo / "scripts/run/smoke_gpu.sbatch").read_text())

    input_hash = sha256_file(copied_input)
    (run_dir / "input.sha256").write_text(f"{input_hash}  {copied_input}\n")

    pseudo_files = parse_atomic_species(copied_input)
    pseudo_records = []
    pseudo_hash_lines = []
    missing = []

    for filename in pseudo_files:
        p = pseudoroot / filename
        if not p.exists():
            missing.append(str(p))
            pseudo_records.append({
                "filename": filename,
                "path": str(p),
                "exists": False,
                "sha256": None,
            })
            continue
        h = sha256_file(p)
        pseudo_records.append({
            "filename": filename,
            "path": str(p),
            "exists": True,
            "sha256": h,
        })
        pseudo_hash_lines.append(f"{h}  {p}\n")

    (run_dir / "pseudo_files.json").write_text(json.dumps(pseudo_records, indent=2) + "\n")
    (run_dir / "pseudo.sha256").write_text("".join(pseudo_hash_lines))

    if missing:
        for item in missing:
            print(f"ERROR: missing pseudo file: {item}", flush=True)
        raise SystemExit(93)

    try:
        repo_commit = subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            text=True,
        ).strip()
    except Exception:
        repo_commit = ""

    pseudo_hashes = [r["sha256"] for r in pseudo_records if r.get("sha256")]

    metadata = {
        "gate_id": args.gate_id,
        "run_type": args.run_type,
        "benchmark_valid": False,
        "performance_claim_allowed": False,
        "optimization_claim_allowed": False,
        "qe_execution_allowed_by_token": True,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "candidate_id": args.build_id,
        "candidate_role": "performance_candidate",
        "build_hash": args.build_hash,
        "pw_x_path": str(pwx),
        "case_name": args.case_name,
        "input_type": "Smoke" if args.case_name == "smoke-si8" else "unknown",
        "input_path": str(src_input),
        "copied_input_path": str(copied_input),
        "input_hash": input_hash,
        "pseudo_dir": str(pseudoroot),
        "pseudo_files": pseudo_files,
        "pseudo_hashes": pseudo_hashes,
        "pseudo_status": "available",
        "partition": args.partition,
        "nodes": args.nodes,
        "ntasks": args.ntasks,
        "ntasks_per_node": args.ntasks_per_node,
        "cpus_per_task": args.cpus_per_task,
        "gres": args.gres,
        "time_limit": args.time_limit,
        "slurm_job_id": args.slurm_job_id,
        "slurm_state": "unknown_until_sacct",
        "repo_commit": repo_commit,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "prepared",
        "launcher": "direct_singleton",
        "failure_class": None,
    }

    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")

    command = (
        f"export OMP_NUM_THREADS={args.cpus_per_task}\n"
        f"cd {shlex.quote(str(run_dir))}\n"
        f"{shlex.quote(str(pwx))} -in {shlex.quote(str(copied_input))} "
        f"> {shlex.quote(str(run_dir / 'pw.out'))} "
        f"2> {shlex.quote(str(run_dir / 'pw.err'))}\n"
    )
    (run_dir / "command.txt").write_text(command)

    env_file = run_dir / "run_env.sh"
    env_file.write_text(
        shell_env_line("RUN_DIR", str(run_dir))
        + shell_env_line("PWX_RESOLVED", str(pwx))
        + shell_env_line("PW_INPUT", str(copied_input))
        + shell_env_line("PW_OUT", str(run_dir / "pw.out"))
        + shell_env_line("PW_ERR", str(run_dir / "pw.err"))
        + shell_env_line("METADATA_JSON", str(run_dir / "metadata.json"))
        + shell_env_line("PARSED_JSON", str(run_dir / "parsed.json"))
    )

    print(env_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
