#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Finalize QE smoke metadata after execution/parsing.")
    ap.add_argument("--metadata", required=True, type=Path)
    ap.add_argument("--parsed", required=True, type=Path)
    ap.add_argument("--qe-exit-code", required=True, type=int)
    args = ap.parse_args()

    meta = json.loads(args.metadata.read_text())
    parsed = json.loads(args.parsed.read_text()) if args.parsed.exists() else {}

    meta["qe_exit_code"] = args.qe_exit_code
    meta["slurm_exit_code"] = args.qe_exit_code
    meta["status"] = "finished"
    meta["finished_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    meta["failure_class"] = parsed.get("failure_class")
    meta["benchmark_valid"] = False
    meta["performance_claim_allowed"] = False
    meta["optimization_claim_allowed"] = False

    args.metadata.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
