#!/usr/bin/env python3
"""Launcher-matched QE rank/GPU mapping validator.

This helper is controller-owned and is invoked by rank 0 of the production
``mpirun``-launched rank wrapper before any wrapper execs ``pw.x``.  It waits
for exactly the expected per-rank CUDA runtime records, validates physical GPU
identity uniqueness per node, and writes a fail-closed PASS/FAIL marker.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "hipac26_qe_launcher_mapping_v1"


class MappingValidationError(RuntimeError):
    pass


def _load_record(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:  # pragma: no cover - exact JSON error varies
        raise MappingValidationError(f"invalid mapping JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise MappingValidationError(f"mapping record root must be object: {path}")
    return data


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def wait_for_records(records_dir: Path, expected_ranks: int, timeout_seconds: int) -> list[Path]:
    deadline = time.monotonic() + timeout_seconds
    expected_names = {f"rank_{rank}.json" for rank in range(expected_ranks)}
    while True:
        present = {path.name for path in records_dir.glob("rank_*.json") if path.is_file()}
        if expected_names.issubset(present):
            return [records_dir / f"rank_{rank}.json" for rank in range(expected_ranks)]
        if time.monotonic() >= deadline:
            missing = sorted(expected_names - present)
            raise MappingValidationError(f"timeout waiting for mapping records; missing={missing}")
        time.sleep(0.2)


def validate_records(
    records: list[dict[str, Any]],
    *,
    expected_ranks: int,
    expected_nodes: int,
    expected_ranks_per_node: int,
    expected_gpus_per_node: int,
    expected_mpi_route_substrings: tuple[str, ...] = ("hpcx", "HPCX", "HPC-X", "nvhpc", "NVHPC", "x86-nvhpc"),
) -> dict[str, Any]:
    if len(records) != expected_ranks:
        raise MappingValidationError(f"wrong mapping record count: {len(records)} != {expected_ranks}")

    by_rank: dict[int, dict[str, Any]] = {}
    for record in records:
        if record.get("schema_version") != SCHEMA_VERSION:
            raise MappingValidationError("unsupported mapping record schema_version")
        rank = record.get("global_mpi_rank")
        if isinstance(rank, bool) or not isinstance(rank, int):
            raise MappingValidationError("global_mpi_rank must be integer")
        if rank in by_rank:
            raise MappingValidationError(f"duplicate global rank record: {rank}")
        by_rank[rank] = record

    expected_rank_set = set(range(expected_ranks))
    observed_rank_set = set(by_rank)
    if observed_rank_set != expected_rank_set:
        raise MappingValidationError(
            f"global rank set mismatch: observed={sorted(observed_rank_set)} expected={sorted(expected_rank_set)}"
        )

    by_host: dict[str, list[dict[str, Any]]] = {}
    for rank in range(expected_ranks):
        record = by_rank[rank]
        host = record.get("hostname")
        if not isinstance(host, str) or not host:
            raise MappingValidationError(f"rank {rank} missing hostname")
        by_host.setdefault(host, []).append(record)

        if record.get("cuda_runtime_visible_device_count") != 1:
            raise MappingValidationError(f"rank {rank} cudaGetDeviceCount() != 1")
        if record.get("selected_cuda_runtime_device_ordinal") != 0:
            raise MappingValidationError(f"rank {rank} selected CUDA ordinal must be 0")
        uuid = record.get("physical_gpu_uuid")
        pci = record.get("physical_gpu_pci_bus_id")
        if not isinstance(uuid, str) or not uuid.strip():
            raise MappingValidationError(f"rank {rank} missing physical GPU UUID")
        if not isinstance(pci, str) or not pci.strip():
            raise MappingValidationError(f"rank {rank} missing physical GPU PCI bus ID")
        route_identity = record.get("mpi_route_identity")
        if not isinstance(route_identity, str) or not any(token in route_identity for token in expected_mpi_route_substrings):
            raise MappingValidationError(f"rank {rank} MPI route is not approved NVHPC/HPC-X")
        wrapper_hash = record.get("wrapper_source_sha256")
        validator_hash = record.get("validator_sha256")
        if not isinstance(wrapper_hash, str) or len(wrapper_hash) != 64:
            raise MappingValidationError(f"rank {rank} missing wrapper hash")
        if not isinstance(validator_hash, str) or len(validator_hash) != 64:
            raise MappingValidationError(f"rank {rank} missing validator hash")

    if len(by_host) != expected_nodes:
        raise MappingValidationError(f"wrong node count: {len(by_host)} != {expected_nodes}")

    host_summaries: dict[str, dict[str, Any]] = {}
    for host, host_records in sorted(by_host.items()):
        if len(host_records) != expected_ranks_per_node:
            raise MappingValidationError(
                f"wrong ranks per node for {host}: {len(host_records)} != {expected_ranks_per_node}"
            )
        local_ranks = sorted(record.get("local_rank") for record in host_records)
        expected_local = list(range(expected_ranks_per_node))
        if local_ranks != expected_local:
            raise MappingValidationError(
                f"wrong local-rank set for {host}: observed={local_ranks} expected={expected_local}"
            )
        uuids = [record["physical_gpu_uuid"] for record in host_records]
        pcis = [record["physical_gpu_pci_bus_id"] for record in host_records]
        if len(set(uuids)) != len(uuids):
            raise MappingValidationError(f"duplicate physical GPU UUID on {host}")
        if len(set(pcis)) != len(pcis):
            raise MappingValidationError(f"duplicate physical GPU PCI bus ID on {host}")
        if len(set(uuids)) != expected_gpus_per_node:
            raise MappingValidationError(
                f"wrong physical GPU count on {host}: {len(set(uuids))} != {expected_gpus_per_node}"
            )
        host_summaries[host] = {
            "ranks": sorted(record["global_mpi_rank"] for record in host_records),
            "local_ranks": local_ranks,
            "physical_gpu_uuids": sorted(set(uuids)),
            "physical_gpu_pci_bus_ids": sorted(set(pcis)),
        }

    return {
        "schema_version": "hipac26_qe_mapping_validation_summary_v1",
        "classification": "PASS",
        "expected_global_rank_count": expected_ranks,
        "observed_global_rank_count": len(records),
        "expected_node_count": expected_nodes,
        "observed_node_count": len(by_host),
        "expected_ranks_per_node": expected_ranks_per_node,
        "expected_gpus_per_node": expected_gpus_per_node,
        "same_launcher_rank_wrapper": True,
        "cuda_runtime_visible_device_count_all_one": True,
        "physical_identity_present_all_ranks": True,
        "unique_physical_gpu_uuid_per_node": True,
        "unique_physical_gpu_pci_bus_id_per_node": True,
        "approved_nvhpc_hpcx_route": True,
        "hosts": host_summaries,
    }


def run_validation(args: argparse.Namespace) -> int:
    records_dir = Path(args.records_dir)
    result_dir = Path(args.result_dir)
    result_dir.mkdir(parents=True, exist_ok=True)
    summary_path = Path(args.summary_path) if args.summary_path else result_dir / "mapping_summary.json"
    try:
        paths = wait_for_records(records_dir, args.expected_ranks, args.timeout_seconds)
        records = [_load_record(path) for path in paths]
        summary = validate_records(
            records,
            expected_ranks=args.expected_ranks,
            expected_nodes=args.expected_nodes,
            expected_ranks_per_node=args.expected_ranks_per_node,
            expected_gpus_per_node=args.expected_gpus_per_node,
        )
        summary["validation_timestamp_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _atomic_write_json(summary_path, summary)
        _atomic_write_text(result_dir / "PASS", "PASS\n")
        return 0
    except Exception as exc:
        summary = {
            "schema_version": "hipac26_qe_mapping_validation_summary_v1",
            "classification": "FAIL",
            "reason": str(exc),
            "validation_timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        _atomic_write_json(summary_path, summary)
        _atomic_write_text(result_dir / "FAIL", "FAIL\n")
        print(f"mapping validation FAIL: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate launcher-matched QE rank/GPU mapping")
    parser.add_argument("--records-dir", required=True)
    parser.add_argument("--result-dir", required=True)
    parser.add_argument("--summary-path")
    parser.add_argument("--expected-ranks", required=True, type=int)
    parser.add_argument("--expected-nodes", required=True, type=int)
    parser.add_argument("--expected-ranks-per-node", required=True, type=int)
    parser.add_argument("--expected-gpus-per-node", required=True, type=int)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    return parser


def main(argv: list[str] | None = None) -> int:
    return run_validation(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
