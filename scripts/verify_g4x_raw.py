#!/usr/bin/env python3
# verifier_schema_version=2; supports=b1-e001

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


TYPE_A_INPUT_SHA = (
    "7c9354016502431300025747b73aebe9ae2b3a6766c811fe0bf0e8a8066b03d2"
)

B1_INPUT_SHA = (
    "3efd3830a380a185e76124e8d7beba2111ea6c1333d8e946bbac199c1c06a340"
)


EXPERIMENTS: dict[str, dict[str, Any]] = {
    "e002": {
        "expected_k_points": 7,
        "expected_iterations": 15,
        "expected_input_sha256": TYPE_A_INPUT_SHA,
        "default_energy_tolerance": 1e-6,
        "candidates": {
            "r14": {
                "count": 3,
                "ranks": 14,
                "layout": [7, 7],
                "active_gpus": 14,
            },
            "r7": {
                "count": 3,
                "ranks": 7,
                "layout": [7],
                "active_gpus": 7,
            },
        },
    },
    "e003": {
        "expected_k_points": 7,
        "expected_iterations": 15,
        "expected_input_sha256": TYPE_A_INPUT_SHA,
        "default_energy_tolerance": 1e-6,
        "candidates": {
            "map7x7": {
                "count": 3,
                "ranks": 14,
                "layout": [7, 7],
                "active_gpus": 14,
            },
            "map8x6": {
                "count": 3,
                "ranks": 14,
                "layout": [6, 8],
                "active_gpus": 14,
            },
        },
    },
    "e004": {
        "expected_k_points": 7,
        "expected_iterations": 15,
        "expected_input_sha256": TYPE_A_INPUT_SHA,
        "default_energy_tolerance": 1e-6,
        "candidates": {
            "map7x7": {
                "count": 5,
                "ranks": 14,
                "layout": [7, 7],
                "active_gpus": 14,
            },
            "map8x6": {
                "count": 5,
                "ranks": 14,
                "layout": [6, 8],
                "active_gpus": 14,
            },
        },
    },
    "b1-e001": {
        "expected_k_points": 1,
        "expected_iterations": 20,
        "expected_input_sha256": B1_INPUT_SHA,
        "default_energy_tolerance": 1e-7,
        "candidates": {
            "r4": {
                "count": 3,
                "ranks": 4,
                "layout": [4],
                "active_gpus": 4,
            },
            "r8": {
                "count": 3,
                "ranks": 8,
                "layout": [8],
                "active_gpus": 8,
            },
            "r16": {
                "count": 3,
                "ranks": 16,
                "layout": [8, 8],
                "active_gpus": 16,
            },
        },
    },
    "b1-e002": {
        "expected_k_points": 1,
        "expected_iterations": 20,
        "expected_input_sha256": B1_INPUT_SHA,
        "default_energy_tolerance": 1e-7,
        "candidates": {
            "r6": {
                "count": 5,
                "ranks": 6,
                "layout": [6],
                "active_gpus": 6,
            },
            "r8": {
                "count": 5,
                "ranks": 8,
                "layout": [8],
                "active_gpus": 8,
            },
        },
    },

    "b1-e003": {
        "expected_k_points": 1,
        "expected_iterations": 20,
        "expected_input_sha256": B1_INPUT_SHA,
        "default_energy_tolerance": 1e-7,
        "candidates": {
            "r6": {
                "count": 5,
                "ranks": 6,
                "layout": [6],
                "active_gpus": 6,
            },
            "r8": {
                "count": 5,
                "ranks": 8,
                "layout": [8],
                "active_gpus": 8,
            },
        },
    },

}


FATAL_RE = re.compile(
    r"Error in routine|MPI_ABORT|Segmentation fault|"
    r"CUDA error|out of memory|\bKilled\b",
    flags=re.IGNORECASE,
)


def read_metadata(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}

    if not path.is_file():
        return result

    for line in path.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip()

    return result


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None

    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def last_float(pattern: str, text: str) -> float | None:
    values = re.findall(pattern, text, flags=re.MULTILINE)
    return float(values[-1]) if values else None


