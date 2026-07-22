#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


RESULT_FIELDS = [
    "order_index",
    "trial_id",
    "case_name",
    "sweep_name",
    "parameter_family",
    "candidate",
    "candidate_role",
    "repeat_index",
    "requested_mpi_ranks",
    "requested_ranks_per_node",
    "requested_nk",
    "requested_openmp_threads",
    "expected_rank_layout",
    "actual_rank_layout",
    "active_nodes",
    "mapping_count",
    "actual_npool",
    "actual_proc_per_pool",
    "actual_diag_mode",
    "number_of_k_points",
    "qe_exit_code",
    "parser_status",
    "result_status",
    "convergence_status",
    "strict_scf_converged",
    "scf_iterations",
    "expected_scf_iterations",
    "numerical_comparable",
    "numerical_reasons",
    "energy_tolerance_ry",
    "total_energy_ry",
    "expected_energy_ry",
    "energy_abs_error_ry",
    "qe_wall_time_sec",
    "qe_cpu_time_sec",
    "normal_end",
    "fatal_error",
    "execution_pass",
    "configuration_pass",
    "comparability_pass",
    "failure_reasons",
    "run_directory",
]


def read_int(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def parse_actual_parallelization(text: str, requested_nk: int) -> tuple[int | None, int | None, str]:
    pool_match = re.search(
        r"K-points division:\s*npool\s*=\s*(\d+)",
        text,
        flags=re.IGNORECASE,
    )
    actual_npool = int(pool_match.group(1)) if pool_match else (1 if requested_nk == 1 else None)

    proc_match = re.search(
        r"R\s*&\s*G space division:\s*proc/nbgrp/npool/nimage\s*=\s*(\d+)",
        text,
        flags=re.IGNORECASE,
    )
    actual_proc = int(proc_match.group(1)) if proc_match else None

    if re.search(r"a serial algorithm will be used", text, flags=re.IGNORECASE):
        diag_mode = "serial"
    elif re.search(r"parallel.*diagonal", text, flags=re.IGNORECASE):
        diag_mode = "parallel"
    else:
        diag_mode = "unknown"

    return actual_npool, actual_proc, diag_mode


def parse_rank_layout(mapping_dir: Path) -> tuple[int, int, str]:
    records: list[tuple[int, str]] = []

    for path in mapping_dir.glob("rank-*.txt"):
        rank_match = re.search(r"rank-(\d+)\.txt$", path.name)
        if not rank_match:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        host_match = re.search(r"\bhost=([^\s]+)", text)
        if host_match:
            records.append((int(rank_match.group(1)), host_match.group(1)))

    records.sort()
    host_counts: Counter[str] = Counter(host for _, host in records)
    counts = sorted(host_counts.values(), reverse=True)
    return len(records), len(host_counts), ",".join(str(value) for value in counts)


def bool_text(value: Any) -> str:
    return "true" if value is True else "false" if value is False else ""


def validate_trial(run_dir: Path) -> dict[str, Any]:
    metadata = read_json(run_dir / "run-metadata.json")
    parsed = read_json(run_dir / "parsed.json")
    qe_exit = read_int(run_dir / "qe-exit-code.txt")
    qe_text = (run_dir / "qe.out").read_text(encoding="utf-8", errors="replace") if (run_dir / "qe.out").exists() else ""

    requested_mpi = int(metadata.get("mpi_ranks", 0))
    requested_rpn = int(metadata.get("ranks_per_node", 0))
    requested_nk = int(metadata.get("k_point_pools", 0))
    expected_scf = int(metadata.get("expected_scf_iterations", 0))
    expected_energy = float(metadata.get("expected_energy_ry", "nan"))
    expected_k_points = int(metadata.get("expected_k_points", 0))
    expected_layout = str(metadata.get("expected_rank_layout", ""))

    actual_npool, actual_proc, diag_mode = parse_actual_parallelization(qe_text, requested_nk)
    mapping_count, active_nodes, actual_layout = parse_rank_layout(run_dir / "rank-mapping")

    energy = parsed.get("total_energy_ry")
    try:
        energy_error = abs(float(energy) - expected_energy)
    except Exception:
        energy_error = math.inf

    execution_reasons: list[str] = []
    if qe_exit != 0:
        execution_reasons.append(f"qe_exit={qe_exit}")
    if parsed.get("parser_status") != "pass":
        execution_reasons.append(f"parser_status={parsed.get('parser_status')}")
    if parsed.get("result_status") != "pass":
        execution_reasons.append(f"result_status={parsed.get('result_status')}")
    if parsed.get("qe_normal_end") is not True:
        execution_reasons.append("no_normal_end")
    if parsed.get("fatal_error_detected") is not False:
        execution_reasons.append("fatal_error")
    if parsed.get("strict_scf_converged") is not True:
        execution_reasons.append("not_strict_converged")
    energy_tolerance = float(
        os.environ.get("NUMERICAL_ENERGY_TOLERANCE_RY", "1e-8")
    )
    if not math.isfinite(energy_tolerance) or energy_tolerance <= 0:
        raise ValueError(
            "NUMERICAL_ENERGY_TOLERANCE_RY must be a positive finite value"
        )

    numerical_reasons = []
    if not math.isfinite(energy_error) or energy_error > energy_tolerance:
        numerical_reasons.append(
            f"energy_error={energy_error}>tolerance={energy_tolerance}"
        )

    configuration_reasons: list[str] = []
    if requested_mpi < 1 or requested_nk < 1 or requested_mpi % requested_nk != 0:
        configuration_reasons.append("invalid_requested_mpi_nk")
    if actual_npool != requested_nk:
        configuration_reasons.append(f"actual_npool={actual_npool}")
    expected_proc = requested_mpi // requested_nk if requested_nk else None
    if actual_proc != expected_proc:
        configuration_reasons.append(f"actual_proc_per_pool={actual_proc}")
    if mapping_count != requested_mpi:
        configuration_reasons.append(f"mapping_count={mapping_count}")
    if expected_layout and actual_layout != expected_layout:
        configuration_reasons.append(f"rank_layout={actual_layout}")
    if "25a-hgpn144" in str(metadata.get("slurm_nodelist", "")):
        configuration_reasons.append("bad_node_in_slurm_nodelist")
    if "25a-hgpn144" in qe_text:
        configuration_reasons.append("bad_node_marker_in_qe_output")

    comparability_reasons: list[str] = []
    if parsed.get("scf_iterations") != expected_scf:
        comparability_reasons.append(f"scf_iterations={parsed.get('scf_iterations')}")
    if parsed.get("number_of_k_points") != expected_k_points:
        comparability_reasons.append(f"k_points={parsed.get('number_of_k_points')}")

    execution_pass = not execution_reasons
    configuration_pass = not configuration_reasons
    comparability_pass = execution_pass and configuration_pass and not comparability_reasons

    all_reasons = execution_reasons + configuration_reasons + comparability_reasons

    return {
        "order_index": metadata.get("order_index"),
        "trial_id": metadata.get("trial_id"),
        "case_name": metadata.get("case_name"),
        "sweep_name": metadata.get("sweep_name"),
        "parameter_family": metadata.get("parameter_family"),
        "candidate": metadata.get("candidate"),
        "candidate_role": metadata.get("candidate_role"),
        "repeat_index": metadata.get("repeat_index"),
        "requested_mpi_ranks": requested_mpi,
        "requested_ranks_per_node": requested_rpn,
        "requested_nk": requested_nk,
        "requested_openmp_threads": metadata.get("openmp_threads"),
        "expected_rank_layout": expected_layout,
        "actual_rank_layout": actual_layout,
        "active_nodes": active_nodes,
        "mapping_count": mapping_count,
        "actual_npool": actual_npool,
        "actual_proc_per_pool": actual_proc,
        "actual_diag_mode": diag_mode,
        "number_of_k_points": parsed.get("number_of_k_points"),
        "qe_exit_code": qe_exit,
        "parser_status": parsed.get("parser_status"),
        "result_status": parsed.get("result_status"),
        "convergence_status": parsed.get("convergence_status"),
        "strict_scf_converged": bool_text(parsed.get("strict_scf_converged")),
        "scf_iterations": parsed.get("scf_iterations"),
        "expected_scf_iterations": expected_scf,
        "numerical_comparable": bool_text(not numerical_reasons),
        "numerical_reasons": ";".join(numerical_reasons),
        "energy_tolerance_ry": energy_tolerance,
        "total_energy_ry": energy,
        "expected_energy_ry": expected_energy,
        "energy_abs_error_ry": energy_error if math.isfinite(energy_error) else "",
        "qe_wall_time_sec": parsed.get("qe_wall_time_sec"),
        "qe_cpu_time_sec": parsed.get("qe_cpu_time_sec"),
        "normal_end": bool_text(parsed.get("qe_normal_end")),
        "fatal_error": bool_text(parsed.get("fatal_error_detected")),
        "execution_pass": bool_text(execution_pass),
        "configuration_pass": bool_text(configuration_pass),
        "comparability_pass": bool_text(comparability_pass),
        "failure_reasons": ";".join(all_reasons),
        "run_directory": str(run_dir),
    }


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["candidate"])].append(row)

    baseline_candidates = [
        candidate
        for candidate, candidate_rows in grouped.items()
        if any(row["candidate_role"] == "baseline" for row in candidate_rows)
    ]
    baseline_median: float | None = None
    if len(baseline_candidates) == 1:
        baseline_values = [
            float(row["qe_wall_time_sec"])
            for row in grouped[baseline_candidates[0]]
            if row["comparability_pass"] == "true" and row["qe_wall_time_sec"] is not None
        ]
        if baseline_values:
            baseline_median = statistics.median(baseline_values)

    summaries: list[dict[str, Any]] = []
    for candidate, candidate_rows in sorted(grouped.items()):
        valid = [
            float(row["qe_wall_time_sec"])
            for row in candidate_rows
            if row["comparability_pass"] == "true" and row["qe_wall_time_sec"] is not None
        ]
        median = statistics.median(valid) if valid else None
        mean = statistics.fmean(valid) if valid else None
        minimum = min(valid) if valid else None
        maximum = max(valid) if valid else None
        stdev = statistics.stdev(valid) if len(valid) >= 2 else 0.0 if len(valid) == 1 else None
        cv = stdev / mean if stdev is not None and mean not in (None, 0.0) else None
        ratio = baseline_median / median if baseline_median and median else None

        summaries.append(
            {
                "candidate": candidate,
                "candidate_role": candidate_rows[0]["candidate_role"],
                "requested_mpi_ranks": candidate_rows[0]["requested_mpi_ranks"],
                "requested_nk": candidate_rows[0]["requested_nk"],
                "requested_openmp_threads": candidate_rows[0]["requested_openmp_threads"],
                "expected_rank_layout": candidate_rows[0]["expected_rank_layout"],
                "total_trials": len(candidate_rows),
                "comparable_trials": len(valid),
                "median_wall_sec": median,
                "mean_wall_sec": mean,
                "min_wall_sec": minimum,
                "max_wall_sec": maximum,
                "stdev_wall_sec": stdev,
                "cv": cv,
                "single_allocation_median_ratio_vs_baseline": ratio,
            }
        )
    return summaries


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect and validate controlled G4X sweep trials.")
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    run_dirs = sorted(
        (path for path in (root / "runs").iterdir() if path.is_dir()),
        key=lambda path: path.name,
    )
    rows = [validate_trial(run_dir) for run_dir in run_dirs]
    rows.sort(key=lambda row: int(row["order_index"] or 0))

    write_csv(root / "results.csv", RESULT_FIELDS, rows)

    summary_rows = summarize(rows)
    summary_fields = [
        "candidate",
        "candidate_role",
        "requested_mpi_ranks",
        "requested_nk",
        "requested_openmp_threads",
        "expected_rank_layout",
        "total_trials",
        "comparable_trials",
        "median_wall_sec",
        "mean_wall_sec",
        "min_wall_sec",
        "max_wall_sec",
        "stdev_wall_sec",
        "cv",
        "single_allocation_median_ratio_vs_baseline",
    ]
    write_csv(root / "candidate-summary.csv", summary_fields, summary_rows)

    failed = [row for row in rows if row["comparability_pass"] != "true"]
    summary = {
        "root": str(root),
        "trial_count": len(rows),
        "comparable_count": len(rows) - len(failed),
        "failed_count": len(failed),
        "failed_trials": [
            {
                "trial_id": row["trial_id"],
                "candidate": row["candidate"],
                "failure_reasons": row["failure_reasons"],
            }
            for row in failed
        ],
        "claim_scope": (
            "Controlled same-allocation screening. Ratios are not formal speedup claims "
            "until baseline and winner receive the planned confirmation repeats."
        ),
    }
    (root / "collection-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"SWEEP_ROOT={root}")
    print(f"TRIAL_COUNT={len(rows)}")
    print(f"COMPARABLE_COUNT={len(rows) - len(failed)}")
    print(f"FAILED_COUNT={len(failed)}")
    print(f"RESULTS_CSV={root / 'results.csv'}")
    print(f"CANDIDATE_SUMMARY_CSV={root / 'candidate-summary.csv'}")

    return 0 if rows and not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
