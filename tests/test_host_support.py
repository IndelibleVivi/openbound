"""Install integrity, conservative discovery reporting and relocated tool behavior."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("host_support", ROOT / "tools/host_support.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


class HostSupportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve())
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / "project with spaces"
        self.project.mkdir()

    def test_six_profiles_install_one_identical_payload_and_report_only_filesystem_evidence(self):
        canonical = h.unit(h.SKILL)
        for host in h.HOSTS:
            with self.subTest(host=host):
                root = self.base / host
                root.mkdir()
                result = h.install(host, "project", root)
                self.assertEqual(result["status"], "installed")
                self.assertEqual(h.unit(result["destination"])["files"], canonical["files"])
                self.assertEqual(h.install(host, "project", root)["status"], "unchanged")
                report = h.doctor(host, "project", root)
                self.assertEqual(report["installation"], "matches_source")
                self.assertEqual(report["implicit_activation"], "not_run")
                self.assertIsNone(report["claims"]["host_compatible"])

    def test_dry_run_and_doctor_create_nothing(self):
        self.assertEqual(h.install("codex", "project", self.project, dry_run=True)["status"], "planned")
        report = h.doctor("codex", "project", self.project)
        self.assertEqual(report["installation"], "missing")
        self.assertEqual(list(self.project.iterdir()), [])

    def test_optional_metadata_is_preserved_when_supplied_and_not_required_for_custom_source(self):
        canonical = h.install("codex", "project", self.project)
        metadata = Path(canonical["destination"]) / "agents/openai.yaml"
        self.assertEqual(metadata.read_bytes(), (h.SKILL / "agents/openai.yaml").read_bytes())
        metadata.unlink()
        metadata.parent.rmdir()
        self.assertEqual(h.doctor("codex", "project", self.project)["installation"], "differs")
        with self.assertRaisesRegex(ValueError, "installation_differs"):
            h.install("codex", "project", self.project)

        source = self.base / "reviewed portable source"
        shutil.copytree(h.SKILL, source, ignore=shutil.ignore_patterns("agents"))
        other = self.base / "other project"
        other.mkdir()
        result = h.install("codex", "project", other, source=source)
        self.assertEqual(result["file_count"], canonical["file_count"] - 1)
        self.assertEqual(h.doctor("codex", "project", other, source=source)["installation"], "matches_source")
        self.assertFalse((Path(result["destination"]) / "agents").exists())

    def test_modified_install_is_preserved(self):
        result = h.install("codex", "project", self.project)
        installed = Path(result["destination"])
        file = installed / "SKILL.md"
        file.write_text(file.read_text() + "\nLocal change.\n")
        before = file.read_bytes()
        with self.assertRaisesRegex(ValueError, "installation_differs"):
            h.install("codex", "project", self.project)
        self.assertEqual(file.read_bytes(), before)
        self.assertEqual(h.doctor("codex", "project", self.project)["installation"], "differs")

    def test_duplicate_native_and_shared_installs_are_reported(self):
        first = h.install("opencode", "project", self.project)
        alternate = self.project / ".opencode/skills/openbound"
        alternate.parent.mkdir(parents=True)
        shutil.copytree(first["destination"], alternate)
        report = h.doctor("opencode", "project", self.project)
        self.assertTrue(report["multiple_locations"])
        self.assertEqual(len(report["copies"]), 2)

    def test_symlink_destination_and_ancestor_are_refused(self):
        outside = self.base / "outside"
        outside.mkdir()
        (self.project / ".agents").symlink_to(outside, target_is_directory=True)
        with self.assertRaises((OSError, h.p.ProjectionError)):
            h.install("codex", "project", self.project)
        self.assertEqual(list(outside.iterdir()), [])

    def test_source_symlink_and_incomplete_unit_are_refused(self):
        source = self.base / "source"
        shutil.copytree(h.SKILL, source)
        (source / "references/delivery.md").unlink()
        with self.assertRaisesRegex(ValueError, "missing_skill_resource"):
            h.install("codex", "project", self.project, source=source)
        (source / "references/delivery.md").symlink_to(h.SKILL / "references/delivery.md")
        with self.assertRaises(h.p.ProjectionError):
            h.install("codex", "project", self.project, source=source)
        self.assertEqual(list(self.project.iterdir()), [])

    def test_existing_parent_modes_and_source_are_unchanged(self):
        parent = self.project / ".claude/skills"
        parent.mkdir(parents=True)
        parent.chmod(0o700)
        before = h.unit(h.SKILL)
        h.install("claude-code", "project", self.project)
        self.assertEqual(stat.S_IMODE(parent.stat().st_mode), 0o700)
        self.assertEqual(h.unit(h.SKILL), before)

    def test_source_target_overlap_is_refused_before_writes(self):
        with self.assertRaisesRegex(ValueError, "source_target_overlap"):
            h.install("codex", "project", h.SKILL, override=h.SKILL)

    def test_installed_directory_mode_drift_is_reported_and_not_repaired_implicitly(self):
        target = Path(h.install("claude-code", "project", self.project)["destination"])
        for changed in (target, target / "scripts"):
            with self.subTest(path=changed.name):
                old_mode = stat.S_IMODE(changed.stat().st_mode)
                changed.chmod(0o777)
                with self.assertRaisesRegex(ValueError, "installation_differs"):
                    h.install("claude-code", "project", self.project)
                self.assertEqual(h.doctor("claude-code", "project", self.project)["installation"], "differs")
                self.assertEqual(stat.S_IMODE(changed.stat().st_mode), 0o777)
                changed.chmod(old_mode)

    def test_cli_works_from_unrelated_directory_and_does_not_identify_generic_agent(self):
        result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/host_support.py"),
                                 "doctor", "--host", "cursor", "--root", str(self.project)],
                                cwd=self.base, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(all(item["identity"] == "not_verified" for item in report["executable_candidates"]))
        self.assertEqual(report["native_discovery"], "not_run")

    def test_all_three_tools_perform_real_work_from_two_install_layouts(self):
        # Two directory profiles, not two running harnesses. Actual CLI discovery
        # and model behavior have their own evidence levels in host_trials.
        for host in ("codex", "claude-code"):
            with self.subTest(host=host):
                root = self.base / host
                root.mkdir()
                installed = Path(h.install(host, "project", root)["destination"])
                scripts = installed / "scripts"
                source = root / "private source"
                source.mkdir()
                (source / "demo.py").write_text("print(6)\n")
                (source / "README.md").write_text("# Demo\nRun python3 demo.py.\n")
                (source / "private.txt").write_text("synthetic private material\n")
                plan = root / "plan.json"
                plan.write_text(json.dumps({"schema": "openbound-projection/1", "files": [
                    {"source": name, "target": name} for name in ("README.md", "demo.py")]}))
                target = root / "public candidate"
                receipt = root / "projection.json"

                def run(script, *args):
                    value = subprocess.run([sys.executable, "-B", str(scripts / script), *map(str, args)],
                                           cwd=self.base, capture_output=True, text=True)
                    self.assertEqual(value.returncode, 0, value.stdout + value.stderr)
                    return json.loads(value.stdout)

                run("project_candidate.py", "materialize", "--source", source, "--plan", plan,
                    "--target", target, "--receipt", receipt)
                run("project_candidate.py", "verify", "--target", target, "--receipt", receipt)
                self.assertFalse((target / "private.txt").exists())
                subprocess.run(["git", "-c", "init.templateDir=", "-C", str(target), "init", "-q"],
                               check=True, capture_output=True)
                subprocess.run(["git", "-c", "core.fsmonitor=false", "-C", str(target), "add", "README.md", "demo.py"],
                               check=True, capture_output=True)
                scan = run("inspect_public_candidate.py", "--repo", target, "--json", "--fail-on-incomplete")
                self.assertFalse(scan["claims"]["publication_ready"])
                contract = root / "verification.json"
                contract.write_text(json.dumps({"schema": "openbound-verification/1", "checks": [
                    {"id": "demo", "argv": ["{python}", "demo.py"], "stdout_json_equals": 6}]}))
                checked = run("verify_public_work.py", "check", "--candidate", target,
                              "--contract", contract, "--receipt", root / "verification-receipt.json",
                              "--execute-reviewed")
                self.assertTrue(checked["all_requested_checks_passed"])
                self.assertTrue(checked["fresh"])


if __name__ == "__main__":
    unittest.main()
