#!/usr/bin/env python3
"""Deterministic QE input derivation utilities for controlled Nano4 cases."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class DerivationError(RuntimeError):
    pass


CARD_HEADERS = (
    "ATOMIC_SPECIES",
    "ATOMIC_POSITIONS",
    "CELL_PARAMETERS",
    "K_POINTS",
    "CONSTRAINTS",
    "OCCUPATIONS",
    "ATOMIC_FORCES",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def strip_qe_comment(line: str) -> str:
    quote: str | None = None
    i = 0
    while i < len(line):
        char = line[i]
        if quote:
            if char == quote:
                quote = None
        elif char in {"'", '"'}:
            quote = char
        elif char == "!":
            return line[:i]
        i += 1
    return line


def split_qe_csv(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    quote: str | None = None
    for i, char in enumerate(text):
        if quote:
            if char == quote:
                quote = None
        elif char in {"'", '"'}:
            quote = char
        elif char == ",":
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return parts


def normalize_scalar(value: str) -> str:
    text = value.strip().rstrip(",").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    return re.sub(r"\s+", " ", text)


def parse_namelists(text: str) -> dict[str, dict[str, str]]:
    namelists: dict[str, dict[str, str]] = {}
    current: str | None = None
    assignment = re.compile(
        r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*('(?:[^']*)'|\"(?:[^\"]*)\"|[^,\s/]+)"
    )

    for raw_line in text.splitlines():
        line = strip_qe_comment(raw_line).strip()
        if not line:
            continue
        if current is None:
            match = re.match(r"&([A-Za-z0-9_]+)\b(.*)$", line)
            if match:
                current = match.group(1).lower()
                rest = match.group(2).strip()
                if rest:
                    for item in assignment.finditer(rest):
                        namelists.setdefault(current, {})[item.group(1).lower()] = normalize_scalar(item.group(2))
            continue
        if line == "/":
            current = None
            continue
        if line.endswith("/"):
            for item in assignment.finditer(line[:-1]):
                namelists.setdefault(current, {})[item.group(1).lower()] = normalize_scalar(item.group(2))
            current = None
            continue
        for item in assignment.finditer(line):
            namelists.setdefault(current, {})[item.group(1).lower()] = normalize_scalar(item.group(2))

    if current is not None:
        raise DerivationError(f"unterminated namelist: {current}")
    return namelists


def is_card_header(line: str) -> bool:
    token = strip_qe_comment(line).strip().split()
    if not token:
        return False
    return token[0].upper() in CARD_HEADERS or token[0].startswith("&")


def parse_cards(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    cards: dict[str, Any] = {}
    i = 0
    while i < len(lines):
        stripped = strip_qe_comment(lines[i]).strip()
        upper = stripped.upper()
        if upper == "ATOMIC_SPECIES":
            entries: list[list[str]] = []
            i += 1
            while i < len(lines) and strip_qe_comment(lines[i]).strip() and not is_card_header(lines[i]):
                entries.append(strip_qe_comment(lines[i]).split())
                i += 1
            cards["ATOMIC_SPECIES"] = entries
            continue
        if upper.startswith("K_POINTS"):
            mode = stripped.split()[1].lower() if len(stripped.split()) > 1 else ""
            i += 1
            while i < len(lines) and not strip_qe_comment(lines[i]).strip():
                i += 1
            value = strip_qe_comment(lines[i]).split() if i < len(lines) else []
            cards["K_POINTS"] = {"mode": mode, "value": value}
            i += 1
            continue
        if upper.startswith("CELL_PARAMETERS"):
            unit = stripped.split()[1].lower() if len(stripped.split()) > 1 else ""
            rows: list[list[str]] = []
            for row in lines[i + 1 : i + 4]:
                rows.append(strip_qe_comment(row).split())
            cards["CELL_PARAMETERS"] = {"unit": unit, "rows": rows}
            i += 4
            continue
        if upper.startswith("ATOMIC_POSITIONS"):
            unit = stripped.split()[1].lower() if len(stripped.split()) > 1 else ""
            rows = []
            i += 1
            while i < len(lines) and strip_qe_comment(lines[i]).strip() and not is_card_header(lines[i]):
                rows.append(strip_qe_comment(lines[i]).split())
                i += 1
            cards["ATOMIC_POSITIONS"] = {"unit": unit, "rows": rows}
            continue
        i += 1
    return cards


def parse_qe_input(text: str) -> dict[str, Any]:
    namelists = parse_namelists(text)
    cards = parse_cards(text)
    electrons = namelists.get("electrons", {})
    return {
        "namelists": namelists,
        "cards": cards,
        "prefix": namelists.get("control", {}).get("prefix"),
        "pseudo_dir": namelists.get("control", {}).get("pseudo_dir"),
        "outdir": namelists.get("control", {}).get("outdir"),
        "restart_settings": {
            key: value
            for scope in ("control", "electrons")
            for key, value in namelists.get(scope, {}).items()
            if "restart" in key or key in {"disk_io", "outdir", "startingpot", "startingwfc"}
        },
        "electron_maxstep": electrons.get("electron_maxstep"),
        "atomic_species": cards.get("ATOMIC_SPECIES", []),
        "pseudo_filenames": [row[2] for row in cards.get("ATOMIC_SPECIES", []) if len(row) >= 3],
        "k_points": cards.get("K_POINTS"),
    }


def find_active_numeric_assignment(text: str, field: str) -> tuple[int, int, int, str]:
    matches: list[tuple[int, int, int, str]] = []
    pattern = re.compile(rf"(?i)(\b{re.escape(field)}\s*=\s*)([+-]?\d+)(\b)")
    offset = 0
    for line_number, line in enumerate(text.splitlines(keepends=True), 1):
        uncommented = strip_qe_comment(line)
        match = pattern.search(uncommented)
        if match:
            start = offset + match.start(2)
            end = offset + match.end(2)
            matches.append((line_number, start, end, match.group(2)))
        offset += len(line)
    if not matches:
        raise DerivationError(f"zero active {field} assignments")
    if len(matches) > 1:
        raise DerivationError(f"multiple active {field} assignments: {len(matches)}")
    return matches[0]


def semantic_without_electron_maxstep(parsed: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(parsed, sort_keys=True))
    result["electron_maxstep"] = "<ignored>"
    result["namelists"].setdefault("electrons", {}).pop("electron_maxstep", None)
    return result


def semantic_compare_except_electron_maxstep(source_text: str, derived_text: str) -> dict[str, Any]:
    source = parse_qe_input(source_text)
    derived = parse_qe_input(derived_text)
    comparable_source = semantic_without_electron_maxstep(source)
    comparable_derived = semantic_without_electron_maxstep(derived)
    return {
        "equivalent_except_electron_maxstep": comparable_source == comparable_derived,
        "source_electron_maxstep": source.get("electron_maxstep"),
        "derived_electron_maxstep": derived.get("electron_maxstep"),
        "source_summary": source,
        "derived_summary": derived,
    }


def reject_symlink_parents(path: Path, label: str) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:-1]:
        current = current / part
        if current.exists() and current.is_symlink():
            raise DerivationError(f"{label} parent component is symlink: {current}")


def derive_electron_maxstep(
    *,
    source: Path,
    dest: Path,
    expected_value: int,
    new_value: int,
) -> dict[str, Any]:
    if not source.is_file():
        raise DerivationError(f"source input missing: {source}")
    reject_symlink_parents(dest, "destination")
    source_bytes = source.read_bytes()
    source_text = source_bytes.decode("utf-8")
    line_number, start, end, observed = find_active_numeric_assignment(source_text, "electron_maxstep")
    if int(observed) != expected_value:
        raise DerivationError(
            f"source electron_maxstep must be {expected_value}; observed {observed}"
        )
    derived_text = source_text[:start] + str(new_value) + source_text[end:]
    proof = semantic_compare_except_electron_maxstep(source_text, derived_text)
    if not proof["equivalent_except_electron_maxstep"]:
        raise DerivationError("semantic comparison failed after electron_maxstep derivation")
    if proof["derived_electron_maxstep"] != str(new_value):
        raise DerivationError("derived semantic electron_maxstep mismatch")

    derived_bytes = derived_text.encode("utf-8")
    if dest.exists():
        if dest.read_bytes() != derived_bytes:
            raise DerivationError(f"existing derived destination differs: {dest}")
        wrote = False
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{dest.name}.", suffix=".tmp", dir=str(dest.parent))
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(derived_bytes)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, dest)
        except Exception:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            raise
        wrote = True

    diff = "".join(
        difflib.unified_diff(
            source_text.splitlines(keepends=True),
            derived_text.splitlines(keepends=True),
            fromfile=str(source),
            tofile=str(dest),
        )
    )
    changed_lines = [line for line in diff.splitlines() if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))]
    if changed_lines != [f"-  electron_maxstep = {expected_value}", f"+  electron_maxstep = {new_value}"]:
        raise DerivationError("textual proof does not show only electron_maxstep value changed")

    return {
        "schema_version": "hipac26_qe_case_derivation_v1",
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "derived_path": str(dest),
        "derived_sha256": hashlib.sha256(derived_bytes).hexdigest(),
        "field": "electron_maxstep",
        "source_value": expected_value,
        "derived_value": new_value,
        "assignment_line": line_number,
        "bytes_changed_only_for_field": True,
        "destination_written": wrote,
        "semantic_comparison": proof,
        "unified_diff": diff,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="derive a bounded QE readiness input")
    parser.add_argument("--source", required=True)
    parser.add_argument("--dest", required=True)
    parser.add_argument("--expected-electron-maxstep", type=int, required=True)
    parser.add_argument("--new-electron-maxstep", type=int, required=True)
    parser.add_argument("--record-json")
    parser.add_argument("--diff-output")
    parser.add_argument("--semantic-output")
    args = parser.parse_args(argv)
    try:
        record = derive_electron_maxstep(
            source=Path(args.source),
            dest=Path(args.dest),
            expected_value=args.expected_electron_maxstep,
            new_value=args.new_electron_maxstep,
        )
        command = ["python3", "scripts/qe_case_derivation.py"] + sys.argv[1:]
        record["transformation_command"] = command
        if args.record_json:
            path = Path(args.record_json)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if args.diff_output:
            path = Path(args.diff_output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(record["unified_diff"], encoding="utf-8")
        if args.semantic_output:
            path = Path(args.semantic_output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record["semantic_comparison"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({k: record[k] for k in ("source_sha256", "derived_sha256", "bytes_changed_only_for_field")}, indent=2, sort_keys=True))
        return 0
    except DerivationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
