#!/usr/bin/env python3

import argparse
import hashlib
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)

    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(
        description="Render an immutable standalone Slurm sweep bundle."
    )

    parser.add_argument("--source", required=True)
    parser.add_argument("--helper", required=True)
    parser.add_argument("--env-script", required=True)
    parser.add_argument("--parser", required=True)
    parser.add_argument("--collector", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--repo-head", required=True)

    args = parser.parse_args()

    source = Path(args.source).resolve()
    helper = Path(args.helper).resolve()
    env_script = Path(args.env_script).resolve()
    qe_parser = Path(args.parser).resolve()
    collector = Path(args.collector).resolve()
    parser_dependency = qe_parser.parent / "qe_convergence.py"
    output = Path(args.output_dir).resolve()
    temporary = Path(str(output) + ".tmp")

    required = [
        source,
        helper,
        env_script,
        qe_parser,
        collector,
        parser_dependency,
    ]

    for path in required:
        if not path.is_file():
            raise SystemExit(
                "ASSERTION_FAILED: missing source {}".format(path)
            )

    if output.exists() or temporary.exists():
        raise SystemExit(
            "ASSERTION_FAILED: output already exists: {}".format(output)
        )

    temporary.mkdir(parents=True)

    source_text = source.read_text(encoding="utf-8")
    helper_text = helper.read_text(encoding="utf-8")

    if helper_text.startswith("#!"):
        helper_text = "\n".join(helper_text.splitlines()[1:]) + "\n"

    # Runtime parser/collector paths are redirected to immutable bundle copies.
    helper_text = helper_text.replace(
        '"${REPO}/scripts/parse_qe_smoke.py"',
        '"${BUNDLE_ROOT}/parse_qe_smoke.py"',
    )
    helper_text = helper_text.replace(
        '"${REPO}/scripts/collect_g4x_sweep.py"',
        '"${BUNDLE_ROOT}/collect_g4x_sweep.py"',
    )

    environment_source = 'source "${REPO}/scripts/env/nvhpc259.sh"'

    environment_replacement = (
        'BUNDLE_ROOT="{}"\n'
        'source "${{BUNDLE_ROOT}}/nvhpc259.sh"'
    ).format(output)

    if environment_source not in source_text:
        raise SystemExit(
            "ASSERTION_FAILED: environment source marker not found"
        )

    source_text = source_text.replace(
        environment_source,
        environment_replacement,
        1,
    )

    helper_source_block = '''REPO_ROOT="${REPO}"
SWEEP_ROOT="${REPO_ROOT}/scripts/run/sweeps"
source "${SWEEP_ROOT}/lib/g4x_sweep_common.sh"
'''

    if helper_source_block not in source_text:
        raise SystemExit(
            "ASSERTION_FAILED: helper source block not found"
        )

    inline_block = (
        "# BEGIN INLINED G4X SWEEP IMPLEMENTATION\n"
        + helper_text
        + "# END INLINED G4X SWEEP IMPLEMENTATION\n"
    )

    source_text = source_text.replace(
        helper_source_block,
        inline_block,
        1,
    )

    generated_marker = (
        "# GENERATED_STANDALONE_SWEEP_BUNDLE\n"
        "# Runtime shell-helper dependency: none\n"
        "# Source repository HEAD: {}\n"
    ).format(args.repo_head)

    if source_text.startswith("#!/"):
        first_line, remainder = source_text.split("\n", 1)
        source_text = first_line + "\n" + generated_marker + remainder
    else:
        source_text = generated_marker + source_text

    forbidden = [
        'source "${SWEEP_ROOT}/lib/g4x_sweep_common.sh"',
        'git -C "$(dirname "${BASH_SOURCE[0]}")"',
        '"${REPO}/scripts/parse_qe_smoke.py"',
        '"${REPO}/scripts/collect_g4x_sweep.py"',
    ]

    for token in forbidden:
        if token in source_text:
            raise SystemExit(
                "ASSERTION_FAILED: forbidden runtime dependency remains: "
                + token
            )

    run_script = temporary / "run.sbatch"
    run_script.write_text(source_text, encoding="utf-8")
    os.chmod(run_script, 0o755)

    copies = [
        (source, temporary / "source-run.sbatch"),
        (helper, temporary / "source-g4x_sweep_common.sh"),
        (env_script, temporary / "nvhpc259.sh"),
        (qe_parser, temporary / "parse_qe_smoke.py"),
        (collector, temporary / "collect_g4x_sweep.py"),
        (parser_dependency, temporary / "qe_convergence.py"),
    ]

    for source_path, destination in copies:
        shutil.copy2(str(source_path), str(destination))

    os.chmod(temporary / "nvhpc259.sh", 0o755)
    os.chmod(temporary / "parse_qe_smoke.py", 0o755)
    os.chmod(temporary / "collect_g4x_sweep.py", 0o755)

    metadata = temporary / "bundle-metadata.txt"
    metadata.write_text(
        "\n".join([
            "bundle_schema=hipac26_qe_standalone_sweep_v1",
            "created_at={}".format(
                datetime.now(timezone.utc).astimezone().isoformat()
            ),
            "repo_head={}".format(args.repo_head),
            "source={}".format(source),
            "helper_source={}".format(helper),
            "env_source={}".format(env_script),
            "parser_source={}".format(qe_parser),
            "parser_dependency_source={}".format(parser_dependency),
            "collector_source={}".format(collector),
            "runtime_helper_dependency=none",
            "runtime_parser={}/parse_qe_smoke.py".format(output),
            "runtime_collector={}/collect_g4x_sweep.py".format(output),
            "",
        ]),
        encoding="utf-8",
    )

    hash_file = temporary / "SHA256SUMS"

    with hash_file.open("w", encoding="utf-8") as handle:
        for path in sorted(temporary.iterdir()):
            if path.name == "SHA256SUMS" or not path.is_file():
                continue

            handle.write(
                "{}  {}\n".format(
                    sha256(path),
                    path.name,
                )
            )

    temporary.rename(output)

    print("STANDALONE_BUNDLE={}".format(output))
    print("STANDALONE_RENDER=PASS")


if __name__ == "__main__":
    main()
