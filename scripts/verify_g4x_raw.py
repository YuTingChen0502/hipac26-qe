#!/usr/bin/env python3

import argparse
import csv
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

SPECS = {
    "e002": {
        "r14": {"count": 3, "ranks": 14, "layout": [7, 7]},
        "r7":  {"count": 3, "ranks": 7,  "layout": [7]},
    },
    "e003": {
        "map7x7": {"count": 3, "ranks": 14, "layout": [7, 7]},
        "map8x6": {"count": 3, "ranks": 14, "layout": [6, 8]},
    },
}


def read_metadata(path):
    result = {}

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


def last_float(pattern, text):
    values = re.findall(pattern, text, flags=re.MULTILINE)
    return float(values[-1]) if values else None


def last_int(pattern, text):
    values = re.findall(pattern, text, flags=re.MULTILINE)
    return int(values[-1]) if values else None


def mapping_layout(path):
    hosts = Counter()

    if not path.is_dir():
        return [], 0

    for item in path.rglob("*"):
        if not item.is_file():
            continue

        text = item.read_text(
            encoding="utf-8",
            errors="replace",
        )

        match = re.search(r"\bhost=([^\s]+)", text)

        if match:
            hosts[match.group(1)] += 1

    return sorted(hosts.values()), sum(hosts.values())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument(
        "--experiment",
        choices=("e002", "e003"),
        required=True,
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--energy-tolerance",
        type=float,
        default=1e-6,
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)

    specs = SPECS[args.experiment]
    trial_dirs = sorted(
        path
        for path in (root / "runs").iterdir()
        if path.is_dir()
    )

    if len(trial_dirs) != 6:
        print(
            "RAW_VERIFICATION=FAIL "
            "reason=trial_count actual={}".format(len(trial_dirs))
        )
        return 1

    rows = []

    for trial in trial_dirs:
        metadata = read_metadata(trial / "run-metadata.txt")
        candidate = metadata.get("candidate", "")

        if candidate not in specs:
            for name in specs:
                if name in trial.name:
                    candidate = name
                    break

        qe_out = (trial / "qe.out").read_text(
            encoding="utf-8",
            errors="replace",
        )

        qe_err = (
            (trial / "qe.err").read_text(
                encoding="utf-8",
                errors="replace",
            )
            if (trial / "qe.err").is_file()
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

        wall = last_float(
            r"PWSCF\s*:\s*.*?([0-9]+(?:\.[0-9]+)?)s\s+WALL",
            qe_out,
        )
        energy = last_float(
            r"!\s+total energy\s*=\s*([-+0-9.Ee]+)\s+Ry",
            qe_out,
        )
        iterations = last_int(
            r"convergence has been achieved in\s+([0-9]+)\s+iterations",
            qe_out,
        )
        k_points = last_int(
            r"number of k points\s*=\s*([0-9]+)",
            qe_out,
        )

        layout, mapping_count = mapping_layout(
            trial / "rank-mapping"
        )

        fatal = bool(
            re.search(
                r"Error in routine|MPI_ABORT|Segmentation fault|"
                r"CUDA error|out of memory|\bKilled\b",
                qe_out + "\n" + qe_err,
                flags=re.IGNORECASE,
            )
        )

        rows.append({
            "trial_id": trial.name,
            "candidate": candidate,
            "layout": ",".join(str(v) for v in layout),
            "layout_values": layout,
            "mapping_count": mapping_count,
            "qe_exit_code": qe_rc,
            "number_of_k_points": k_points,
            "scf_iterations": iterations,
            "total_energy_ry": energy,
            "qe_wall_time_sec": wall,
            "job_done": "JOB DONE." in qe_out,
            "fatal_error": fatal,
        })

    valid_energies = [
        row["total_energy_ry"]
        for row in rows
        if row["total_energy_ry"] is not None
    ]

    reference_energy = (
        statistics.median(valid_energies)
        if len(valid_energies) == 6
        else None
    )

    counts = Counter(row["candidate"] for row in rows)
    overall = True

    for row in rows:
        spec = specs.get(row["candidate"])
        reasons = []

        if spec is None:
            reasons.append("unknown_candidate")
        else:
            if row["layout_values"] != spec["layout"]:
                reasons.append(
                    "layout={} expected={}".format(
                        row["layout_values"],
                        spec["layout"],
                    )
                )

            if row["mapping_count"] != spec["ranks"]:
                reasons.append(
                    "mapping_count={} expected={}".format(
                        row["mapping_count"],
                        spec["ranks"],
                    )
                )

        if row["qe_exit_code"] != 0:
            reasons.append("qe_exit_code={}".format(row["qe_exit_code"]))

        if not row["job_done"]:
            reasons.append("job_done_missing")

        if row["fatal_error"]:
            reasons.append("fatal_error")

        if row["number_of_k_points"] != 7:
            reasons.append(
                "number_of_k_points={}".format(
                    row["number_of_k_points"]
                )
            )

        if row["scf_iterations"] is None:
            reasons.append("convergence_missing")

        if row["qe_wall_time_sec"] is None:
            reasons.append("wall_time_missing")

        if row["total_energy_ry"] is None:
            reasons.append("energy_missing")

        energy_error = None

        if (
            reference_energy is not None
            and row["total_energy_ry"] is not None
        ):
            energy_error = abs(
                row["total_energy_ry"] - reference_energy
            )

            if energy_error > args.energy_tolerance:
                reasons.append(
                    "energy_error={}".format(energy_error)
                )
        else:
            reasons.append("energy_reference_missing")

        row["reference_energy_ry"] = reference_energy
        row["energy_abs_error_ry"] = energy_error
        row["pass"] = not reasons
        row["failure_reasons"] = ";".join(reasons)
        row.pop("layout_values")

        if reasons:
            overall = False

    for candidate, spec in specs.items():
        if counts[candidate] != spec["count"]:
            overall = False
            print(
                "candidate_count_mismatch={} expected={} actual={}".format(
                    candidate,
                    spec["count"],
                    counts[candidate],
                )
            )

    fields = [
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
        "job_done",
        "fatal_error",
        "pass",
        "failure_reasons",
    ]

    with (output / "raw-trial-results.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    groups = defaultdict(list)

    for row in rows:
        if row["pass"]:
            groups[row["candidate"]].append(
                row["qe_wall_time_sec"]
            )

    summary_rows = []

    for candidate in specs:
        values = groups.get(candidate, [])

        summary_rows.append({
            "candidate": candidate,
            "valid_trials": len(values),
            "raw_wall_times_sec": ",".join(
                "{:.2f}".format(value)
                for value in values
            ),
            "median_wall_sec": (
                statistics.median(values)
                if values
                else ""
            ),
            "mean_wall_sec": (
                statistics.mean(values)
                if values
                else ""
            ),
            "cv_percent": (
                statistics.stdev(values)
                / statistics.mean(values)
                * 100.0
                if len(values) > 1
                else ""
            ),
        })

    with (output / "raw-candidate-summary.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "candidate",
                "valid_trials",
                "raw_wall_times_sec",
                "median_wall_sec",
                "mean_wall_sec",
                "cv_percent",
            ],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    medians = {
        row["candidate"]: row["median_wall_sec"]
        for row in summary_rows
        if row["median_wall_sec"] != ""
    }

    ratio_name = ""
    ratio = None
    winner = ""

    if args.experiment == "e002" and len(medians) == 2:
        ratio_name = "r14_over_r7_median_ratio"
        ratio = medians["r14"] / medians["r7"]
        winner = min(medians, key=medians.get)

    if args.experiment == "e003" and len(medians) == 2:
        ratio_name = "map8x6_over_map7x7_median_ratio"
        ratio = medians["map8x6"] / medians["map7x7"]
        winner = min(medians, key=medians.get)

    lines = [
        "experiment={}".format(args.experiment),
        "actual_trials={}".format(len(rows)),
        "valid_trials={}".format(
            sum(1 for row in rows if row["pass"])
        ),
        "failed_trials={}".format(
            sum(1 for row in rows if not row["pass"])
        ),
        "reference_energy_ry={}".format(reference_energy),
    ]

    if ratio is not None:
        lines.append("{}={:.9f}".format(ratio_name, ratio))
        lines.append("latency_winner={}".format(winner))

    lines.append(
        "raw_verification={}".format(
            "PASS" if overall else "FAIL"
        )
    )

    (output / "raw-verification-summary.txt").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    for row in rows:
        print(
            "trial={} candidate={} layout={} qe_rc={} nk={} "
            "iterations={} energy={} wall={} pass={} reasons={}".format(
                row["trial_id"],
                row["candidate"],
                row["layout"],
                row["qe_exit_code"],
                row["number_of_k_points"],
                row["scf_iterations"],
                row["total_energy_ry"],
                row["qe_wall_time_sec"],
                row["pass"],
                row["failure_reasons"],
            )
        )

    for row in summary_rows:
        print(
            "candidate={} raw={} median={} mean={} cv={}".format(
                row["candidate"],
                row["raw_wall_times_sec"],
                row["median_wall_sec"],
                row["mean_wall_sec"],
                row["cv_percent"],
            )
        )

    if ratio is not None:
        print("{}={:.9f}".format(ratio_name, ratio))
        print("latency_winner={}".format(winner))

    print(
        "RAW_VERIFICATION={}".format(
            "PASS" if overall else "FAIL"
        )
    )

    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
