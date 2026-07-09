#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import json
import os
import zipfile
from pathlib import Path
from typing import Any


COLUMNS = [
    "gate_id",
    "run_id",
    "run_dir",
    "run_type",
    "input_type",
    "case_name",
    "candidate_id",
    "candidate_role",
    "pw_x_path",
    "build_hash",
    "input_path",
    "input_hash",
    "pseudo_files",
    "pseudo_hashes",
    "pseudo_status",
    "partition",
    "nodes",
    "ntasks",
    "ntasks_per_node",
    "cpus_per_task",
    "gres",
    "time_limit",
    "slurm_job_id",
    "slurm_state",
    "slurm_exit_code",
    "qe_started",
    "qe_normal_end",
    "fatal_error_detected",
    "convergence_status",
    "parser_status",
    "result_status",
    "failure_class",
    "qe_wall_time_sec",
    "qe_cpu_time_sec",
    "total_energy_ry",
    "scf_iterations",
    "number_of_atoms",
    "number_of_k_points",
    "eligible_for_timing_comparison",
    "exclusion_reason",
    "benchmark_valid",
    "performance_claim_allowed",
    "optimization_claim_allowed",
    "notes",
]


SHEETS = [
    "Dashboard",
    "All_Runs",
    "Smoke",
    "TypeA_manyk",
    "TypeB_gamma",
    "TypeB_si512",
    "TypeB_si1000",
    "Correctness_Arbiter",
    "Failures",
    "Build_Artifacts",
    "Pseudos",
    "Comparison_Summary",
]


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def read_first_line(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(errors="replace").splitlines()[0].strip() if path.read_text(errors="replace").splitlines() else ""


def classify_input_type(case_name: str) -> str:
    if case_name == "smoke-si8" or case_name.startswith("smoke"):
        return "Smoke"
    if case_name.startswith("typeA"):
        return "TypeA_manyk"
    if case_name == "typeB-si512-gamma":
        return "TypeB_si512"
    if case_name == "typeB-si1000-gamma":
        return "TypeB_si1000"
    if case_name.startswith("typeB"):
        return "TypeB_gamma"
    return "unknown"


def candidate_role(candidate_id: str) -> tuple[str, bool, str]:
    if "G1p" in candidate_id or "nvtx" in candidate_id:
        return "profiling_only", False, "NVTX profiling-only; excluded from timing comparison"
    if "C3" in candidate_id or "openblas" in candidate_id:
        return "correctness_arbiter", False, "correctness arbiter only; excluded from performance comparison"
    if "C2" in candidate_id:
        return "deferred", False, "C2 deferred"
    if candidate_id.startswith("C1"):
        return "cpu_isolation", False, "CPU-only isolation; not in GPU timing group"
    if candidate_id.startswith("G"):
        return "performance_candidate", True, ""
    return "unknown", False, "unknown candidate role"


def parse_hash_file(path: Path) -> str:
    if not path.exists():
        return ""
    vals = []
    for line in path.read_text(errors="replace").splitlines():
        parts = line.split()
        if parts:
            vals.append(parts[0])
    return ";".join(vals)


def load_run(run_dir: Path) -> dict[str, Any]:
    meta = read_json(run_dir / "metadata.json")
    parsed = {}
    if (run_dir / "parsed.json").exists():
        parsed = read_json(run_dir / "parsed.json")
    elif (run_dir / "smoke_summary.json").exists():
        parsed = read_json(run_dir / "smoke_summary.json")

    row: dict[str, Any] = {}
    row.update(meta)
    row.update(parsed)

    run_id = meta.get("run_id") or run_dir.name
    case_name = meta.get("case_name") or parsed.get("case_name") or ""
    candidate_id = meta.get("candidate_id") or parsed.get("candidate_id") or ""

    role, eligible, reason = candidate_role(candidate_id)

    input_hash = meta.get("input_hash") or parse_hash_file(run_dir / "input.sha256")
    pseudo_hashes = meta.get("pseudo_hashes") or parse_hash_file(run_dir / "pseudo.sha256")

    if isinstance(pseudo_hashes, list):
        pseudo_hashes = ";".join(str(x) for x in pseudo_hashes)
    if isinstance(input_hash, list):
        input_hash = ";".join(str(x) for x in input_hash)

    parser_status = parsed.get("parser_status")
    if not parser_status:
        parser_status = "missing" if not (run_dir / "parsed.json").exists() and not (run_dir / "smoke_summary.json").exists() else "partial"

    result_status = parsed.get("result_status")
    if not result_status:
        result_status = "incomplete"

    benchmark_valid = bool(row.get("benchmark_valid", False))
    # Fail closed: collector never promotes benchmark_valid.
    if benchmark_valid is not False:
        benchmark_valid = False

    out = {
        "gate_id": row.get("gate_id", ""),
        "run_id": run_id,
        "run_dir": str(run_dir),
        "run_type": row.get("run_type", ""),
        "input_type": row.get("input_type") or classify_input_type(case_name),
        "case_name": case_name,
        "candidate_id": candidate_id,
        "candidate_role": row.get("candidate_role") or role,
        "pw_x_path": row.get("pw_x_path") or row.get("pwx", ""),
        "build_hash": row.get("build_hash", ""),
        "input_path": row.get("input_path", ""),
        "input_hash": input_hash,
        "pseudo_files": ";".join(row.get("pseudo_files", [])) if isinstance(row.get("pseudo_files"), list) else row.get("pseudo_files", ""),
        "pseudo_hashes": pseudo_hashes,
        "pseudo_status": row.get("pseudo_status", "unknown"),
        "partition": row.get("partition") or row.get("slurm_partition", ""),
        "nodes": row.get("nodes", ""),
        "ntasks": row.get("ntasks", ""),
        "ntasks_per_node": row.get("ntasks_per_node", ""),
        "cpus_per_task": row.get("cpus_per_task", ""),
        "gres": row.get("gres", ""),
        "time_limit": row.get("time_limit", ""),
        "slurm_job_id": row.get("slurm_job_id", ""),
        "slurm_state": row.get("slurm_state", ""),
        "slurm_exit_code": row.get("slurm_exit_code") or row.get("qe_exit_code", ""),
        "qe_started": row.get("qe_started", ""),
        "qe_normal_end": row.get("qe_normal_end", ""),
        "fatal_error_detected": row.get("fatal_error_detected", ""),
        "convergence_status": row.get("convergence_status", ""),
        "parser_status": parser_status,
        "result_status": result_status,
        "failure_class": row.get("failure_class", ""),
        "qe_wall_time_sec": row.get("qe_wall_time_sec", ""),
        "qe_cpu_time_sec": row.get("qe_cpu_time_sec", ""),
        "total_energy_ry": row.get("total_energy_ry", ""),
        "scf_iterations": row.get("scf_iterations", ""),
        "number_of_atoms": row.get("number_of_atoms", ""),
        "number_of_k_points": row.get("number_of_k_points", ""),
        "eligible_for_timing_comparison": eligible and not benchmark_valid is False,
        "exclusion_reason": row.get("exclusion_reason") or reason,
        "benchmark_valid": False,
        "performance_claim_allowed": False,
        "optimization_claim_allowed": False,
        "notes": row.get("notes", ""),
    }

    # For smoke/baseperf planning, eligible_for_timing_comparison should remain false unless a later gate says otherwise.
    if out["gate_id"] != "BUILD-BASEPERF-T001":
        out["eligible_for_timing_comparison"] = False
        if not out["exclusion_reason"]:
            out["exclusion_reason"] = "not in base performance gate"

    return out


def rows_to_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})


