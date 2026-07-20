#!/usr/bin/env python3
"""Strict QE SCF-convergence classification.

Normal termination and QE's textual convergence claim are kept separate from
numerical satisfaction of conv_thr.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional


_QE_FLOAT_RE = (
    r"[-+]?"
    r"(?:\d+(?:\.\d*)?|\.\d+)"
    r"(?:[EeDd][-+]?\d+)?"
)


def _fortran_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None

    cleaned = value.strip().strip("'\"").replace("D", "E").replace("d", "e")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _remove_fortran_comments(text: str) -> str:
    return "\n".join(line.split("!", 1)[0] for line in text.splitlines())


def _find_assignment(text: str, name: str) -> Optional[str]:
    clean = _remove_fortran_comments(text)
    match = re.search(
        rf"(?im)\b{re.escape(name)}\s*=\s*([^,\n/]+)",
        clean,
    )
    return match.group(1).strip() if match else None


def parse_qe_input_controls(input_path: Optional[Path]) -> dict[str, Any]:
    controls: dict[str, Any] = {
        "conv_thr_ry": None,
        "electron_maxstep": 100,
        "scf_must_converge": True,
    }

    if input_path is None or not input_path.exists():
        return controls

    text = input_path.read_text(encoding="utf-8", errors="replace")

    conv_thr = _fortran_float(_find_assignment(text, "conv_thr"))
    if conv_thr is not None:
        controls["conv_thr_ry"] = conv_thr

    maxstep_raw = _find_assignment(text, "electron_maxstep")
    if maxstep_raw is not None:
        try:
            controls["electron_maxstep"] = int(maxstep_raw.strip())
        except ValueError:
            controls["electron_maxstep"] = None

    must_converge_raw = _find_assignment(text, "scf_must_converge")
    if must_converge_raw is not None:
        normalized = must_converge_raw.strip().lower().strip(".")
        if normalized == "true":
            controls["scf_must_converge"] = True
        elif normalized == "false":
            controls["scf_must_converge"] = False
        else:
            controls["scf_must_converge"] = None

    return controls


def classify_qe_convergence(
    output_text: str,
    input_path: Optional[Path] = None,
) -> dict[str, Any]:
    controls = parse_qe_input_controls(input_path)

    status_pattern = re.compile(
        r"convergence\s+"
        r"(has\s+been\s+achieved\s+in|NOT\s+achieved\s+after)"
        r"\s+(\d+)\s+iterations",
        re.IGNORECASE,
    )
    status_events = status_pattern.findall(output_text)

    output_claimed_converged = False
    output_reported_not_converged = False
    last_scf_cycle_iterations: Optional[int] = None

    if status_events:
        status_phrase, iteration_text = status_events[-1]
        last_scf_cycle_iterations = int(iteration_text)
        output_claimed_converged = status_phrase.lower().startswith("has")
        output_reported_not_converged = not output_claimed_converged
    else:
        output_claimed_converged = bool(
            re.search(
                r"convergence\s+has\s+been\s+achieved",
                output_text,
                re.IGNORECASE,
            )
        )
        output_reported_not_converged = bool(
            re.search(
                r"convergence\s+NOT\s+achieved|not\s+converged",
                output_text,
                re.IGNORECASE,
            )
        )

    accuracy_matches = re.findall(
        rf"estimated\s+scf\s+accuracy\s*<\s*({_QE_FLOAT_RE})\s+Ry",
        output_text,
        re.IGNORECASE,
    )
    final_accuracy = (
        _fortran_float(accuracy_matches[-1])
        if accuracy_matches
        else None
    )

    total_iteration_lines = len(
        re.findall(
            r"^\s*iteration\s+#",
            output_text,
            re.MULTILINE | re.IGNORECASE,
        )
    )

    conv_thr = controls["conv_thr_ry"]
    electron_maxstep = controls["electron_maxstep"]
    scf_must_converge = controls["scf_must_converge"]

    numerically_converged: Optional[bool] = None
    if final_accuracy is not None and conv_thr is not None:
        numerically_converged = final_accuracy <= conv_thr

    cycle_iterations = (
        last_scf_cycle_iterations
        if last_scf_cycle_iterations is not None
        else (total_iteration_lines or None)
    )

    reached_electron_maxstep = bool(
        cycle_iterations is not None
        and electron_maxstep is not None
        and cycle_iterations >= electron_maxstep
    )

    strict_scf_converged = bool(
        output_claimed_converged
        and not output_reported_not_converged
        and numerically_converged is True
    )

    forced_accept = bool(
        output_claimed_converged
        and scf_must_converge is False
        and reached_electron_maxstep
        and numerically_converged is False
    )

    if strict_scf_converged:
        convergence_status = "strict_converged"
    elif forced_accept:
        convergence_status = "maxstep_forced_accept"
    elif output_reported_not_converged or numerically_converged is False:
        convergence_status = "not_converged"
    elif output_claimed_converged:
        convergence_status = "claimed_converged_unverified"
    else:
        convergence_status = "unknown"

    return {
        "convergence_status": convergence_status,
        "strict_scf_converged": strict_scf_converged,
        "forced_accept": forced_accept,
        "reached_electron_maxstep": reached_electron_maxstep,
        "output_claimed_converged": output_claimed_converged,
        "output_reported_not_converged": output_reported_not_converged,
        "numerically_converged": numerically_converged,
        "final_scf_accuracy_ry": final_accuracy,
        "conv_thr_ry": conv_thr,
        "electron_maxstep": electron_maxstep,
        "scf_must_converge": scf_must_converge,
        "last_scf_cycle_iterations": last_scf_cycle_iterations,
    }
