#!/usr/bin/env python3
"""Policy regression tests for project-local OpenCode profiles."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "opencode.json"
AGENTS = ROOT / ".opencode" / "agents"
SKILL = ROOT / ".opencode" / "skills" / "qe-nano4-bounded-phase-executor" / "SKILL.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        raise AssertionError("missing YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise AssertionError("unterminated YAML frontmatter")
    return text[4:end]


def bash_rule_block(text: str) -> str:
    fm = frontmatter(text)
    match = re.search(r"(?ms)^  bash:\n(?P<body>(?:    .*\n)+)", fm + "\n")
    if not match:
        raise AssertionError("missing permission.bash block")
    return match.group("body")


class OpenCodePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(read(CONFIG))
        cls.repo_auto = read(AGENTS / "qe-repo-auto.md")
        cls.runtime = read(AGENTS / "qe-runtime-gated.md")
        cls.phase_auto = read(AGENTS / "qe-phase-auto.md")
        cls.compat = read(AGENTS / "qe-bounded-phase.md")
        cls.skill = read(SKILL)

    def test_project_config_basics(self) -> None:
        self.assertEqual(self.config["$schema"], "https://opencode.ai/config.json")
        self.assertEqual(self.config["default_agent"], "qe-runtime-gated")
        self.assertEqual(self.config["share"], "disabled")

    def test_project_baseline_denies_runtime_and_remote_git(self) -> None:
        bash = self.config["permission"]["bash"]
        self.assertEqual(bash["*"], "ask")
        self.assertEqual(bash["python3 scripts/qe_runctl.py submit*"], "deny")
        for key in (
            "git push *",
            "git merge*",
            "git rebase*",
            "git reset --hard*",
            "git clean*",
            "sbatch *",
            "srun *",
            "salloc *",
            "mpirun *",
            "mpiexec *",
            "pw.x *",
        ):
            self.assertEqual(bash[key], "deny", key)

    def test_agents_exist_and_are_primary(self) -> None:
        for name, text in (
            ("qe-repo-auto", self.repo_auto),
            ("qe-runtime-gated", self.runtime),
            ("qe-phase-auto", self.phase_auto),
            ("qe-bounded-phase", self.compat),
        ):
            self.assertIn("mode: primary", frontmatter(text), name)

    def test_phase_auto_is_primary_and_fail_closed(self) -> None:
        fm = frontmatter(self.phase_auto)
        bash = bash_rule_block(self.phase_auto)
        self.assertIn("mode: primary", fm)
        self.assertIn("reasoningEffort: high", fm)
        self.assertIn("textVerbosity: low", fm)
        self.assertRegex(bash, r'(?m)^    "\*": deny$')
        for tool in (
            "list: allow",
            "glob: allow",
            "grep: allow",
            "lsp: allow",
            "question: deny",
            "webfetch: deny",
            "websearch: deny",
            "doom_loop: deny",
        ):
            self.assertIn(tool, fm)

    def test_phase_auto_submit_is_fixed_to_control_center_root(self) -> None:
        bash = bash_rule_block(self.phase_auto)
        broad = '"python3 scripts/qe_runctl.py submit*": deny'
        exact = (
            '"python3 scripts/qe_runctl.py submit --manifest '
            "/work/austinhpc25/hipac26-qe-local/control_center/"
            'chatCD_auto_review/*/manifest.json": allow'
        )
        nested = (
            '"python3 scripts/qe_runctl.py submit --manifest '
            "/work/austinhpc25/hipac26-qe-local/control_center/"
            'chatCD_auto_review/**/manifest.json": allow'
        )
        self.assertIn(broad, bash)
        self.assertIn(exact, bash)
        self.assertIn(nested, bash)
        self.assertLess(bash.index(broad), bash.index(exact))
        self.assertLess(bash.index(broad), bash.index(nested))
        self.assertNotIn('"python3 scripts/qe_runctl.py submit --manifest *": allow', bash)
        self.assertNotIn('"python3 scripts/qe_runctl.py submit --manifest *": ask', bash)

    def test_phase_auto_denies_other_submit_and_direct_runtime(self) -> None:
        bash = bash_rule_block(self.phase_auto)
        for command in (
            '"sbatch": deny',
            '"sbatch *": deny',
            '"srun": deny',
            '"srun *": deny',
            '"salloc": deny',
            '"salloc *": deny',
            '"mpirun": deny',
            '"mpirun *": deny',
            '"mpiexec": deny',
            '"mpiexec *": deny',
            '"pw.x": deny',
            '"pw.x *": deny',
            '"scancel": deny',
            '"scancel *": deny',
        ):
            self.assertIn(command, bash)

    def test_phase_auto_denies_controller_and_policy_edits(self) -> None:
        fm = frontmatter(self.phase_auto)
        for rule in (
            '"opencode.json": deny',
            '"*/opencode.json": deny',
            '".opencode/**": deny',
            '"*/.opencode/**": deny',
            '"scripts/qe_runctl.py": deny',
            '"scripts/qe_mapping_validator.py": deny',
            '"scripts/qe_rank_wrapper.cu": deny',
            '"schemas/**": deny',
        ):
            self.assertIn(rule, fm)

    def test_phase_auto_external_roots_are_bounded(self) -> None:
        fm = frontmatter(self.phase_auto)
        self.assertIn('external_directory:\n    "*": deny', fm)
        expected = {
            '"/work/austinhpc25/hipac26-qe-builds/**": allow',
            '"/work/austinhpc25/hipac26-qe-pseudos/**": allow',
            '"/work/austinhpc25/hipac26-qe-cases/**": allow',
            '"/work/austinhpc25/hipac26-qe-runs/**": allow',
            '"/work/austinhpc25/hipac26-qe-local/**": allow',
        }
        for rule in expected:
            self.assertIn(rule, fm)
        self.assertNotIn('"/tmp/**": allow', fm)
        self.assertNotIn('"/scratch/**": allow', fm)

    def test_phase_auto_denies_remote_and_history_rewrite_git(self) -> None:
        bash = bash_rule_block(self.phase_auto)
        for command in (
            '"git push": deny',
            '"git push *": deny',
            '"git merge*": deny',
            '"git rebase*": deny',
            '"git reset*": deny',
            '"git clean*": deny',
        ):
            self.assertIn(command, bash)

    def test_repo_auto_is_fail_closed(self) -> None:
        fm = frontmatter(self.repo_auto)
        bash = bash_rule_block(self.repo_auto)
        self.assertRegex(bash, r'(?m)^    "\*": deny$')
        self.assertIn('"python3 -m unittest*": allow', bash)
        self.assertIn('"git status*": allow', bash)
        self.assertIn('"git commit*": allow', bash)
        self.assertNotIn("qe_runctl.py submit", bash)
        self.assertIn('external_directory:\n    "*": deny', fm)
        for path in (
            '"opencode.json": deny',
            '".opencode/agents/**": deny',
            '".opencode/skills/**": deny',
        ):
            self.assertIn(path, fm)
        self.assertIn("may be launched with `--auto`", self.repo_auto)

    def test_runtime_submit_is_ask_but_direct_execution_is_denied(self) -> None:
        bash = bash_rule_block(self.runtime)
        self.assertRegex(bash, r'(?m)^    "\*": ask$')
        self.assertIn(
            '"python3 scripts/qe_runctl.py submit --manifest *": ask', bash
        )
        self.assertIn('"python3 scripts/qe_runctl.py submit*": deny', bash)
        for command in (
            '"sbatch *": deny',
            '"srun *": deny',
            '"salloc *": deny',
            '"mpirun *": deny',
            '"mpiexec *": deny',
            '"pw.x *": deny',
            '"git push *": deny',
            '"git reset --hard*": deny',
            '"git clean*": deny',
        ):
            self.assertIn(command, bash)
        self.assertIn("Never use\nthis agent with `--auto`", self.runtime)

    def test_specific_runtime_submit_rule_follows_broad_deny(self) -> None:
        bash = bash_rule_block(self.runtime)
        broad = bash.index('"python3 scripts/qe_runctl.py submit*": deny')
        specific = bash.index(
            '"python3 scripts/qe_runctl.py submit --manifest *": ask'
        )
        self.assertLess(broad, specific)

    def test_compatibility_agent_is_not_more_permissive(self) -> None:
        compat = bash_rule_block(self.compat)
        runtime = bash_rule_block(self.runtime)
        critical = (
            '"sbatch *": deny',
            '"srun *": deny',
            '"salloc *": deny',
            '"mpirun *": deny',
            '"mpiexec *": deny',
            '"pw.x *": deny',
            '"git push *": deny',
            '"git reset --hard*": deny',
            '"git clean*": deny',
        )
        for rule in critical:
            self.assertIn(rule, runtime)
            self.assertIn(rule, compat)
        self.assertIn("Compatibility profile only", self.compat)
        self.assertIn("Never use this alias\nwith `--auto`", self.compat)

    def test_existing_repo_and_runtime_profiles_remain_bounded(self) -> None:
        repo = bash_rule_block(self.repo_auto)
        runtime = bash_rule_block(self.runtime)
        self.assertRegex(repo, r'(?m)^    "\*": deny$')
        self.assertNotIn("qe_runctl.py submit", repo)
        self.assertIn("may be launched with `--auto`", self.repo_auto)
        self.assertRegex(runtime, r'(?m)^    "\*": ask$')
        self.assertIn('"python3 scripts/qe_runctl.py submit*": deny', runtime)
        self.assertIn(
            '"python3 scripts/qe_runctl.py submit --manifest *": ask', runtime
        )
        self.assertIn("Never use\nthis agent with `--auto`", self.runtime)

    def test_skill_exists_and_preserves_gate_control(self) -> None:
        self.assertIn("qe-nano4-bounded-phase-executor", self.skill)
        self.assertIn(
            "Only the Control Center may declare the gate `pass-closed`",
            self.skill,
        )

    def test_no_agent_grants_direct_runtime_commands(self) -> None:
        for name, text in (
            ("repo-auto", self.repo_auto),
            ("runtime", self.runtime),
            ("phase-auto", self.phase_auto),
            ("compat", self.compat),
        ):
            bash = bash_rule_block(text)
            for command in ("sbatch", "srun", "salloc", "mpirun", "mpiexec", "pw.x"):
                self.assertNotIn(f'"{command} *": allow', bash, (name, command))

    def test_documented_profiles(self) -> None:
        doc = read(ROOT / "docs" / "opencode_execution_profiles.md")
        self.assertIn("opencode . --agent qe-repo-auto --auto", doc)
        self.assertIn(
            "opencode . --agent qe-phase-auto --model openai/gpt-5.5 --auto",
            doc,
        )
        self.assertIn("chatCD_auto_review", doc)
        self.assertIn("opencode . --agent qe-runtime-gated", doc)
        self.assertIn("Never add `--auto`", doc)


if __name__ == "__main__":
    unittest.main()
