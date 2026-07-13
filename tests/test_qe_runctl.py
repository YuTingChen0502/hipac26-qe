import argparse
import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import qe_runctl  # noqa: E402
import qe_case_derivation  # noqa: E402
import qe_mapping_validator  # noqa: E402


HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64


def clone(value):
    return copy.deepcopy(value)


class QERunCtlTests(unittest.TestCase):
    def setUp(self):
        self.tmp_obj = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.tmp_obj.name)
        self.run_root = self.temp_root / "approved-runs"
        self.run_root.mkdir()
        self.config = qe_runctl.load_config()
        self.config = clone(self.config)
        self.config["paths"]["run_root"] = str(self.run_root)
        self.registry = qe_runctl.load_case_registry()
        self._render_counter = 0

    def tearDown(self):
        self.tmp_obj.cleanup()

    def write_json(self, root, name, data):
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def manifest_v2(self, job_kind="qe", *, nodes=2, gpus_per_node=1, npools=1, run_dir=None, run_root=None):
        total = nodes * gpus_per_node
        slurm = {
            "account": "ACD114087",
            "partition": "dev",
            "nodes": nodes,
            "ntasks": total,
            "ntasks_per_node": gpus_per_node,
            "cpus_per_task": 12,
            "gpus_per_node": gpus_per_node,
            "total_gpus": total,
            "gres": f"gpu:{gpus_per_node}",
            "time": "00:10:00",
        }
        job = {
            "config_id": "cfg001_test",
            "job_kind": job_kind,
            "run_dir": run_dir or str(self.run_root / "cfg001_test"),
            "slurm": slurm,
            "runtime": {"omp_num_threads": 12},
        }
        if job_kind == "environment_probe":
            job["probe_profile"] = "basic_environment"
        else:
            case = self.registry["cases"][0]
            input_path = (case.get("input") or {}).get("path") or "/tmp/hipac26-qe-test/input/typeA.in"
            input_sha = (case.get("input") or {}).get("sha256") or HEX_B
            pseudo_files = (case.get("pseudos") or {}).get("files") or ["/tmp/hipac26-qe-test/pseudo/Au.UPF"]
            pseudo_hashes = (case.get("pseudos") or {}).get("sha256") or {pseudo_files[0]: HEX_C}
            binary_identity = ((case.get("runtime_binaries") or {}).get("g1_production") or {})
            binary_path = binary_identity.get("path") or "/tmp/hipac26-qe-test/bin/pw.x"
            binary_sha = binary_identity.get("sha256") or HEX_A
            job.update(
                {
                    "case_id": "typeA-au111-manyk-emax5",
                    "runtime_role": "two_node_readiness_diagnostic",
                    "binary_path": binary_path,
                    "binary_sha256": binary_sha,
                    "input_path": input_path,
                    "input_sha256": input_sha,
                    "pseudo_paths": pseudo_files,
                    "pseudo_sha256": pseudo_hashes,
                }
            )
            job["runtime"].update({"npools": npools, "mpirun_np": total})
        return {
            "schema_version": qe_runctl.MANIFEST_V2,
            "trial_id": "P0B-T001",
            "autonomy_level": "L1",
            "benchmark_valid": False,
            "performance_claim_allowed": False,
            "optimization_claim_allowed": False,
            "approved_by_human": False,
            "allowed_submit": False,
            "max_retries": 0,
            "run_root": run_root or str(self.run_root),
            "jobs": [job],
        }

    def controller_config_patch(self):
        return mock.patch.object(qe_runctl, "load_config", return_value=self.config)

    def test_chatc_accepted_environment_flags_and_claim_guards(self):
        policy = qe_runctl.load_config()["policy"]
        self.assertTrue(policy["two_node_environment_verified"])
        self.assertFalse(policy["environment_probe_submit_enabled"])
        self.assertFalse(policy["two_node_qe_submit_enabled"])
        self.assertFalse(policy["benchmark_valid_default"])
        self.assertFalse(policy["performance_claim_allowed_default"])
        self.assertFalse(policy["optimization_claim_allowed_default"])

    def test_environment_flag_alone_cannot_bypass_qe_enablement(self):
        manifest = self.manifest_v2("qe", gpus_per_node=1, npools=1, run_dir=str(self.run_root / "qe_env_true_qe_disabled"))
        manifest["approved_by_human"] = True
        manifest["allowed_submit"] = True
        registry = self.verified_registry_for_manifest(manifest)
        config = clone(self.config)
        config["policy"]["two_node_environment_verified"] = True
        config["policy"]["two_node_qe_submit_enabled"] = False
        config["policy"]["environment_probe_submit_enabled"] = False
        self.assert_invalid(manifest, submit=True, config=config, registry=registry)

    def test_environment_probe_submission_remains_disabled(self):
        manifest = self.manifest_v2("environment_probe", gpus_per_node=1, run_dir=str(self.run_root / "probe_disabled"))
        manifest["approved_by_human"] = True
        manifest["allowed_submit"] = True
        config = clone(self.config)
        config["policy"]["environment_probe_submit_enabled"] = False
        self.assert_invalid(manifest, submit=True, config=config)

    def verified_registry_for_manifest(self, manifest):
        root = self.temp_root / "identity"
        root.mkdir(exist_ok=True)
        input_path = root / "verified.in"
        pseudo_path = root / "verified.UPF"
        binary_path = root / "pw.x"
        for path, text in [(input_path, "input"), (pseudo_path, "pseudo"), (binary_path, "binary")]:
            path.write_text(text, encoding="utf-8")
        input_hash = hashlib.sha256(input_path.read_bytes()).hexdigest()
        pseudo_hash = hashlib.sha256(pseudo_path.read_bytes()).hexdigest()
        binary_hash = hashlib.sha256(binary_path.read_bytes()).hexdigest()
        registry = clone(self.registry)
        registry["cases"] = [clone(self.registry["cases"][0])]
        registry["cases"][0].update(lifecycle="verified", qe_submit_eligible=True)
        registry["cases"][0]["input"] = {"path": str(input_path), "sha256": input_hash, "identity_status": "verified"}
        registry["cases"][0]["pseudos"] = {"files": [str(pseudo_path)], "sha256": {str(pseudo_path): pseudo_hash}, "identity_status": "verified"}
        registry["cases"][0]["runtime_binaries"] = {"g1_production": {"path": str(binary_path), "sha256": binary_hash, "identity_status": "verified_test"}}
        registry["cases"][0]["allowed_npools"] = [1]
        job = manifest["jobs"][0]
        job.update(binary_path=str(binary_path), binary_sha256=binary_hash, input_path=str(input_path), input_sha256=input_hash, pseudo_paths=[str(pseudo_path)], pseudo_sha256={str(pseudo_path): pseudo_hash})
        return registry

    def render_submit_ready_qe(self, tmp):
        self._render_counter += 1
        manifest = self.manifest_v2("qe", nodes=1, gpus_per_node=1, npools=1, run_dir=str(self.run_root / f"tamper_qe_{self._render_counter}"))
        manifest["approved_by_human"] = True
        manifest["allowed_submit"] = True
        registry = self.verified_registry_for_manifest(manifest)
        manifest_path = self.write_json(tmp, "qe_submit_ready.json", manifest)
        with self.controller_config_patch(), mock.patch.object(qe_runctl, "load_case_registry", return_value=registry):
            qe_runctl.cmd_render(argparse.Namespace(manifest=str(manifest_path), strict_files=False, no_overwrite=True))
        return manifest, manifest_path, registry

    def write_submit_permit(self, manifest_path, manifest, *, ledger_path=None, resources=None, trial_id=None):
        job = manifest["jobs"][0]
        permit = {
            "schema_version": qe_runctl.PERMIT_SCHEMA,
            "phase_identifier": "chatC_p2_readiness_recovery2",
            "trial_id": trial_id or manifest["trial_id"],
            "manifest_sha256": qe_runctl.sha256_file(Path(manifest_path)),
            "build_sha256": job.get("binary_sha256"),
            "input_sha256": job.get("input_sha256"),
            "pseudo_sha256": dict(sorted(job.get("pseudo_sha256", {}).items())),
            "resources": resources or job["slurm"],
            "maximum_attempts": 1,
            "ledger_path": str(ledger_path or (self.temp_root / "control" / "submission_ledger.json")),
        }
        return self.write_json(Path(manifest_path).parent, "permit_record.json", permit)

    def assert_tampered_submit_rejected_before_subprocess(self, manifest_path, registry=None, config=None):
        with mock.patch.object(qe_runctl.subprocess, "run", side_effect=AssertionError("subprocess forbidden")) as run_mock:
            with self.controller_config_patch(), mock.patch.object(qe_runctl, "load_case_registry", return_value=registry or self.registry):
                if config is not None:
                    with mock.patch.object(qe_runctl, "load_config", return_value=config):
                        with self.assertRaises(qe_runctl.RunCtlError):
                            qe_runctl.cmd_submit(argparse.Namespace(manifest=str(manifest_path), strict_files=False))
                else:
                    with self.assertRaises(qe_runctl.RunCtlError):
                        qe_runctl.cmd_submit(argparse.Namespace(manifest=str(manifest_path), strict_files=False))
            self.assertFalse(run_mock.called)

    def legacy_manifest(self, run_dir):
        return {
            "schema_version": "hipac26_qe_manifest_v1",
            "trial_id": "P0B-T001",
            "autonomy_level": "L1",
            "benchmark_valid": False,
            "approved_by_human": False,
            "allowed_submit": False,
            "max_retries": 0,
            "jobs": [
                {
                    "config_id": "cfg001_legacy",
                    "run_dir": str(run_dir),
                    "binary_path": "/tmp/legacy/pw.x",
                    "binary_sha256": HEX_A,
                    "input_path": "/tmp/legacy/in.in",
                    "input_sha256": HEX_B,
                    "pseudo_paths": ["/tmp/legacy/Au.UPF"],
                    "pseudo_sha256": {"/tmp/legacy/Au.UPF": HEX_C},
                    "slurm": {
                        "account": "ACD114087",
                        "partition": "dev",
                        "nodes": 1,
                        "ntasks": 1,
                        "cpus_per_task": 12,
                        "gres": "gpu:1",
                        "time": "00:10:00",
                    },
                    "runtime": {"omp_num_threads": 12, "npools": 1, "mpirun_np": 1},
                }
            ],
        }

    def assert_valid(self, manifest):
        qe_runctl.validate_manifest(
            manifest,
            submit_mode=False,
            strict_files=False,
            config=self.config,
            case_registry=self.registry,
        )

    def assert_invalid(self, manifest, *, submit=False, config=None, registry=None):
        with self.assertRaises(qe_runctl.RunCtlError):
            qe_runctl.validate_manifest(
                manifest,
                submit_mode=submit,
                strict_files=False,
                config=config or self.config,
                case_registry=registry or self.registry,
            )

    def add_profiler(self, manifest, *, ranks=None, enabled=True, required=True):
        job = manifest["jobs"][0]
        ranks = [0] if ranks is None else ranks
        job["profiler"] = {
            "profiler_required": required,
            "enabled": enabled,
            "route": "per_rank",
            "selected_global_ranks": ranks,
            "maximum_report_count": max(1, len(ranks)),
            "traces": ["cuda", "nvtx", "osrt", "mpi"],
            "output_root": str(Path(job["run_dir"]) / "profiles"),
            "require_readable_report": True,
            "require_stats": True,
            "require_cuda_activity": True,
        }
        return manifest

    def write_profile_success_artifacts(self, manifest, *, empty_report=False, missing_stats=False, missing_cuda=False, missing_nvtx=False, mapping_pass=True, qe_done=True):
        job = manifest["jobs"][0]
        metadata = qe_runctl.build_job_metadata(manifest, job)
        run_dir = Path(job["run_dir"])
        output_root = Path(job["profiler"]["output_root"])
        (run_dir / "mapping_raw").mkdir(parents=True, exist_ok=True)
        output_root.mkdir(parents=True, exist_ok=True)
        if mapping_pass:
            self.write_json(run_dir, "mapping_summary.json", {"classification": "PASS"})
        if qe_done:
            (run_dir / "qe.out").write_text("Program PWSCF\npw.x\nJOB DONE\n", encoding="utf-8")
            self.write_json(run_dir, "parsed.json", {"job_done": True})
        for rank in job["profiler"]["selected_global_ranks"]:
            host = f"n{rank}"
            self.write_json(run_dir / "mapping_raw", f"rank_{rank}.json", {"hostname": host})
            prefix = qe_runctl.profile_report_prefix(manifest["trial_id"], host, rank)
            report = output_root / f"{prefix}.nsys-rep"
            report.write_bytes(b"" if empty_report else b"fake report")
            if not missing_stats:
                stats = "Process,pw.x\n"
                stats += "CUDA,1\n" if not missing_cuda else "CUDA,0\n"
                stats += "NVTX,1\n" if not missing_nvtx else "NVTX,0\n"
                report.with_suffix(".stats.csv").write_text(stats, encoding="utf-8")
        return metadata

    def test_legacy_1node_manifest_and_render_compatible(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "legacy_run"
            manifest = self.legacy_manifest(run_dir)
            qe_runctl.validate_manifest(manifest, submit_mode=False, strict_files=False)
            path = self.write_json(tmp, "legacy.json", manifest)
            rc = qe_runctl.cmd_render(argparse.Namespace(manifest=str(path), strict_files=False, no_overwrite=True))
            self.assertEqual(rc, 0)
            script = (run_dir / "job.sh").read_text(encoding="utf-8")
            self.assertIn("QE_BIN", script)
            self.assertIn("qe.out", script)
            qe_runctl.validate_rendered_files(manifest)

    def test_v2_positive_np_shapes_validate_and_render(self):
        for gpn, npools in [(1, 1), (2, 1), (4, 1), (8, 1)]:
            with self.subTest(gpus_per_node=gpn), tempfile.TemporaryDirectory() as tmp:
                run_dir = self.run_root / f"qe_np{2*gpn}"
                manifest = self.manifest_v2("qe", gpus_per_node=gpn, npools=npools, run_dir=str(run_dir))
                self.assert_valid(manifest)
                script = qe_runctl.render_job_script(manifest["jobs"][0])
                self.assertIn(f"-np {2*gpn}", script)
                path = self.write_json(tmp, "manifest.json", manifest)
                with self.controller_config_patch():
                    self.assertEqual(qe_runctl.cmd_dry_run(argparse.Namespace(manifest=str(path), strict_files=False)), 0)
                self.assertFalse(run_dir.exists())
                with self.controller_config_patch():
                    self.assertEqual(qe_runctl.cmd_render(argparse.Namespace(manifest=str(path), strict_files=False, no_overwrite=True)), 0)
                    qe_runctl.validate_rendered_files(manifest, config=self.config)

    def test_launcher_matched_qe_route_contains_rank_wrapper_not_srun_probe(self):
        manifest = self.manifest_v2("qe", gpus_per_node=4, npools=1)
        script = qe_runctl.render_job_script(manifest["jobs"][0])
        self.assertIn("mpirun --bind-to none -np 8 --map-by ppr:4:node \"$RANK_WRAPPER_BIN\" > qe.out", script)
        self.assertIn("qe_rank_wrapper.cu", script)
        self.assertIn("qe_mapping_validator.py", script)
        self.assertIn("launcher_matched_rank_wrapper=true", script)
        self.assertIn("HIPAC_EXPECTED_RANKS_PER_NODE=4", script)
        self.assertNotRegex(script, r"\bsrun\b.*mapping")

    def test_per_rank_profiler_render_uses_mpirun_wrapper_not_outer_nsys(self):
        manifest = self.add_profiler(self.manifest_v2("qe", gpus_per_node=2, npools=1), ranks=[0, 3])
        self.assert_valid(manifest)
        script = qe_runctl.render_job_script(manifest["jobs"][0], manifest=manifest)
        self.assertIn("mpirun --bind-to none -np 4 --map-by ppr:2:node \"$RANK_WRAPPER_BIN\" > qe.out", script)
        self.assertNotRegex(script, r"nsys\s+profile.*mpirun")
        self.assertIn("HIPAC_PROFILE_ROUTE=per_rank", script)
        self.assertIn("HIPAC_PROFILE_SELECTED_GLOBAL_RANKS=0,3", script)
        wrapper = (REPO_ROOT / "scripts" / "qe_rank_wrapper.cu").read_text(encoding="utf-8")
        self.assertIn("wait_for_global_result(state_dir", wrapper)
        self.assertLess(wrapper.index("wait_for_global_result(state_dir"), wrapper.index("rank_selected_for_profile(rank)"))
        self.assertIn('exec_args[n++] = (char *)"profile";', wrapper)
        self.assertIn("execv(qe_bin, exec_args)", wrapper)
        self.assertIn("profiler report overwrite refused", wrapper)

    def test_profiler_manifest_schema_rejects_invalid_routes_and_ranks(self):
        cases = []
        m = self.add_profiler(self.manifest_v2("qe"), ranks=[]); cases.append(("enabled-no-ranks", m))
        m = self.add_profiler(self.manifest_v2("qe"), ranks=[0, 1, 2, 3, 4]); cases.append(("too-many", m))
        m = self.add_profiler(self.manifest_v2("qe"), ranks=[0, 0]); cases.append(("duplicate", m))
        m = self.add_profiler(self.manifest_v2("qe"), ranks=[2]); cases.append(("outside", m))
        m = self.add_profiler(self.manifest_v2("qe")); m["jobs"][0]["profiler"]["route"] = "outer_mpirun"; cases.append(("outer", m))
        m = self.add_profiler(self.manifest_v2("qe")); m["jobs"][0]["profiler"]["output_root"] = str(self.run_root.parent / "evil"); cases.append(("outside-root", m))
        m = self.add_profiler(self.manifest_v2("qe"), enabled=False, required=True); cases.append(("required-disabled", m))
        m = self.add_profiler(self.manifest_v2("qe")); m["jobs"][0]["profiler"]["traces"] = ["cuda", "shell"]; cases.append(("trace-injection", m))
        for name, manifest in cases:
            with self.subTest(name=name):
                self.assert_invalid(manifest)

    def test_profiler_recovery_cannot_remove_or_weaken_required_profile(self):
        manifest = self.add_profiler(self.manifest_v2("qe"))
        before = manifest["jobs"][0]
        after = clone(before)
        after.pop("profiler")
        with self.assertRaises(qe_runctl.RunCtlError):
            qe_runctl.validate_profiler_recovery_invariants(before, after)
        after = clone(before)
        after["profiler"]["enabled"] = False
        with self.assertRaises(qe_runctl.RunCtlError):
            qe_runctl.validate_profiler_recovery_invariants(before, after)

    def test_render_expands_environment_identity_paths_for_runtime_shell(self):
        manifest = self.manifest_v2("qe", gpus_per_node=1, npools=1)
        job = manifest["jobs"][0]
        job["binary_path"] = "/work/$USER/example/bin/app"
        job["input_path"] = "/work/$USER/example/input.in"
        job["pseudo_paths"] = ["/work/$USER/example/Au.UPF"]
        job["pseudo_sha256"] = {"/work/$USER/example/Au.UPF": HEX_C}
        script = qe_runctl.render_job_script(job)
        self.assertIn(f"/work/{os.environ.get('USER')}/example/bin/app", script)
        self.assertIn(f"/work/{os.environ.get('USER')}/example/input.in", script)
        self.assertIn(f"/work/{os.environ.get('USER')}/example/Au.UPF", script)
        self.assertNotIn("'/work/$USER/example", script)

    def test_manifest_cannot_inject_different_wrapper(self):
        manifest = self.manifest_v2("qe", gpus_per_node=1, npools=1)
        manifest["jobs"][0]["runtime"]["rank_wrapper"] = "/tmp/evil.sh"
        self.assert_invalid(manifest)

    def test_future_2node_16gpu_shape_validates_and_renders(self):
        manifest = self.manifest_v2("qe", gpus_per_node=8, npools=1)
        self.assert_valid(manifest)
        script = qe_runctl.render_job_script(manifest["jobs"][0])
        self.assertIn("#SBATCH -p dev", script)
        self.assertIn("#SBATCH -N 2", script)
        self.assertIn("#SBATCH --ntasks=16", script)
        self.assertIn("#SBATCH --gres=gpu:8", script)

    def test_controlled_probe_template_validates_renders_dry_runs_and_blocks_submit(self):
        template = qe_runctl.read_json(REPO_ROOT / "config" / "manifests" / "p0b_2node_probe.template.json")
        self.assertFalse(template["approved_by_human"])
        self.assertFalse(template["allowed_submit"])
        qe_runctl.validate_manifest(
            template,
            submit_mode=False,
            strict_files=False,
            config=qe_runctl.load_config(),
            case_registry=self.registry,
        )
        script = qe_runctl.render_job_script(template["jobs"][0])
        for token in ["probe_kind=environment_probe", "hostname", "srun", "mpirun --bind-to none", "MPI_Allreduce", "--gpus-per-task=1", "taskset -pc $$", "cudaGetDeviceCount", "cuda_runtime_visible_device_count"]:
            self.assertIn(token, script)
        for token in ["QE_BIN", "QE_INPUT", "mpiexec", "qe.out", " -in "]:
            self.assertNotIn(token, script)
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_json(tmp, "probe.json", template)
            with mock.patch.object(qe_runctl.subprocess, "run", side_effect=AssertionError("subprocess forbidden")):
                self.assertEqual(qe_runctl.cmd_dry_run(argparse.Namespace(manifest=str(path), strict_files=False)), 0)
            self.assertFalse(Path(os.path.expandvars(template["jobs"][0]["run_dir"])).exists())
        blocked = clone(template)
        blocked["approved_by_human"] = True
        blocked["allowed_submit"] = True
        self.assert_invalid(blocked, submit=True)

    def test_2node_qe_validate_render_dry_run_but_submit_hard_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.manifest_v2("qe", gpus_per_node=8, npools=1, run_dir=str(self.run_root / "qe16"))
            self.assert_valid(manifest)
            path = self.write_json(tmp, "qe.json", manifest)
            with self.controller_config_patch():
                self.assertEqual(qe_runctl.cmd_dry_run(argparse.Namespace(manifest=str(path), strict_files=False)), 0)
            submit_manifest = clone(manifest)
            submit_manifest["approved_by_human"] = True
            submit_manifest["allowed_submit"] = True
            self.assert_invalid(submit_manifest, submit=True)
            submit_path = self.write_json(tmp, "qe_submit.json", submit_manifest)
            with mock.patch.object(qe_runctl.subprocess, "run", side_effect=AssertionError("subprocess forbidden")):
                with self.controller_config_patch():
                    with self.assertRaises(qe_runctl.RunCtlError):
                        qe_runctl.cmd_submit(argparse.Namespace(manifest=str(submit_path), strict_files=False))

    def test_negative_resource_and_policy_matrix(self):
        cases = []
        def add(name, mutator):
            m = self.manifest_v2("qe", gpus_per_node=8, npools=1)
            mutator(m)
            cases.append((name, m))
        add("unauthorized account", lambda m: m["jobs"][0]["slurm"].update(account="BAD000000"))
        add("forbidden account", lambda m: m["jobs"][0]["slurm"].update(account="ACD115059"))
        add("account partition mismatch", lambda m: m["jobs"][0]["slurm"].update(account="GOV114009"))
        mismatch_config = clone(self.config)
        mismatch_config["partitions"]["dev"]["authorized_accounts"] = ["ACD114087"]
        add("partition GPU minimum", lambda m: m["jobs"][0]["slurm"].update(partition="16gpus", ntasks=2, ntasks_per_node=1, gpus_per_node=1, total_gpus=2, gres="gpu:1"))
        add("partition GPU ceiling", lambda m: m["jobs"][0]["slurm"].update(partition="64gpus"))
        low_ceiling_config = clone(self.config)
        low_ceiling_config["partitions"]["dev"]["maximum_total_gpus_by_account"]["ACD114087"] = 8
        add("walltime", lambda m: m["jobs"][0]["slurm"].update(time="3-00:00:00"))
        add("nodes tasks mismatch", lambda m: m["jobs"][0]["slurm"].update(ntasks=15))
        add("gpu total mismatch", lambda m: m["jobs"][0]["slurm"].update(total_gpus=15))
        add("gpu capacity", lambda m: m["jobs"][0]["slurm"].update(gpus_per_node=9, gres="gpu:9", ntasks_per_node=9, ntasks=18, total_gpus=18))
        add("CPU TRES", lambda m: m["jobs"][0]["slurm"].update(cpus_per_task=14))
        add("CPU per GPU", lambda m: m["jobs"][0]["slurm"].update(cpus_per_task=13))
        add("gres inconsistency", lambda m: m["jobs"][0]["slurm"].update(gres="gpu:7"))
        add("missing per-node", lambda m: m["jobs"][0]["slurm"].pop("ntasks_per_node"))
        add("ambiguous shape", lambda m: m["jobs"][0]["slurm"].update(gpus=16))
        add("mpirun mismatch", lambda m: m["jobs"][0]["runtime"].update(mpirun_np=8))
        add("invalid npools", lambda m: m["jobs"][0]["runtime"].update(npools=0))
        add("npools greater", lambda m: m["jobs"][0]["runtime"].update(npools=17))
        add("npools indivisible", lambda m: m["jobs"][0]["runtime"].update(npools=3))
        add("case disallowed npools", lambda m: m["jobs"][0]["runtime"].update(npools=2, mpirun_np=16))
        add("duplicate config", lambda m: m["jobs"].append(clone(m["jobs"][0])))
        add("duplicate run_dir", lambda m: (m["jobs"].append(clone(m["jobs"][0])), m["jobs"][1].update(config_id="cfg002_test", run_dir="/tmp//hipac26-qe-test-run/cfg001_test")))
        add("relative paths", lambda m: m["jobs"][0].update(run_dir="relative/run"))
        add("path aliases", lambda m: m["jobs"][0].update(run_dir="/tmp/hipac26/../run"))
        add("unknown case", lambda m: m["jobs"][0].update(case_id="unknown-case"))
        add("blocked case", lambda m: m["jobs"][0].update(case_id="official-scale-unfrozen", runtime_role="official_representative_scale"))
        add("unapproved role", lambda m: m["jobs"][0].update(runtime_role="longer_stabilization"))
        add("input path mismatch", lambda m: m["jobs"][0].update(case_id="verified-case", runtime_role="verified_role", input_path="/tmp/wrong.in"))
        add("input hash mismatch", lambda m: m["jobs"][0].update(case_id="verified-case", runtime_role="verified_role", input_path="/tmp/verified.in", input_sha256=HEX_A))
        add("pseudo path mismatch", lambda m: m["jobs"][0].update(case_id="verified-case", runtime_role="verified_role", input_path="/tmp/verified.in", input_sha256=HEX_B, pseudo_paths=["/tmp/wrong.UPF"], pseudo_sha256={"/tmp/wrong.UPF": HEX_C}))
        add("pseudo hash mismatch", lambda m: m["jobs"][0].update(case_id="verified-case", runtime_role="verified_role", input_path="/tmp/verified.in", input_sha256=HEX_B, pseudo_paths=["/tmp/verified.UPF"], pseudo_sha256={"/tmp/verified.UPF": HEX_A}))

        verified_registry = clone(self.registry)
        verified_registry["cases"].append({
            "case_id": "verified-case",
            "display_name": "Verified test case",
            "case_family": "test",
            "role": "two_node_readiness_diagnostic",
            "lifecycle": "verified",
            "selected": True,
            "separate_workload": False,
            "qe_submit_eligible": True,
            "approved_runtime_roles": ["verified_role"],
            "input": {"path": "/tmp/verified.in", "sha256": HEX_B, "identity_status": "verified"},
            "pseudos": {"files": ["/tmp/verified.UPF"], "sha256": {"/tmp/verified.UPF": HEX_C}, "identity_status": "verified"},
            "blocked_reason": None,
            "notes": "test only",
        })

        for name, manifest in cases:
            with self.subTest(name=name):
                if name == "account partition mismatch":
                    self.assert_invalid(manifest, config=mismatch_config)
                elif name == "account GPU ceiling":
                    self.assert_invalid(manifest, config=low_ceiling_config)
                elif "mismatch" in name and name not in {"mpirun mismatch", "nodes tasks mismatch", "gpu total mismatch", "gres inconsistency"}:
                    self.assert_invalid(manifest, registry=verified_registry)
                else:
                    self.assert_invalid(manifest)

        ceiling_manifest = self.manifest_v2("qe", gpus_per_node=8, npools=1)
        self.assert_invalid(ceiling_manifest, config=low_ceiling_config)

    def test_negative_submit_claim_case_and_probe_routes(self):
        for field in ["benchmark_valid", "performance_claim_allowed", "optimization_claim_allowed"]:
            m = self.manifest_v2("qe")
            m[field] = True
            with self.subTest(field=field):
                self.assert_invalid(m)
        m = self.manifest_v2("qe"); m["max_retries"] = 1; self.assert_invalid(m)
        m = self.manifest_v2("qe"); m["approved_by_human"] = "yes"; self.assert_invalid(m)
        m = self.manifest_v2("qe"); m["approved_by_human"] = False; m["allowed_submit"] = False; self.assert_invalid(m, submit=True)
        m = self.manifest_v2("qe"); m["approved_by_human"] = True; m["allowed_submit"] = False; self.assert_invalid(m, submit=True)
        m = self.manifest_v2("qe"); m["approved_by_human"] = True; m["allowed_submit"] = True; self.assert_invalid(m, submit=True)
        m = self.manifest_v2("qe", nodes=1, gpus_per_node=1, npools=1); m["approved_by_human"] = True; m["allowed_submit"] = True; self.assert_invalid(m, submit=True)
        m = self.manifest_v2("qe"); m["schema_version"] = "hipac26_qe_manifest_v22"; self.assert_invalid(m)
        m = self.manifest_v2("environment_probe"); m["jobs"][0]["binary_path"] = "/tmp/pw.x"; self.assert_invalid(m)
        with tempfile.TemporaryDirectory() as tmp:
            probe = self.manifest_v2("environment_probe", gpus_per_node=8, run_dir=str(self.run_root / "probe"))
            path = self.write_json(tmp, "probe.json", probe)
            submit_probe = clone(probe)
            submit_probe["approved_by_human"] = True
            submit_probe["allowed_submit"] = True
            submit_probe_path = self.write_json(tmp, "submit_probe.json", submit_probe)
            with mock.patch.object(qe_runctl.subprocess, "run", side_effect=AssertionError("subprocess forbidden")):
                with self.controller_config_patch():
                    with self.assertRaises(qe_runctl.RunCtlError):
                        qe_runctl.cmd_submit(argparse.Namespace(manifest=str(submit_probe_path), strict_files=False))
            with self.assertRaises(qe_runctl.RunCtlError):
                qe_runctl.cmd_parse(argparse.Namespace(manifest=str(path), allow_missing=True))
            with self.assertRaises(qe_runctl.RunCtlError):
                qe_runctl.cmd_summarize(argparse.Namespace(manifest=str(path), output=str(Path(tmp) / "summary.json")))

    def test_existing_run_directory_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self.run_root / "exists"
            run_dir.mkdir()
            manifest = self.manifest_v2("environment_probe", gpus_per_node=8, run_dir=str(run_dir))
            path = self.write_json(tmp, "probe.json", manifest)
            with self.controller_config_patch():
                with self.assertRaises(qe_runctl.RunCtlError):
                    qe_runctl.cmd_render(argparse.Namespace(manifest=str(path), strict_files=False, no_overwrite=True))

    def test_rendered_artifact_tamper_matrix_rejected_before_subprocess(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, manifest_path, registry = self.render_submit_ready_qe(tmp)
            run_dir = Path(manifest["jobs"][0]["run_dir"])

            with self.subTest("append QE command"):
                (run_dir / "job.sh").write_text((run_dir / "job.sh").read_text(encoding="utf-8") + "\necho tampered\n", encoding="utf-8")
                self.assert_tampered_submit_rejected_before_subprocess(manifest_path, registry=registry)

    def mapping_record(self, rank, host, local_rank, uuid=None, pci=None, count=1):
        return {
            "schema_version": qe_mapping_validator.SCHEMA_VERSION,
            "hostname": host,
            "global_mpi_rank": rank,
            "local_rank": local_rank,
            "mpi_world_size": 4,
            "SLURM_PROCID": str(rank),
            "SLURM_LOCALID": str(local_rank),
            "CUDA_VISIBLE_DEVICES": str(local_rank),
            "cuda_runtime_visible_device_count": count,
            "selected_cuda_runtime_device_ordinal": 0,
            "physical_gpu_pci_bus_id": pci or f"0000:{local_rank + 1:02x}:00.0",
            "physical_gpu_uuid": uuid or f"GPU-{host}-{local_rank}",
            "timestamp_utc": "2026-01-01T00:00:00Z",
            "wrapper_version": "qe_rank_wrapper_v1",
            "wrapper_source_sha256": HEX_A,
            "validator_sha256": HEX_B,
            "mpi_route_identity": "/opt/nvhpc/hpcx/bin/mpirun NVHPC",
        }

    def valid_mapping_records(self):
        return [
            self.mapping_record(0, "n1", 0),
            self.mapping_record(1, "n1", 1),
            self.mapping_record(2, "n2", 0),
            self.mapping_record(3, "n2", 1),
        ]

    def assert_mapping_invalid(self, records, **kwargs):
        params = dict(expected_ranks=4, expected_nodes=2, expected_ranks_per_node=2, expected_gpus_per_node=2)
        params.update(kwargs)
        with self.assertRaises(qe_mapping_validator.MappingValidationError):
            qe_mapping_validator.validate_records(records, **params)

    def test_global_mapping_aggregation_positive_and_negative_matrix(self):
        records = self.valid_mapping_records()
        summary = qe_mapping_validator.validate_records(
            records,
            expected_ranks=4,
            expected_nodes=2,
            expected_ranks_per_node=2,
            expected_gpus_per_node=2,
        )
        self.assertEqual(summary["classification"], "PASS")

        cases = []
        r = clone(records); r[0]["cuda_runtime_visible_device_count"] = 2; cases.append(("cuda-count", r, {}))
        r = clone(records); r[0]["physical_gpu_uuid"] = ""; cases.append(("missing-uuid", r, {}))
        r = clone(records); r[0]["physical_gpu_pci_bus_id"] = ""; cases.append(("missing-pci", r, {}))
        r = clone(records); r[1]["physical_gpu_uuid"] = r[0]["physical_gpu_uuid"]; cases.append(("duplicate-uuid", r, {}))
        r = clone(records); r[1]["physical_gpu_pci_bus_id"] = r[0]["physical_gpu_pci_bus_id"]; cases.append(("duplicate-pci", r, {}))
        r = clone(records); r[3]["hostname"] = "n3"; cases.append(("wrong-node-count", r, {}))
        r = clone(records); r[1]["local_rank"] = 0; cases.append(("wrong-local-ranks", r, {}))
        r = clone(records[:-1]); cases.append(("missing-rank-record", r, {}))
        r = clone(records); r[0]["mpi_route_identity"] = "/usr/bin/mpirun"; cases.append(("bad-route", r, {}))

        for name, bad_records, kw in cases:
            with self.subTest(name=name):
                self.assert_mapping_invalid(bad_records, **kw)

    def test_mapping_wait_timeout_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(qe_mapping_validator.MappingValidationError):
                qe_mapping_validator.wait_for_records(Path(tmp), expected_ranks=1, timeout_seconds=0)

    def test_profiler_acceptance_json_positive_and_negative_matrix(self):
        manifest = self.add_profiler(self.manifest_v2("qe", gpus_per_node=2, npools=1), ranks=[0, 3])
        metadata = self.write_profile_success_artifacts(manifest)
        result = qe_runctl.profile_acceptance_from_metadata(metadata, generate_stats=False)
        self.assertTrue(result["acceptance"])
        self.assertEqual(result["expected_report_count"], 2)
        self.assertEqual(result["observed_report_count"], 2)
        for key in ("reports_nonempty", "reports_readable", "stats_generated", "pw_process_observed", "cuda_activity_observed", "nvtx_activity_observed", "mapping_pass", "qe_job_done"):
            self.assertTrue(result[key], key)
        self.assertEqual(len(result["reports"]), 2)
        self.assertTrue(all(record["sha256"] for record in result["reports"]))

        negative_cases = {
            "missing-report": {},
            "empty-report": {"empty_report": True},
            "unreadable-report": {},
            "missing-stats": {"missing_stats": True},
            "missing-cuda": {"missing_cuda": True},
            "missing-nvtx": {"missing_nvtx": True},
            "missing-mapping-pass": {"mapping_pass": False},
            "missing-qe-done": {"qe_done": False},
        }
        for name, kwargs in negative_cases.items():
            with self.subTest(name=name):
                m = self.add_profiler(self.manifest_v2("qe", gpus_per_node=2, npools=1, run_dir=str(self.run_root / name)), ranks=[0])
                md = self.write_profile_success_artifacts(m, **kwargs)
                if name == "missing-report":
                    for report in Path(m["jobs"][0]["profiler"]["output_root"]).glob("*.nsys-rep"):
                        report.unlink()
                if name == "unreadable-report":
                    for report in Path(m["jobs"][0]["profiler"]["output_root"]).glob("*.nsys-rep"):
                        report.unlink()
                        report.mkdir()
                out = qe_runctl.profile_acceptance_from_metadata(md, generate_stats=False)
                self.assertFalse(out["acceptance"])

    def test_bare_g1p_job_cannot_satisfy_profiler_required_stage(self):
        manifest = self.manifest_v2("qe", run_dir=str(self.run_root / "bare_g1p"))
        metadata = qe_runctl.build_job_metadata(manifest, manifest["jobs"][0])
        run_dir = Path(manifest["jobs"][0]["run_dir"])
        run_dir.mkdir(parents=True)
        (run_dir / "qe.out").write_text("JOB DONE\n", encoding="utf-8")
        result = qe_runctl.profile_acceptance_from_metadata(metadata, generate_stats=False)
        self.assertFalse(result["profiler_required"])
        self.assertFalse(result["acceptance"])

        with tempfile.TemporaryDirectory() as tmp:
            manifest, manifest_path, registry = self.render_submit_ready_qe(tmp)
            run_dir = Path(manifest["jobs"][0]["run_dir"])
            with self.subTest("change Slurm directive"):
                text = (run_dir / "job.sh").read_text(encoding="utf-8").replace("#SBATCH --ntasks=1", "#SBATCH --ntasks=2")
                (run_dir / "job.sh").write_text(text, encoding="utf-8")
                self.assert_tampered_submit_rejected_before_subprocess(manifest_path, registry=registry)

        with tempfile.TemporaryDirectory() as tmp:
            manifest, manifest_path, registry = self.render_submit_ready_qe(tmp)
            run_dir = Path(manifest["jobs"][0]["run_dir"])
            with self.subTest("alter metadata resource"):
                metadata = qe_runctl.read_json(run_dir / "metadata.json")
                metadata["slurm"]["ntasks"] = 2
                self.write_json(run_dir, "metadata.json", metadata)
                self.assert_tampered_submit_rejected_before_subprocess(manifest_path, registry=registry)

        with tempfile.TemporaryDirectory() as tmp:
            manifest, manifest_path, registry = self.render_submit_ready_qe(tmp)
            run_dir = Path(manifest["jobs"][0]["run_dir"])
            with self.subTest("job symlink"):
                (run_dir / "job.sh").unlink()
                os.symlink(run_dir / "metadata.json", run_dir / "job.sh")
                self.assert_tampered_submit_rejected_before_subprocess(manifest_path, registry=registry)

        with tempfile.TemporaryDirectory() as tmp:
            manifest, manifest_path, registry = self.render_submit_ready_qe(tmp)
            run_dir = Path(manifest["jobs"][0]["run_dir"])
            with self.subTest("metadata symlink"):
                (run_dir / "metadata.json").unlink()
                os.symlink(run_dir / "job.sh", run_dir / "metadata.json")
                self.assert_tampered_submit_rejected_before_subprocess(manifest_path, registry=registry)

    def test_environment_probe_tamper_rejected_before_subprocess(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = clone(self.config)
            config["policy"]["environment_probe_submit_enabled"] = True
            manifest = self.manifest_v2("environment_probe", gpus_per_node=8, run_dir=str(self.run_root / "tamper_probe"))
            manifest["approved_by_human"] = True
            manifest["allowed_submit"] = True
            manifest_path = self.write_json(tmp, "probe_submit_ready.json", manifest)
            with mock.patch.object(qe_runctl, "load_config", return_value=config):
                qe_runctl.cmd_render(argparse.Namespace(manifest=str(manifest_path), strict_files=False, no_overwrite=True))
            run_dir = Path(manifest["jobs"][0]["run_dir"])
            (run_dir / "job.sh").write_text((run_dir / "job.sh").read_text(encoding="utf-8") + "\necho probe-tampered\n", encoding="utf-8")
            self.assert_tampered_submit_rejected_before_subprocess(manifest_path, config=config)

    def test_v2_run_root_containment_matrix(self):
        valid = self.manifest_v2("qe")
        self.assert_valid(valid)
        cases = []
        m = self.manifest_v2("qe"); m.pop("run_root"); cases.append(("missing", m, self.config))
        m = self.manifest_v2("qe"); m["run_root"] = "relative/runs"; cases.append(("relative", m, self.config))
        m = self.manifest_v2("qe"); m["run_root"] = str(self.run_root / "../approved-runs"); cases.append(("dotdot", m, self.config))
        m = self.manifest_v2("qe"); m["run_root"] = str(self.run_root).replace("/", "//", 1); cases.append(("repeated", m, self.config))
        m = self.manifest_v2("qe"); m["jobs"][0]["run_dir"] = str(self.run_root.parent / (self.run_root.name + "-evil") / "job"); cases.append(("sibling-prefix", m, self.config))
        m = self.manifest_v2("qe"); m["jobs"][0]["run_dir"] = str(self.run_root); cases.append(("not-strict", m, self.config))
        repo_config = clone(self.config)
        repo_config["paths"]["run_root"] = str(REPO_ROOT / "bad-runs")
        m = self.manifest_v2("qe", run_root=repo_config["paths"]["run_root"], run_dir=str(REPO_ROOT / "bad-runs" / "job")); cases.append(("repo-contained", m, repo_config))
        target = self.temp_root / "symlink-target"
        target.mkdir()
        link = self.run_root / "symlink-parent"
        os.symlink(target, link)
        m = self.manifest_v2("qe", run_dir=str(link / "job")); cases.append(("symlink-parent", m, self.config))
        for name, manifest, config in cases:
            with self.subTest(name=name):
                self.assert_invalid(manifest, config=config)

    def test_p1a_probe_renderer_static_checks(self):
        template = qe_runctl.read_json(REPO_ROOT / "config" / "manifests" / "p0b_2node_probe.template.json")
        script = qe_runctl.render_job_script(template["jobs"][0], manifest=template, config=qe_runctl.load_config())
        lines = script.splitlines()
        first_body = next(i for i, line in enumerate(lines) if line and not line.startswith("#"))
        self.assertEqual(lines[first_body], "set -euo pipefail")
        self.assertTrue(any(line.startswith("#SBATCH -A ACD114087") for line in lines[1:first_body]))
        self.assertTrue(any(line.startswith("#SBATCH -p 16gpus") for line in lines[1:first_body]))
        required = [
            "allocation_nodelist", "SLURM_JOB_ID", "SLURM_NNODES", "SLURM_NODEID",
            "SLURM_PROCID", "SLURM_LOCALID", "task_hostname", "EXPECTED_TASKS",
            "taskset -pc $$", "Cpus_allowed_list", "SLURM_CPU_BIND",
            "--gpus-per-task=1", "CUDA_VISIBLE_DEVICES", "p1a_t001_cuda_probe.cu",
            "cuda_runtime_visible_device_count", "cuda_selected_visible_device_ordinal",
            "cuda_visible_gpu_uuid", "cuda_visible_gpu_pci_bus_id",
            "p1a_t001_shared_fs_marker.txt",
            "sha256sum \"${PROBE_MARKER}\"", "environment_snapshot.txt", "module_snapshot.txt",
            "resolved_mpirun", "resolved_mpicc", "realpath_mpirun", "realpath_mpicc",
            "mpirun --version", "mpicc --showme:link", "ldd \"$MPIRUN_REALPATH\"",
            "MPI_Allreduce", "mpirun --bind-to none -np 16", "rank_count", "node_count",
            "CONFIGURED_BINARY_PATH", "ACCEPTED_G1_SMOKE_PATH", "sha256sum \"$target\"",
            "binary_identity_status=accepted_g1_production_binary_no_performance_claim",
        ]
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, script)
        for forbidden in ["QE_BIN", "QE_INPUT", "qe.out", " -in "]:
            self.assertNotIn(forbidden, script)

        recovery = clone(template)
        recovery["trial_id"] = "P1A-R001"
        qe_runctl.validate_manifest(
            recovery,
            submit_mode=False,
            strict_files=False,
            config=qe_runctl.load_config(),
            case_registry=self.registry,
        )
        recovery_script = qe_runctl.render_job_script(
            recovery["jobs"][0],
            manifest=recovery,
            config=qe_runctl.load_config(),
        )
        self.assertIn("trial=P1A-R001", recovery_script)

    def test_environment_snapshot_is_allowlisted_and_secret_safe(self):
        template = qe_runctl.read_json(REPO_ROOT / "config" / "manifests" / "p0b_2node_probe.template.json")
        script = qe_runctl.render_job_script(template["jobs"][0], manifest=template, config=qe_runctl.load_config())
        self.assertNotIn("env | sort", script)
        for token in ["safe_env_name_allowed", "environment_snapshot.txt", "PATH LD_LIBRARY_PATH MODULEPATH", "CUDA_VISIBLE_DEVICES", "SLURM_PROCID", "OMPI_", "PMIX_", "UCX_", "NVHPC_"]:
            with self.subTest(token=token):
                self.assertIn(token, script)
        for secret_name in ["MY_SECRET_TOKEN", "PASSWORD", "PASSWD", "API_KEY", "PRIVATE_KEY", "CREDENTIAL", "AUTH_HEADER"]:
            with self.subTest(secret_name=secret_name):
                self.assertNotIn(f"{secret_name}=", script)

    def test_mpi_route_validation_requires_nvhpc_or_hpcx_identity(self):
        template = qe_runctl.read_json(REPO_ROOT / "config" / "manifests" / "p0b_2node_probe.template.json")
        script = qe_runctl.render_job_script(template["jobs"][0], manifest=template, config=qe_runctl.load_config())
        self.assertIn("MPI_ROUTE_IDENTITY", script)
        self.assertIn("realpath_mpirun", script)
        self.assertIn("realpath_mpicc", script)
        self.assertIn("approved NVHPC/HPC-X", script)
        self.assertNotIn("*openmpi*|*OpenMPI*", script)

    def test_single_authoritative_environment_probe_renderer(self):
        source = (REPO_ROOT / "scripts" / "qe_runctl.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("def render_environment_probe_script("), 1)

    def test_production_submit_command_is_fixed_sbatch(self):
        with mock.patch.dict(os.environ, {"HIPAC_SUBMIT_CMD": "bash"}):
            self.assertEqual(qe_runctl.production_submit_command(), "sbatch")
        for attempted in ["bash", "sh", sys.executable, "python3", "/tmp/fake_sbatch"]:
            with self.subTest(attempted=attempted), mock.patch.dict(os.environ, {"HIPAC_SUBMIT_CMD": attempted}):
                self.assertEqual(qe_runctl.production_submit_command(), "sbatch")

    def test_fake_submit_isolation_uses_patched_subprocess_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "verified.in"
            pseudo_path = root / "verified.UPF"
            binary_path = root / "pw.x"
            for path, text in [(input_path, "input"), (pseudo_path, "pseudo"), (binary_path, "binary")]:
                path.write_text(text, encoding="utf-8")
            input_hash = hashlib.sha256(input_path.read_bytes()).hexdigest()
            pseudo_hash = hashlib.sha256(pseudo_path.read_bytes()).hexdigest()
            binary_hash = hashlib.sha256(binary_path.read_bytes()).hexdigest()
            registry = clone(self.registry)
            registry["cases"] = [clone(self.registry["cases"][0])]
            registry["cases"][0].update(lifecycle="verified", qe_submit_eligible=True)
            registry["cases"][0]["input"] = {"path": str(input_path), "sha256": input_hash, "identity_status": "verified"}
            registry["cases"][0]["pseudos"] = {"files": [str(pseudo_path)], "sha256": {str(pseudo_path): pseudo_hash}, "identity_status": "verified"}
            registry["cases"][0]["runtime_binaries"] = {"g1_production": {"path": str(binary_path), "sha256": binary_hash, "identity_status": "verified_test"}}
            registry["cases"][0]["allowed_npools"] = [1]
            manifest = self.manifest_v2("qe", nodes=1, gpus_per_node=1, npools=1, run_dir=str(self.run_root / "run"))
            manifest["approved_by_human"] = True
            manifest["allowed_submit"] = True
            job = manifest["jobs"][0]
            job.update(binary_path=str(binary_path), binary_sha256=binary_hash, input_path=str(input_path), input_sha256=input_hash, pseudo_paths=[str(pseudo_path)], pseudo_sha256={str(pseudo_path): pseudo_hash})
            qe_runctl.validate_manifest(manifest, submit_mode=False, strict_files=False, config=self.config, case_registry=registry)
            manifest_path = self.write_json(tmp, "manifest.json", manifest)
            self.write_submit_permit(manifest_path, manifest)
            try:
                with self.controller_config_patch(), mock.patch.object(qe_runctl, "load_case_registry", return_value=registry):
                    qe_runctl.cmd_render(argparse.Namespace(manifest=str(manifest_path), strict_files=False, no_overwrite=True))
                calls = []
                def fake_run(args, **kwargs):
                    calls.append((args, kwargs))
                    return subprocess_result(0, "Submitted batch job 12345\n", "")
                enabled_config = clone(self.config)
                enabled_config["policy"]["two_node_qe_submit_enabled"] = True
                with mock.patch.object(qe_runctl, "approved_local_root", return_value=self.temp_root), mock.patch.dict(os.environ, {"HIPAC_SUBMIT_CMD": str(root / "fake_sbatch")}), mock.patch.object(qe_runctl, "load_config", return_value=enabled_config), mock.patch.object(qe_runctl, "load_case_registry", return_value=registry), mock.patch.object(qe_runctl.subprocess, "run", side_effect=fake_run):
                    self.assertEqual(qe_runctl.cmd_submit(argparse.Namespace(manifest=str(manifest_path), strict_files=False)), 0)
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0][0][0], "sbatch")
                self.assertTrue((self.run_root / "run" / "job_id.txt").exists())
                self.assertTrue((self.run_root / "run" / "submission_record.json").exists())
                ledger = qe_runctl.read_json(self.temp_root / "control" / "submission_ledger.json")
                self.assertEqual(ledger["entries"][manifest["trial_id"]]["attempts_consumed"], 1)
            finally:
                pass

    def submit_ready_manifest_with_permit(self, tmp, *, trial_id="P2A-R2-NP2"):
        manifest = self.manifest_v2("qe", nodes=1, gpus_per_node=1, npools=1, run_dir=str(self.run_root / f"permit_{trial_id}"))
        manifest["trial_id"] = trial_id
        manifest["approved_by_human"] = True
        manifest["allowed_submit"] = True
        registry = self.verified_registry_for_manifest(manifest)
        path = self.write_json(tmp, f"{trial_id}.json", manifest)
        self.write_submit_permit(path, manifest)
        with self.controller_config_patch(), mock.patch.object(qe_runctl, "load_case_registry", return_value=registry):
            qe_runctl.cmd_render(argparse.Namespace(manifest=str(path), strict_files=False, no_overwrite=True))
        enabled = clone(self.config)
        enabled["policy"]["two_node_qe_submit_enabled"] = True
        return manifest, path, registry, enabled

    def test_one_time_permit_first_attempt_consumes_and_second_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, path, registry, enabled = self.submit_ready_manifest_with_permit(tmp)
            def fake_run(args, **kwargs):
                return subprocess_result(0, "Submitted batch job 111\n", "")
            with mock.patch.object(qe_runctl, "approved_local_root", return_value=self.temp_root), mock.patch.object(qe_runctl, "load_config", return_value=enabled), mock.patch.object(qe_runctl, "load_case_registry", return_value=registry), mock.patch.object(qe_runctl.subprocess, "run", side_effect=fake_run):
                self.assertEqual(qe_runctl.cmd_submit(argparse.Namespace(manifest=str(path), strict_files=False)), 0)
            with mock.patch.object(qe_runctl, "approved_local_root", return_value=self.temp_root), mock.patch.object(qe_runctl, "load_config", return_value=enabled), mock.patch.object(qe_runctl, "load_case_registry", return_value=registry), mock.patch.object(qe_runctl.subprocess, "run", side_effect=AssertionError("second scheduler contact forbidden")):
                with self.assertRaises(qe_runctl.RunCtlError):
                    qe_runctl.cmd_submit(argparse.Namespace(manifest=str(path), strict_files=False))

    def test_permit_rejects_changed_manifest_resources_and_trial_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self.manifest_v2("qe", nodes=1, gpus_per_node=1, npools=1, run_dir=str(self.run_root / "permit_changed"))
            manifest["trial_id"] = "P2A-R2-NP2"
            manifest["approved_by_human"] = True
            manifest["allowed_submit"] = True
            registry = self.verified_registry_for_manifest(manifest)
            path = self.write_json(tmp, "manifest.json", manifest)
            self.write_submit_permit(path, manifest)
            manifest["jobs"][0]["slurm"]["time"] = "00:11:00"
            path = self.write_json(tmp, "manifest.json", manifest)
            with mock.patch.object(qe_runctl, "approved_local_root", return_value=self.temp_root), mock.patch.object(qe_runctl, "load_config", return_value=self.config), mock.patch.object(qe_runctl, "load_case_registry", return_value=registry), mock.patch.object(qe_runctl.subprocess, "run", side_effect=AssertionError("scheduler forbidden")):
                with self.assertRaises(qe_runctl.RunCtlError):
                    qe_runctl.cmd_submit(argparse.Namespace(manifest=str(path), strict_files=False))

            path2 = self.write_json(tmp, "manifest2.json", manifest)
            self.write_submit_permit(path2, manifest, trial_id="P2A-R2-NP4")
            with self.assertRaises(qe_runctl.RunCtlError):
                qe_runctl.load_and_validate_submit_permit(manifest_path=Path(path2), manifest=manifest)

    def test_pre_scheduler_failure_consumes_attempt_and_scheduler_rejection_consumes(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, path, registry, enabled = self.submit_ready_manifest_with_permit(tmp, trial_id="P2A-R2-NP4")
            with mock.patch.object(qe_runctl, "approved_local_root", return_value=self.temp_root), mock.patch.object(qe_runctl, "load_config", return_value=enabled), mock.patch.object(qe_runctl, "load_case_registry", return_value=registry), mock.patch.object(qe_runctl, "create_attempt_directory", side_effect=qe_runctl.RunCtlError("tmp failure before scheduler")), mock.patch.object(qe_runctl.subprocess, "run", side_effect=AssertionError("scheduler forbidden")):
                with self.assertRaises(qe_runctl.RunCtlError):
                    qe_runctl.cmd_submit(argparse.Namespace(manifest=str(path), strict_files=False))
            ledger = qe_runctl.read_json(self.temp_root / "control" / "submission_ledger.json")
            self.assertEqual(ledger["entries"][manifest["trial_id"]]["attempts_consumed"], 1)

        with tempfile.TemporaryDirectory() as tmp:
            manifest, path, registry, enabled = self.submit_ready_manifest_with_permit(tmp, trial_id="P2A-R2-NP8")
            def reject(args, **kwargs):
                return subprocess_result(1, "", "rejected")
            with mock.patch.object(qe_runctl, "approved_local_root", return_value=self.temp_root), mock.patch.object(qe_runctl, "load_config", return_value=enabled), mock.patch.object(qe_runctl, "load_case_registry", return_value=registry), mock.patch.object(qe_runctl.subprocess, "run", side_effect=reject):
                with self.assertRaises(qe_runctl.RunCtlError):
                    qe_runctl.cmd_submit(argparse.Namespace(manifest=str(path), strict_files=False))
            ledger = qe_runctl.read_json(self.temp_root / "control" / "submission_ledger.json")
            attempt = ledger["entries"][manifest["trial_id"]]["attempts"][-1]
            self.assertTrue(attempt["scheduler_contacted"])
            self.assertEqual(attempt["final_state"], "scheduler_rejected")

    def test_one_trial_cannot_consume_another_and_ledger_tampering_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, path, registry, enabled = self.submit_ready_manifest_with_permit(tmp, trial_id="P2A-R2-NP16")
            permit_path = Path(path).parent / "permit_record.json"
            permit = qe_runctl.read_json(permit_path)
            permit["trial_id"] = "P2A-R2-NP2"
            self.write_json(Path(path).parent, "permit_record.json", permit)
            with self.assertRaises(qe_runctl.RunCtlError):
                qe_runctl.load_and_validate_submit_permit(manifest_path=Path(path), manifest=manifest)

            self.write_submit_permit(path, manifest)
            bad_ledger = self.temp_root / "control" / "submission_ledger.json"
            self.write_json(bad_ledger.parent, bad_ledger.name, {"schema_version": "bad", "entries": {}})
            with mock.patch.object(qe_runctl, "approved_local_root", return_value=self.temp_root), mock.patch.object(qe_runctl, "load_config", return_value=enabled), mock.patch.object(qe_runctl, "load_case_registry", return_value=registry), mock.patch.object(qe_runctl.subprocess, "run", side_effect=AssertionError("scheduler forbidden")):
                with self.assertRaises(qe_runctl.RunCtlError):
                    qe_runctl.cmd_submit(argparse.Namespace(manifest=str(path), strict_files=False))

    def test_no_permit_authorizes_direct_sbatch(self):
        source = (REPO_ROOT / "scripts" / "qe_runctl.py").read_text(encoding="utf-8")
        self.assertIn("def cmd_submit", source)
        self.assertEqual(qe_runctl.production_submit_command(), "sbatch")

    def test_emax5_derivation_preserves_semantics_except_maxstep(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.in"
            dest = root / "derived" / "pw.in"
            source.write_text(
                "&CONTROL\n"
                "  calculation = 'scf'\n"
                "  prefix = 'au111'\n"
                "  outdir = './out'\n"
                "  pseudo_dir = '/pseudos'\n"
                "  disk_io = 'none'\n"
                "/\n"
                "&SYSTEM\n  nat = 1, ntyp = 1\n/\n"
                "&ELECTRONS\n  electron_maxstep = 100\n/\n"
                "ATOMIC_SPECIES\nAu 196.96657 Au.UPF\n"
                "ATOMIC_POSITIONS angstrom\nAu 0 0 0\n"
                "K_POINTS automatic\n4 4 1 0 0 0\n",
                encoding="utf-8",
            )
            record = qe_case_derivation.derive_electron_maxstep(
                source=source,
                dest=dest,
                expected_value=100,
                new_value=5,
            )
            self.assertTrue(dest.exists())
            self.assertTrue(record["bytes_changed_only_for_field"])
            self.assertIn("-  electron_maxstep = 100", record["unified_diff"])
            self.assertIn("+  electron_maxstep = 5", record["unified_diff"])
            self.assertTrue(record["semantic_comparison"]["equivalent_except_electron_maxstep"])
            self.assertEqual(record["semantic_comparison"]["derived_electron_maxstep"], "5")

    def test_emax5_derivation_negative_guards(self):
        cases = {
            "missing": "&ELECTRONS\n/\n",
            "multiple": "&ELECTRONS\n  electron_maxstep = 100\n  electron_maxstep = 100\n/\n",
            "wrong": "&ELECTRONS\n  electron_maxstep = 20\n/\n",
        }
        for name, text in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                source = Path(tmp) / "source.in"
                dest = Path(tmp) / "dest.in"
                source.write_text(text, encoding="utf-8")
                with self.assertRaises(qe_case_derivation.DerivationError):
                    qe_case_derivation.derive_electron_maxstep(
                        source=source,
                        dest=dest,
                        expected_value=100,
                        new_value=5,
                    )

    def test_existing_different_derived_destination_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.in"
            dest = Path(tmp) / "dest.in"
            source.write_text("&ELECTRONS\n  electron_maxstep = 100\n/\n", encoding="utf-8")
            dest.write_text("different\n", encoding="utf-8")
            with self.assertRaises(qe_case_derivation.DerivationError):
                qe_case_derivation.derive_electron_maxstep(
                    source=source,
                    dest=dest,
                    expected_value=100,
                    new_value=5,
                )

    def test_evidence_bundle_uses_relative_sha256sums_and_excludes_residue(self):
        root = self.temp_root / "control_center" / "chatE_auto_review" / "bundle_root"
        root.mkdir(parents=True)
        (root / "final_report.md").write_text("ok\n", encoding="utf-8")
        (root / "nested").mkdir()
        (root / "nested" / "stats.csv").write_text("CUDA,1\n", encoding="utf-8")
        (root / "write_test.txt").write_text("residue\n", encoding="utf-8")
        (root / "raw.nsys-rep").write_bytes(b"large raw")
        out = self.temp_root / "control_center" / "chatE_auto_review.tgz"
        with mock.patch.object(qe_runctl, "approved_local_root", return_value=self.temp_root):
            result = qe_runctl.package_evidence_root(root, out)
        self.assertTrue(result["sha256sums_relative_to_bundle_root"])
        with tempfile.TemporaryDirectory() as tmp:
            import tarfile
            import subprocess
            with tarfile.open(out, "r:gz") as tf:
                tf.extractall(tmp)
            extracted = Path(tmp) / root.name
            sums = (extracted / "SHA256SUMS").read_text(encoding="utf-8")
            self.assertIn("  final_report.md\n", sums)
            self.assertNotIn(str(root), sums)
            self.assertNotIn("write_test.txt", sums)
            self.assertNotIn("raw.nsys-rep", sums)
            check = subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=extracted, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)


def subprocess_result(returncode, stdout, stderr):
    completed = mock.Mock()
    completed.returncode = returncode
    completed.stdout = stdout
    completed.stderr = stderr
    return completed


if __name__ == "__main__":
    unittest.main()
