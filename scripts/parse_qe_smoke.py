#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Optional


def parse_qe_time_to_sec(s: str) -> Optional[float]:
    s = s.strip()
    # QE examples are inconsistent; support: 1d2h3m4.5s, 2h3m4.5s, 3m4.5s, 4.5s
    pat = re.compile(
        r"(?:(?P<d>\d+)d)?\s*"
        r"(?:(?P<h>\d+)h)?\s*"
        r"(?:(?P<m>\d+)m)?\s*"
        r"(?:(?P<s>\d+(?:\.\d+)?)s)?"
    )
    m = pat.fullmatch(s.replace(" ", ""))
    if not m:
        return None
    d = int(m.group("d") or 0)
    h = int(m.group("h") or 0)
    mi = int(m.group("m") or 0)
    sec = float(m.group("s") or 0.0)
    return d * 86400 + h * 3600 + mi * 60 + sec


def classify_failure(text: str, pw_err: str = "") -> Optional[str]:
    both = f"{text}\n{pw_err}".lower()

    if "error in routine" in both:
        if "pseudo" in both and ("not found" in both or "file" in both):
            return "input_pseudo_path_failure"
        if "namelist" in both or "card" in both:
            return "input_syntax_failure"
        if "cuda" in both or "gpu" in both:
            return "gpu_runtime_failure"
        if "mpi" in both or "pmix" in both:
            return "mpi_runtime_failure"
        return "qe_fatal_runtime_failure"

    if "pseudo" in both and ("not found" in both or "no such file" in both):
        return "input_pseudo_path_failure"
    if "cuda" in both or "gpu error" in both:
        return "gpu_runtime_failure"
    if "no such file" in both:
        return "path_failure"
    if "permission denied" in both:
        return "permission_failure"
    if "segmentation fault" in both or "sigsegv" in both:
        return "segmentation_fault"
    return None


def parse_qe_output(pw_out: Path, pw_err: Optional[Path] = None) -> dict[str, Any]:
    if not pw_out.exists():
        return {
            "parser_status": "missing",
            "result_status": "incomplete",
            "qe_started": False,
            "qe_normal_end": False,
            "fatal_error_detected": False,
            "failure_class": "output_missing",
            "benchmark_valid": False,
            "performance_claim_allowed": False,
            "optimization_claim_allowed": False,
        }

    text = pw_out.read_text(errors="replace")
    err_text = pw_err.read_text(errors="replace") if pw_err and pw_err.exists() else ""

    qe_started = bool(re.search(r"\bProgram\s+PWSCF\b|\bPWSCF\b", text))
    qe_normal_end = "JOB DONE" in text
    fatal_error_detected = bool(
        re.search(r"Error in routine|%%%%%%%%%%%%|stopping\s+.*error", text, re.I)
        or re.search(r"Error in routine|segmentation fault|SIGSEGV|CUDA|No such file", err_text, re.I)
    )
    failure_class = classify_failure(text, err_text)

    energies = re.findall(r"!\s+total energy\s+=\s+([-+0-9.Ee]+)\s+Ry", text)
    total_energy_ry = float(energies[-1]) if energies else None

    scf_iterations = len(re.findall(r"^\s*iteration\s+#", text, flags=re.M))
    if scf_iterations == 0:
        scf_iterations = len(re.findall(r"estimated\s+scf\s+accuracy", text, flags=re.I))

    if re.search(r"convergence\s+has\s+been\s+achieved", text, re.I):
        convergence_status = "converged"
    elif re.search(r"convergence\s+NOT\s+achieved|not\s+converged", text, re.I):
        convergence_status = "not_converged"
    else:
        convergence_status = "unknown"

    number_of_atoms = None
    m = re.search(r"number\s+of\s+atoms/cell\s+=\s+(\d+)", text, re.I)
    if m:
        number_of_atoms = int(m.group(1))

    number_of_k_points = None
    m = re.search(r"number\s+of\s+k\s+points\s*=\s*(\d+)", text, re.I)
    if m:
        number_of_k_points = int(m.group(1))

    qe_wall_time_sec = None
    qe_cpu_time_sec = None
    # Example: PWSCF        :      0.15s CPU      0.18s WALL
    m = re.search(r"PWSCF\s*:\s*(.*?)\s+CPU\s+(.*?)\s+WALL", text)
    if m:
        qe_cpu_time_sec = parse_qe_time_to_sec(m.group(1))
        qe_wall_time_sec = parse_qe_time_to_sec(m.group(2))

    smoke_pass = bool(qe_started and qe_normal_end and not fatal_error_detected)

    if smoke_pass:
        result_status = "pass"
        parser_status = "pass"
    elif qe_started:
        result_status = "fail" if fatal_error_detected else "partial"
        parser_status = "partial"
    else:
        result_status = "incomplete"
        parser_status = "partial" if text.strip() else "missing"

    if failure_class is None and not smoke_pass:
        if not qe_started:
            failure_class = "qe_not_started"
        elif not qe_normal_end:
            failure_class = "qe_no_normal_end"
        elif fatal_error_detected:
            failure_class = "qe_fatal_runtime_failure"

    return {
        "parser_status": parser_status,
        "result_status": result_status,
        "qe_started": qe_started,
        "qe_normal_end": qe_normal_end,
        "fatal_error_detected": fatal_error_detected,
        "smoke_pass": smoke_pass,
        "failure_class": failure_class,
        "convergence_status": convergence_status,
        "total_energy_ry": total_energy_ry,
        "scf_iterations": scf_iterations,
        "number_of_atoms": number_of_atoms,
        "number_of_k_points": number_of_k_points,
        "qe_wall_time_sec": qe_wall_time_sec,
        "qe_cpu_time_sec": qe_cpu_time_sec,
        "benchmark_valid": False,
        "performance_claim_allowed": False,
        "optimization_claim_allowed": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Parse QE pw.x smoke output into parsed.json.")
    ap.add_argument("--pw-out", required=True, type=Path)
    ap.add_argument("--pw-err", type=Path)
    ap.add_argument("--metadata", type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    result = parse_qe_output(args.pw_out, args.pw_err)

    if args.metadata and args.metadata.exists():
        try:
            meta = json.loads(args.metadata.read_text())
            result["gate_id"] = meta.get("gate_id")
            result["run_id"] = meta.get("run_id")
            result["candidate_id"] = meta.get("candidate_id")
            result["case_name"] = meta.get("case_name")
        except Exception as exc:
            result["metadata_parse_warning"] = str(exc)

    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