def last_int(pattern: str, text: str) -> int | None:
    values = re.findall(pattern, text, flags=re.MULTILINE)
    return int(values[-1]) if values else None


def parse_duration_token(token: str) -> float | None:
    compact = re.sub(r"\s+", "", token)

    match = re.fullmatch(
        r"(?:(?P<days>[0-9]+)d)?"
        r"(?:(?P<hours>[0-9]+)h)?"
        r"(?:(?P<minutes>[0-9]+)m)?"
        r"(?P<seconds>[0-9]+(?:\.[0-9]+)?)s",
        compact,
    )

    if match is None:
        return None

    return (
        int(match.group("days") or 0) * 86400.0
        + int(match.group("hours") or 0) * 3600.0
        + int(match.group("minutes") or 0) * 60.0
        + float(match.group("seconds"))
    )


def pwscf_wall_seconds(text: str) -> float | None:
    values: list[float] = []

    for line in text.splitlines():
        if "PWSCF" not in line or "WALL" not in line:
            continue

        match = re.search(
            r"([0-9dhms.]+)\s+WALL",
            line,
        )

        if match is None:
            continue

        parsed = parse_duration_token(match.group(1))

        if parsed is not None:
            values.append(parsed)

    return values[-1] if values else None


def mapping_layout(path: Path) -> tuple[list[int], int]:
    hosts: Counter[str] = Counter()

    if not path.is_dir():
        return [], 0

    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue

        text = item.read_text(
            encoding="utf-8",
            errors="replace",
        )

        match = re.search(
            r"\bhost=([^\s]+)",
            text,
        )

        if match is not None:
            hosts[match.group(1)] += 1

    return sorted(hosts.values()), sum(hosts.values())


def detect_candidate(
    trial: Path,
    metadata: dict[str, str],
    candidates: dict[str, Any],
) -> str:
    candidate = metadata.get("candidate", "")

    if candidate in candidates:
        return candidate

    for name in candidates:
        if re.search(
            rf"(?:^|-){re.escape(name)}(?:-|$)",
            trial.name,
        ):
            return name

    return ""


