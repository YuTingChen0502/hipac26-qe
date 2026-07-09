#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import time
from pathlib import Path

from qe_smoke_prepare import (
    parse_atomic_species,
    patch_outdir,
    sha256_file,
    shell_env_line,
)


def patch_electron_maxstep(input_path: Path, maxstep: int) -> None:
    text = input_path.read_text()

    if re.search(r"(?im)^\s*electron_maxstep\s*=", text):
        text = re.sub(
            r"(?im)^(\s*electron_maxstep\s*=\s*)[^,\n/]+(,?)",
            rf"\g<1>{maxstep}\2",
            text,
        )
        input_path.write_text(text)
        return

    electrons_block = re.search(
        r"(?ims)^&ELECTRONS\b(?P<body>.*?)(?P<end>^\s*/\s*$)",
        text,
    )
    if electrons_block:
        insert_at = electrons_block.start("end")
        text = text[:insert_at] + f"  electron_maxstep = {maxstep},\n" + text[insert_at:]
        input_path.write_text(text)
        return

    atomic_species = re.search(r"(?im)^ATOMIC_SPECIES\s*$", text)
    block = f"&ELECTRONS\n  electron_maxstep = {maxstep},\n/\n\n"
    if atomic_species:
        text = text[:atomic_species.start()] + block + text[atomic_species.start():]
    else:
        text = text.rstrip() + "\n\n" + block
    input_path.write_text(text)


def main() -> int:
    ap = argparse.ArgumentParser(description="Prepare a controlled QE baseperf/calibration run directory.")
    ap.add_argument("--workroot", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--buildroot", required=True)
    ap.add_argument("--caseroot", required=True)
    ap.add_argument("--pseudoroot", required=True)
    ap.add_argument("--runroot", required=True)
    ap.add_argument("--gate-id", default="BUILD-BASEPERF-T001")
    ap.add_argument("--run-type", default="calibration")
    ap.add_argument("--input-type", default="TypeA_manyk")
    ap.add_argument("--build-id", default="G1-qe75-nvhpc259-gpu-base")
    ap.add_argument("--case-name", default="typeA-au111-manyk")
    ap.add_argument("--build-hash", required=True)
    ap.add_argument("--pwx", default="")
    ap.add_argument("--slurm-job-id", default="")
    ap.add_argument("--partition", default="dev")
    ap.add_argument("--nodes", default="1")
    ap.add_argument("--ntasks", default="1")
    ap.add_argument("--ntasks-per-node", default="1")
    ap.add_argument("--cpus-per-task", default="12")
    ap.add_argument("--gres", default="gpu:1")
    ap.add_argument("--time-limit", default="00:30:00")
    ap.add_argument("--electron-maxstep", type=int, default=2)
    ap.add_argument("--runtime-group-id", default="typeA_calib_g1_dev_1gpu_np1")
    ap.add_argument("--launcher", default="mpirun_np1_bind_to_none")
    ap.add_argument("--sbatch-source", default="")
    args = ap.parse_args()

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
    run_id = (
        f"{args.gate_id}__{args.run_type}__{args.build_id}__"
        f"{args.case_name}__emax{args.electron_maxstep}__job{job_id}__{timestamp}"
    )
    run_dir = runroot / args.gate_id / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "outdir").mkdir(parents=True, exist_ok=True)

    copied_input = run_dir / "pw.in"
    copied_input.write_text(src_input.read_text())
    patch_outdir(copied_input)
    patch_electron_maxstep(copied_input, args.electron_maxstep)

    sbatch_source = Path(args.sbatch_source) if args.sbatch_source else repo / "scripts/run/baseperf_typeA_g1_calib.sbatch"
    if sbatch_source.exists():
        (run_dir / "resolved_sbatch.sh").write_text(sbatch_source.read_text())

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
        "input_type": args.input_type,
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
        "opal_prefix": os.environ.get("OPAL_PREFIX", ""),
        "launcher": args.launcher,
        "electron_maxstep_override": args.electron_maxstep,
        "runtime_group_id": args.runtime_group_id,
        "eligible_for_timing_comparison": False,
        "exclusion_reason": "calibration run; benchmark_valid=false",
        "failure_class": None,
        "notes": "TypeA calibration only; not benchmark; not performance claim.",
    }

    metadata_json = run_dir / "metadata.json"
    parsed_json = run_dir / "parsed.json"
    pw_out = run_dir / "pw.out"
    pw_err = run_dir / "pw.err"

    metadata_json.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")

    command = (
        f"export OMP_NUM_THREADS={args.cpus_per_task}\n"
        f"cd {shlex.quote(str(run_dir))}\n"
        f"mpirun --bind-to none -np 1 {shlex.quote(str(pwx))} "
        f"-in {shlex.quote(str(copied_input))} "
        f"> {shlex.quote(str(pw_out))} "
        f"2> {shlex.quote(str(pw_err))}\n"
    )
    (run_dir / "command.txt").write_text(command)

    env_file = run_dir / "run_env.sh"
    env_file.write_text(
        shell_env_line("OPAL_PREFIX", os.environ.get("OPAL_PREFIX", ""))
        + shell_env_line("RUN_DIR", str(run_dir))
        + shell_env_line("PWX_RESOLVED", str(pwx))
        + shell_env_line("PW_INPUT", str(copied_input))
        + shell_env_line("PW_OUT", str(pw_out))
        + shell_env_line("PW_ERR", str(pw_err))
        + shell_env_line("METADATA_JSON", str(metadata_json))
        + shell_env_line("PARSED_JSON", str(parsed_json))
    )

    print(env_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