def sheet_xml(rows: list[list[Any]]) -> str:
    xml_rows = []
    for r_idx, row in enumerate(rows, start=1):
        cells = []
        for c_idx, value in enumerate(row, start=1):
            col = ""
            n = c_idx
            while n:
                n, rem = divmod(n - 1, 26)
                col = chr(65 + rem) + col
            ref = f"{col}{r_idx}"
            text = "" if value is None else str(value)
            cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{html.escape(text)}</t></is></c>')
        xml_rows.append(f'<row r="{r_idx}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData>'
        + "".join(xml_rows)
        + '</sheetData></worksheet>'
    )


def write_xlsx(sheet_data: dict[str, list[list[Any]]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet_names = list(sheet_data.keys())
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            + ''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1, len(sheet_names)+1))
            + '</Types>')
        z.writestr("_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>')
        z.writestr("xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets>'
            + ''.join(f'<sheet name="{html.escape(name)}" sheetId="{i}" r:id="rId{i}"/>' for i, name in enumerate(sheet_names, start=1))
            + '</sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + ''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(sheet_names)+1))
            + '</Relationships>')
        for i, name in enumerate(sheet_names, start=1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", sheet_xml(sheet_data[name]))


def make_sheet_data(rows: list[dict[str, Any]], pseudo_manifest: Path | None = None) -> dict[str, list[list[Any]]]:
    header = COLUMNS
    all_rows = [header] + [[r.get(c, "") for c in COLUMNS] for r in rows]

    def filt(pred):
        return [header] + [[r.get(c, "") for c in COLUMNS] for r in rows if pred(r)]

    failures = filt(lambda r: str(r.get("result_status", "")).lower() in {"fail", "incomplete"} or bool(r.get("failure_class")) or str(r.get("slurm_state", "")).upper() == "FAILED")
    smoke = filt(lambda r: r.get("run_type") == "smoke" or r.get("case_name") == "smoke-si8")
    typea = filt(lambda r: r.get("input_type") == "TypeA_manyk")
    typeb = filt(lambda r: str(r.get("input_type", "")).startswith("TypeB"))
    typeb512 = filt(lambda r: r.get("case_name") == "typeB-si512-gamma")
    typeb1000 = filt(lambda r: r.get("case_name") == "typeB-si1000-gamma")
    c3 = filt(lambda r: r.get("candidate_role") == "correctness_arbiter" or "C3" in r.get("candidate_id", ""))

    unique_builds = {}
    for r in rows:
        cid = r.get("candidate_id", "")
        if cid and cid not in unique_builds:
            unique_builds[cid] = [
                cid,
                r.get("candidate_role", ""),
                r.get("build_hash", ""),
                r.get("pw_x_path", ""),
                r.get("exclusion_reason", ""),
            ]
    build_artifacts = [["candidate_id", "candidate_role", "build_hash", "pw_x_path", "notes"]] + list(unique_builds.values())

    pseudo_rows = [["timestamp_utc", "filename", "sha256", "source", "role", "notes"]]
    if pseudo_manifest and pseudo_manifest.exists():
        for line in pseudo_manifest.read_text(errors="replace").splitlines()[1:]:
            pseudo_rows.append(line.split("\t"))

    dashboard = [
        ["Metric", "Value"],
        ["total_rows", len(rows)],
        ["smoke_rows", max(0, len(smoke) - 1)],
        ["failure_rows", max(0, len(failures) - 1)],
        ["typeA_rows", max(0, len(typea) - 1)],
        ["typeB_rows", max(0, len(typeb) - 1)],
        ["benchmark_valid_rows", 0],
        ["performance_claim_allowed", "false"],
        ["optimization_claim_allowed", "false"],
    ]

    comparison_summary = [
        ["status", "reason"],
        ["not_available", "Comparison summary is disabled until BUILD-BASEPERF-T001 with matching guards."],
    ]

    return {
        "Dashboard": dashboard,
        "All_Runs": all_rows,
        "Smoke": smoke,
        "TypeA_manyk": typea,
        "TypeB_gamma": typeb,
        "TypeB_si512": typeb512,
        "TypeB_si1000": typeb1000,
        "Correctness_Arbiter": c3,
        "Failures": failures,
        "Build_Artifacts": build_artifacts,
        "Pseudos": pseudo_rows,
        "Comparison_Summary": comparison_summary,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect QE run directories into results.csv and qe_results.xlsx.")
    ap.add_argument("--root", type=Path, default=Path(f"/work/{os.environ.get('USER', '')}/hipac26-qe-runs"))
    ap.add_argument("--csv", type=Path)
    ap.add_argument("--xlsx", type=Path)
    ap.add_argument("--no-xlsx", action="store_true")
    args = ap.parse_args()

    root = args.root
    csv_path = args.csv or root / "results.csv"
    xlsx_path = args.xlsx or root / "qe_results.xlsx"

    rows = []
    for meta_path in sorted(root.rglob("metadata.json")):
        # Skip derived/report dirs if any.
        run_dir = meta_path.parent
        rows.append(load_run(run_dir))

    rows_to_csv(rows, csv_path)

    if not args.no_xlsx:
        pseudo_manifest = Path(f"/work/{os.environ.get('USER', '')}/hipac26-qe-pseudos/pseudos_manifest.tsv")
        sheet_data = make_sheet_data(rows, pseudo_manifest=pseudo_manifest)
        write_xlsx(sheet_data, xlsx_path)

    print(f"rows={len(rows)}")
    print(f"csv={csv_path}")
    if not args.no_xlsx:
        print(f"xlsx={xlsx_path}")
        print("sheets=" + ",".join(SHEETS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