def derived_summary(
    experiment: str,
    medians: dict[str, float],
) -> list[str]:
    lines: list[str] = []

    if (
        experiment == "e002"
        and {"r14", "r7"} <= medians.keys()
    ):
        ratio = medians["r14"] / medians["r7"]

        lines.extend([
            f"r14_over_r7_median_ratio={ratio:.9f}",
            "r14_latency_improvement_percent="
            f"{(1.0 - ratio) * 100.0:.3f}",
        ])

    elif (
        experiment in {"e003", "e004"}
        and {"map8x6", "map7x7"} <= medians.keys()
    ):
        ratio = (
            medians["map8x6"]
            / medians["map7x7"]
        )

        lines.extend([
            "map8x6_over_map7x7_median_ratio="
            f"{ratio:.9f}",
            "map8x6_latency_improvement_percent="
            f"{(1.0 - ratio) * 100.0:.3f}",
        ])

    elif (
        experiment == "b1-e001"
        and {"r4", "r8", "r16"} <= medians.keys()
    ):
        r8_r4 = medians["r8"] / medians["r4"]
        r16_r8 = medians["r16"] / medians["r8"]

        lines.extend([
            f"r8_over_r4_median_ratio={r8_r4:.9f}",
            "r8_vs_r4_latency_reduction_percent="
            f"{(1.0 - r8_r4) * 100.0:.3f}",
            f"r16_over_r8_median_ratio={r16_r8:.9f}",
            "r8_vs_r16_latency_reduction_percent="
            f"{(1.0 - 1.0 / r16_r8) * 100.0:.3f}",
        ])

    elif (
        experiment == "b1-e002"
        and {"r6", "r8"} <= medians.keys()
    ):
        ratio = medians["r8"] / medians["r6"]

        lines.extend([
            f"r8_over_r6_median_ratio={ratio:.9f}",
            "r8_vs_r6_latency_reduction_percent="
            f"{(1.0 - ratio) * 100.0:.3f}",
        ])

    elif (
        experiment == "b1-e003"
        and {"r6", "r8"} <= medians.keys()
    ):
        ratio = medians["r8"] / medians["r6"]

        lines.extend([
            f"r8_over_r6_median_ratio={ratio:.9f}",
            "r8_vs_r6_latency_reduction_percent="
            f"{(1.0 - ratio) * 100.0:.3f}",
        ])

    return lines


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--root",
        required=True,
    )

    parser.add_argument(
        "--experiment",
        choices=tuple(EXPERIMENTS),
        required=True,
    )

    parser.add_argument(
        "--output-dir",
        required=True,
    )

    parser.add_argument(
        "--energy-tolerance",
        type=float,
    )

    args = parser.parse_args()

    root = Path(args.root).resolve()
    output = Path(args.output_dir).resolve()
    experiment = EXPERIMENTS[args.experiment]

    candidates: dict[str, dict[str, Any]] = (
        experiment["candidates"]
    )

    tolerance = (
        args.energy_tolerance
        if args.energy_tolerance is not None
        else float(
            experiment["default_energy_tolerance"]
        )
    )

    runs_root = root / "runs"

    if not runs_root.is_dir():
        print(
            "RAW_VERIFICATION=FAIL "
            f"reason=missing_runs_root path={runs_root}"
        )
        return 1

    if output.exists():
        print(
            "RAW_VERIFICATION=FAIL "
            f"reason=output_exists path={output}"
        )
        return 1

    output.mkdir(parents=True)

    trial_dirs = sorted(
        path
        for path in runs_root.iterdir()
        if path.is_dir()
    )

    expected_trials = sum(
        specification["count"]
        for specification in candidates.values()
    )

    if len(trial_dirs) != expected_trials:
        print(
            "RAW_VERIFICATION=FAIL "
            "reason=trial_count "
            f"expected={expected_trials} "
            f"actual={len(trial_dirs)}"
        )
        return 1

    rows: list[dict[str, Any]] = []

    for trial in trial_dirs:
        metadata = read_metadata(
            trial / "run-metadata.txt"
        )

        candidate = detect_candidate(
            trial,
            metadata,
            candidates,
        )

        qe_out_path = trial / "qe.out"
        qe_err_path = trial / "qe.err"

        qe_out = (
            qe_out_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
            if qe_out_path.is_file()
            else ""
        )

        qe_err = (
            qe_err_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
            if qe_err_path.is_file()
            else ""
        )

        try:
            qe_rc = int(
                (trial / "qe-exit-code.txt")
                .read_text(encoding="utf-8")
                .strip()
            )
        except (OSError, ValueError):
            qe_rc = None

        layout, mapping_count = mapping_layout(
            trial / "rank-mapping"
        )

        rows.append({
            "trial_id": trial.name,
            "candidate": candidate,
            "layout_values": layout,
            "layout": ",".join(
                str(value)
                for value in layout
            ),
            "mapping_count": mapping_count,
            "qe_exit_code": qe_rc,
            "number_of_k_points": last_int(
                r"number of k points\s*=\s*([0-9]+)",
                qe_out,
            ),
            "scf_iterations": last_int(
                r"convergence has been achieved in\s+"
                r"([0-9]+)\s+iterations",
                qe_out,
            ),
            "total_energy_ry": last_float(
                r"!\s+total energy\s*=\s*"
                r"([-+0-9.Ee]+)\s+Ry",
                qe_out,
            ),
            "qe_wall_time_sec": pwscf_wall_seconds(
                qe_out
            ),
            "input_sha256": sha256_file(
                trial / "pw.in"
            ),
            "job_done": "JOB DONE." in qe_out,
            "fatal_error": bool(
                FATAL_RE.search(
                    qe_out + "\n" + qe_err
                )
            ),
        })

    energies = [
        row["total_energy_ry"]
        for row in rows
        if row["total_energy_ry"] is not None
    ]

    reference_energy = (
        statistics.median(energies)
        if len(energies) == expected_trials
        else None
    )

    candidate_counts = Counter(
        row["candidate"]
        for row in rows
    )

    overall = True

    for row in rows:
        reasons: list[str] = []
        specification = candidates.get(
            row["candidate"]
        )

        if specification is None:
            reasons.append("unknown_candidate")
        else:
            if (
                row["layout_values"]
                != specification["layout"]
            ):
                reasons.append(
                    "layout={} expected={}".format(
                        row["layout_values"],
                        specification["layout"],
                    )
                )

            if (
                row["mapping_count"]
                != specification["ranks"]
            ):
                reasons.append(
                    "mapping_count={} expected={}".format(
                        row["mapping_count"],
                        specification["ranks"],
                    )
                )

        if row["qe_exit_code"] != 0:
            reasons.append(
                f"qe_exit_code={row['qe_exit_code']}"
            )

        if not row["job_done"]:
            reasons.append("job_done_missing")

        if row["fatal_error"]:
            reasons.append("fatal_error")

        if (
            row["number_of_k_points"]
            != experiment["expected_k_points"]
        ):
            reasons.append(
                "number_of_k_points={} expected={}".format(
                    row["number_of_k_points"],
                    experiment["expected_k_points"],
                )
            )

        if (
            row["scf_iterations"]
            != experiment["expected_iterations"]
        ):
            reasons.append(
                "scf_iterations={} expected={}".format(
                    row["scf_iterations"],
                    experiment["expected_iterations"],
                )
            )

        if row["qe_wall_time_sec"] is None:
            reasons.append("wall_time_missing")

        if (
            row["input_sha256"]
            != experiment["expected_input_sha256"]
        ):
            reasons.append(
                "input_sha256={} expected={}".format(
                    row["input_sha256"],
                    experiment[
                        "expected_input_sha256"
                    ],
                )
            )

        energy_error = None

        if (
            reference_energy is not None
            and row["total_energy_ry"] is not None
        ):
            energy_error = abs(
                row["total_energy_ry"]
                - reference_energy
            )

            if energy_error > tolerance:
                reasons.append(
                    "energy_error={} tolerance={}".format(
                        energy_error,
                        tolerance,
                    )
                )
        else:
            reasons.append(
                "energy_reference_missing"
            )

        row["reference_energy_ry"] = reference_energy
        row["energy_abs_error_ry"] = energy_error
        row["pass"] = not reasons
        row["failure_reasons"] = ";".join(reasons)

        row.pop("layout_values")

        if reasons:
            overall = False

    for candidate, specification in candidates.items():
        if (
            candidate_counts[candidate]
            != specification["count"]
        ):
            overall = False

            print(
                "candidate_count_mismatch={} "
                "expected={} actual={}".format(
                    candidate,
                    specification["count"],
                    candidate_counts[candidate],
                )
            )

    trial_fields = [
        "trial_id",
        "candidate",
        "layout",
        "mapping_count",
        "qe_exit_code",
        "number_of_k_points",
        "scf_iterations",
        "total_energy_ry",
        "reference_energy_ry",
        "energy_abs_error_ry",
        "qe_wall_time_sec",
        "input_sha256",
        "job_done",
        "fatal_error",
        "pass",
        "failure_reasons",
    ]

    with (
        output / "raw-trial-results.csv"
    ).open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=trial_fields,
        )

        writer.writeheader()
        writer.writerows(rows)

    valid_groups: dict[str, list[float]] = (
        defaultdict(list)
    )

    for row in rows:
        if (
            row["pass"]
            and row["qe_wall_time_sec"] is not None
        ):
            valid_groups[
                row["candidate"]
            ].append(
                float(row["qe_wall_time_sec"])
            )

    summary_rows: list[dict[str, Any]] = []

    for candidate, specification in candidates.items():
        values = valid_groups.get(
            candidate,
            [],
        )

        median = (
            statistics.median(values)
            if values
            else None
        )

        mean = (
            statistics.mean(values)
            if values
            else None
        )

        cv = (
            statistics.stdev(values)
            / mean
            * 100.0
            if len(values) > 1 and mean
            else None
        )

        active_gpu_seconds = (
            median
            * specification["active_gpus"]
            if median is not None
            else None
        )

        summary_rows.append({
            "candidate": candidate,
            "valid_trials": len(values),
            "raw_wall_times_sec": ",".join(
                f"{value:.2f}"
                for value in values
            ),
            "median_wall_sec": median,
            "mean_wall_sec": mean,
            "cv_percent": cv,
            "active_gpus": (
                specification["active_gpus"]
            ),
            "median_active_gpu_seconds": (
                active_gpu_seconds
            ),
        })

    summary_fields = [
        "candidate",
        "valid_trials",
        "raw_wall_times_sec",
        "median_wall_sec",
        "mean_wall_sec",
        "cv_percent",
        "active_gpus",
        "median_active_gpu_seconds",
    ]

    with (
        output / "raw-candidate-summary.csv"
    ).open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=summary_fields,
        )

        writer.writeheader()
        writer.writerows(summary_rows)

    medians = {
        row["candidate"]: float(
            row["median_wall_sec"]
        )
        for row in summary_rows
        if row["median_wall_sec"] is not None
    }

    gpu_seconds = {
        row["candidate"]: float(
            row["median_active_gpu_seconds"]
        )
        for row in summary_rows
        if (
            row["median_active_gpu_seconds"]
            is not None
        )
    }

    maximum_energy_error = max(
        (
            float(row["energy_abs_error_ry"])
            for row in rows
            if (
                row["energy_abs_error_ry"]
                is not None
            )
        ),
        default=None,
    )

    lines = [
        f"experiment={args.experiment}",
        f"root={root}",
        f"expected_trials={expected_trials}",
        f"actual_trials={len(rows)}",
        "valid_trials={}".format(
            sum(
                1
                for row in rows
                if row["pass"]
            )
        ),
        "failed_trials={}".format(
            sum(
                1
                for row in rows
                if not row["pass"]
            )
        ),
        f"reference_energy_ry={reference_energy}",
        f"energy_tolerance_ry={tolerance}",
        "maximum_energy_abs_error_ry="
        f"{maximum_energy_error}",
    ]

    lines.extend(
        derived_summary(
            args.experiment,
            medians,
        )
    )

    lines.extend([
        "latency_winner={}".format(
            min(
                medians,
                key=medians.get,
            )
            if len(medians) == len(candidates)
            else ""
        ),
        "active_gpu_seconds_winner={}".format(
            min(
                gpu_seconds,
                key=gpu_seconds.get,
            )
            if (
                len(gpu_seconds)
                == len(candidates)
            )
            else ""
        ),
        "raw_verification={}".format(
            "PASS"
            if overall
            else "FAIL"
        ),
    ])

    (
        output / "raw-verification-summary.txt"
    ).write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    for row in rows:
        print(
            "trial={} candidate={} layout={} "
            "mapping_count={} qe_rc={} nk={} "
            "iterations={} energy={} wall={} "
            "input_sha={} pass={} reasons={}".format(
                row["trial_id"],
                row["candidate"],
                row["layout"],
                row["mapping_count"],
                row["qe_exit_code"],
                row["number_of_k_points"],
                row["scf_iterations"],
                row["total_energy_ry"],
                row["qe_wall_time_sec"],
                row["input_sha256"],
                row["pass"],
                row["failure_reasons"],
            )
        )

    for row in summary_rows:
        print(
            "candidate={} raw={} median={} "
            "mean={} cv={} active_gpus={} "
            "active_gpu_seconds={}".format(
                row["candidate"],
                row["raw_wall_times_sec"],
                row["median_wall_sec"],
                row["mean_wall_sec"],
                row["cv_percent"],
                row["active_gpus"],
                row[
                    "median_active_gpu_seconds"
                ],
            )
        )

    print(
        "RAW_VERIFICATION={}".format(
            "PASS"
            if overall
            else "FAIL"
        )
    )

    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
