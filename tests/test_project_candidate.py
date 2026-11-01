"""Real filesystem regression tests for the public candidate projector.

Run: python3 -m unittest discover -s tests -p 'test_project_candidate.py' -v
No external services or source test execution are used by the projector itself.
"""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "skills/openbound/scripts/project_candidate.py"
SPEC = importlib.util.spec_from_file_location("project_candidate", SCRIPT)
pc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pc)


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="openbound-projection-test-")
        self.root = Path(self.temp.name)
        self.source = self.root / "private"
        self.source.mkdir()
        self.target = self.root / "public-v1"
        self.receipt = self.root / "receipt-private.json"

    def tearDown(self):
        self.temp.cleanup()

    def put(self, path, text, mode=0o644):
        full = self.source / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
        full.chmod(mode)
        return full

    def plan(self, *paths):
        return {"schema": pc.PLAN_SCHEMA, "files": [{"source": p, "target": p} for p in paths]}

    def make(self, plan):
        return pc.materialize(self.source, plan, self.target, self.receipt)

    def expect_error(self, code, callback, *args, **kwargs):
        with self.assertRaises(pc.ProjectionError) as result:
            callback(*args, **kwargs)
        self.assertEqual(code, result.exception.code)

    def test_mature_repository_preserves_complete_selected_project(self):
        files = {
            "README.md": "# Mature tool\nExisting usage and maintenance scope.\n",
            "LICENSE": "Existing license; unchanged.\n",
            "pyproject.toml": '[project]\nname = "mature-example"\nversion = "1.0.0"\n',
            "tool.py": 'def add(a, b):\n    return a + b\n',
            "tests/test_tool.py": 'from tool import add\nassert add(2, 3) == 5\n',
            ".github/workflows/test.yml": "name: Test\non: [push]\njobs: {}\n",
            "bin/run": "#!/usr/bin/env python3\nprint('ready')\n",
            "config.example.json": '{"endpoint": "http://localhost:8080"}\n',
        }
        for path, text in files.items():
            self.put(path, text, 0o755 if path == "bin/run" else 0o644)
        self.put(".env", "PRIVATE_TOKEN=private-fixture-do-not-copy\n")
        self.put(".git/config", "private Git transport details")
        result = self.make(self.plan(*files))
        self.assertEqual("materialized", result["status"])
        self.assertEqual(len(files), result["file_count"])
        for path, text in files.items():
            self.assertEqual(text, (self.target / path).read_text())
            self.assertEqual((self.source / path).read_bytes(), (self.target / path).read_bytes())
        self.assertFalse((self.target / ".env").exists())
        self.assertFalse((self.target / ".git").exists())
        self.assertEqual(0o755, stat.S_IMODE((self.target / "bin/run").stat().st_mode))
        self.assertEqual("verified", pc.verify(self.target, self.receipt, self.source, self.plan(*files))["status"])
        receipt = json.loads(self.receipt.read_text())
        self.assertFalse(receipt["source"]["atomic_snapshot"])
        self.assertEqual(0o600, stat.S_IMODE(self.receipt.stat().st_mode))

    def test_component_extraction_rewrites_interface_and_preserves_private_original(self):
        original = "PRIVATE_ROOT = '/home/example/internal'\nVALUE = 3\n"
        self.put("system/components/parser.py", original)
        self.put("system/secret-transport.py", "do not extract")
        plan = {"schema": pc.PLAN_SCHEMA, "files": [{
            "source": "system/components/parser.py", "target": "src/parser.py",
            "replacements": [{"old": "'/home/example/internal'", "new": "None", "expected_count": 1}]}]}
        result = self.make(plan)
        self.assertEqual("materialized", result["status"])
        self.assertEqual("PRIVATE_ROOT = None\nVALUE = 3\n", (self.target / "src/parser.py").read_text())
        self.assertEqual(original, (self.source / "system/components/parser.py").read_text())
        self.assertFalse((self.target / "system").exists())
        self.assertNotIn("/home/example/internal", self.receipt.read_text())
        self.assertNotIn(str(self.source), self.receipt.read_text())

    def test_count_mismatch_has_no_partial_output_and_no_sensitive_diagnostic(self):
        secret = "sensitive-private-fixture-458021"
        self.put("data.txt", secret + secret)
        plan = {"schema": pc.PLAN_SCHEMA, "files": [{"source": "data.txt", "target": "data.txt",
                 "replacements": [{"old": secret, "new": "public", "expected_count": 1}]}]}
        with self.assertRaises(pc.ProjectionError) as result:
            self.make(plan)
        self.assertEqual("replacement_count_mismatch", result.exception.code)
        self.assertNotIn(secret, str(result.exception))
        self.assertFalse(self.target.exists())
        self.assertFalse(self.receipt.exists())
        self.assertEqual([], list(self.root.glob(".openbound-stage-*")))

    def test_sequential_literal_replacement_counts_and_zero_count_assertion(self):
        self.put("data.txt", "PRIVATE / PRIVATE\n")
        plan = {"schema": pc.PLAN_SCHEMA, "files": [{"source": "data.txt", "target": "data.txt",
                "replacements": [{"old": "PRIVATE", "new": "sample", "expected_count": 2},
                                 {"old": "sample", "new": "example", "expected_count": 2},
                                 {"old": "PRIVATE", "new": "none", "expected_count": 0}]}]}
        self.make(plan)
        self.assertEqual("example / example\n", (self.target / "data.txt").read_text())

    def test_unchanged_rerun_is_noop_and_does_not_rewrite_receipt(self):
        self.put("README.md", "ready")
        plan = self.plan("README.md")
        first = self.make(plan)
        before = (self.receipt.stat().st_mtime_ns, (self.target / "README.md").stat().st_mtime_ns)
        second = self.make(plan)
        after = (self.receipt.stat().st_mtime_ns, (self.target / "README.md").stat().st_mtime_ns)
        self.assertEqual("no_change", second["status"])
        self.assertEqual(first["candidate_sha256"], second["candidate_sha256"])
        self.assertEqual(before, after)

    def test_modified_candidate_is_never_overwritten(self):
        self.put("a", "original")
        plan = self.plan("a")
        self.make(plan)
        (self.target / "a").write_text("user edit")
        self.expect_error("candidate_changed", self.make, plan)
        self.assertEqual("user edit", (self.target / "a").read_text())

    def test_foreign_empty_and_nonempty_targets_are_preserved(self):
        self.put("a", "x")
        self.target.mkdir()
        self.expect_error("candidate_already_exists", self.make, self.plan("a"))
        (self.target / "foreign").write_text("preserve")
        self.expect_error("candidate_already_exists", self.make, self.plan("a"))
        self.assertEqual("preserve", (self.target / "foreign").read_text())
        self.assertFalse(self.receipt.exists())

    def test_missing_changed_extra_file_and_extra_empty_directory_invalidate(self):
        self.put("a", "x")
        self.make(self.plan("a"))
        (self.target / "a").unlink()
        self.expect_error("candidate_changed", pc.verify, self.target, self.receipt)
        (self.target / "a").write_text("x")
        (self.target / "a").chmod(0o644)
        (self.target / "extra").write_text("extra")
        self.expect_error("candidate_changed", pc.verify, self.target, self.receipt)
        (self.target / "extra").unlink()
        (self.target / "empty").mkdir()
        self.expect_error("candidate_changed", pc.verify, self.target, self.receipt)

    def test_source_drift_is_explicit_and_requires_new_target_for_next_version(self):
        self.put("a", "v1")
        plan = self.plan("a")
        self.make(plan)
        (self.source / "a").write_text("v2")
        self.expect_error("source_changed", pc.verify, self.target, self.receipt, self.source, plan)
        self.expect_error("receipt_operation_changed", self.make, plan)
        self.assertEqual("v1", (self.target / "a").read_text())
        second = self.root / "public-v2"
        pc.materialize(self.source, plan, second, self.root / "receipt-v2.json")
        self.assertEqual("v2", (second / "a").read_text())
        self.assertEqual("v1", (self.target / "a").read_text())

    def test_plan_change_cannot_reuse_old_receipt_or_candidate(self):
        self.put("a", "private")
        plan = self.plan("a")
        self.make(plan)
        plan["files"][0]["replacements"] = [{"old": "private", "new": "public", "expected_count": 1}]
        self.expect_error("receipt_operation_changed", self.make, plan)
        self.expect_error("plan_changed", pc.verify, self.target, self.receipt, self.source, plan)

    def test_candidate_file_mode_directory_mode_and_root_mode_are_bound(self):
        self.put("bin/run", "#!/bin/sh\nexit 0\n", 0o755)
        self.make(self.plan("bin/run"))
        (self.target / "bin/run").chmod(0o644)
        self.expect_error("candidate_changed", pc.verify, self.target, self.receipt)
        (self.target / "bin/run").chmod(0o755)
        (self.target / "bin").chmod(0o700)
        self.expect_error("candidate_changed", pc.verify, self.target, self.receipt)
        (self.target / "bin").chmod(0o755)
        self.target.chmod(0o755)
        self.expect_error("candidate_changed", pc.verify, self.target, self.receipt)

    def test_source_mode_change_invalidates(self):
        self.put("a", "ready")
        plan = self.plan("a")
        self.make(plan)
        (self.source / "a").chmod(0o755)
        self.expect_error("source_changed", pc.verify, self.target, self.receipt, self.source, plan)

    def test_duplicate_case_and_file_directory_collisions(self):
        cases = [("a", "a"), ("README", "readme"), ("A/file", "a/other"),
                 ("x", "x/file"), ("x/file", "x")]
        for first, second in cases:
            with self.subTest(first=first, second=second):
                plan = {"schema": pc.PLAN_SCHEMA, "files": [{"source": "one", "target": first},
                                                             {"source": "two", "target": second}]}
                self.expect_error("path_collision", pc.validate_plan, plan)

    def test_traversal_absolute_ambiguous_and_control_paths_are_refused(self):
        values = ["../a", "a/../b", "/tmp/file", "a//b", "./a", "a/./b", "a\\b", "a:b",
                  "a\nb", "a/", "NUL", "x/COM1.txt", "a. ", "e\u0301", ".git/config",
                  "x/.GIT/config", ".openbound/state.json", ".openbound-cache/a"]
        for value in values:
            with self.subTest(value=value), self.assertRaises(pc.ProjectionError):
                pc.validate_plan(self.plan(value))

    def test_source_symlink_file_directory_and_root_ancestor_are_refused(self):
        self.put("real/a", "x")
        (self.source / "linked-file").symlink_to(self.source / "real/a")
        self.expect_error("symlink_or_invalid_ancestor", self.make, self.plan("linked-file"))
        (self.source / "linked-dir").symlink_to(self.source / "real", target_is_directory=True)
        self.expect_error("symlink_or_invalid_ancestor", self.make, self.plan("linked-dir/a"))
        linked_root = self.root / "source-link"
        linked_root.symlink_to(self.source, target_is_directory=True)
        self.expect_error("unsafe_or_missing_directory", pc.materialize, linked_root, self.plan("real/a"),
                          self.target, self.receipt)
        self.assertFalse(self.target.exists())

    def test_target_and_receipt_parent_symlink_are_refused(self):
        self.put("a", "x")
        real = self.root / "real-output"
        real.mkdir()
        link = self.root / "output-link"
        link.symlink_to(real, target_is_directory=True)
        self.expect_error("unsafe_or_missing_directory", pc.materialize, self.source, self.plan("a"),
                          link / "public", self.receipt)
        self.expect_error("unsafe_or_missing_directory", pc.materialize, self.source, self.plan("a"),
                          self.target, link / "receipt.json")
        self.assertEqual([], list(real.iterdir()))

    def test_hardlinks_and_fifos_are_rejected_without_blocking(self):
        self.put("a", "x")
        os.link(self.source / "a", self.source / "alias")
        self.expect_error("nonregular_or_linked_file", self.make, self.plan("a"))
        os.mkfifo(self.source / "pipe")
        self.expect_error("nonregular_or_linked_file", self.make, self.plan("pipe"))

    def test_receipt_and_output_must_be_outside_source_and_each_other(self):
        self.put("a", "x")
        for target, receipt, code in [
                (self.source / "public", self.receipt, "source_target_overlap"),
                (self.target, self.source / "receipt.json", "receipt_must_be_outside_roots"),
                (self.target, self.target / "receipt.json", "receipt_must_be_outside_roots"),
                (self.root, self.receipt, "source_target_overlap")]:
            with self.subTest(code=code):
                self.expect_error(code, pc.materialize, self.source, self.plan("a"), target, receipt)

    def test_prepared_receipt_can_recover_rename_acknowledgement(self):
        self.put("a", "x")
        plan = self.plan("a")
        self.make(plan)
        value = json.loads(self.receipt.read_text())
        value["state"] = "prepared"
        self.receipt.write_text(json.dumps(value))
        self.expect_error("receipt_incomplete", pc.verify, self.target, self.receipt)
        self.assertEqual("recovered", self.make(plan)["status"])
        self.assertEqual("verified", pc.verify(self.target, self.receipt)["status"])

    def test_prepared_receipt_resumes_when_publish_was_interrupted(self):
        self.put("a", "x")
        plan = self.plan("a")
        with mock.patch.object(pc, "_publish_directory", side_effect=pc.ProjectionError("test_interruption")):
            self.expect_error("test_interruption", self.make, plan)
        self.assertFalse(self.target.exists())
        self.assertEqual("prepared", json.loads(self.receipt.read_text())["state"])
        self.assertEqual([], list(self.root.glob(".openbound-stage-*")))
        self.assertEqual("resumed", self.make(plan)["status"])

    def test_complete_receipt_does_not_recreate_deleted_owned_candidate(self):
        self.put("a", "x")
        plan = self.plan("a")
        self.make(plan)
        (self.target / "a").unlink()
        self.target.rmdir()
        self.expect_error("owned_candidate_missing", self.make, plan)
        self.assertFalse(self.target.exists())

    def test_drift_during_preparation_cleans_only_owned_stage(self):
        self.put("a", "before")
        original = pc._write_tree

        def concurrent_write(*args):
            original(*args)
            (self.source / "a").write_text("after")

        with mock.patch.object(pc, "_write_tree", side_effect=concurrent_write):
            self.expect_error("source_changed", self.make, self.plan("a"))
        self.assertFalse(self.target.exists())
        self.assertFalse(self.receipt.exists())
        self.assertEqual([], list(self.root.glob(".openbound-stage-*")))

    def test_atomic_publication_never_overwrites_concurrent_foreign_directory(self):
        self.put("a", "x")
        original = pc._publish_directory

        def concurrent_target(*args):
            self.target.mkdir()
            return original(*args)

        with mock.patch.object(pc, "_publish_directory", side_effect=concurrent_target):
            self.expect_error("candidate_already_exists", self.make, self.plan("a"))
        self.assertTrue(self.target.is_dir())
        self.assertEqual([], list(self.target.iterdir()))
        self.assertEqual("prepared", json.loads(self.receipt.read_text())["state"])

    def test_mutation_at_final_location_never_produces_complete_receipt(self):
        self.put("a", "x")
        original = pc._publish_directory

        def mutate_after_rename(*args):
            original(*args)
            (self.target / "a").write_text("concurrent edit")

        with mock.patch.object(pc, "_publish_directory", side_effect=mutate_after_rename):
            self.expect_error("candidate_changed", self.make, self.plan("a"))
        self.assertEqual("prepared", json.loads(self.receipt.read_text())["state"])
        self.assertEqual("concurrent edit", (self.target / "a").read_text())
        self.expect_error("candidate_changed", self.make, self.plan("a"))

    def test_corrupt_receipt_never_authorizes_existing_target_replacement(self):
        self.put("a", "x")
        self.make(self.plan("a"))
        self.receipt.write_text('{"state": "complete"}')
        self.expect_error("invalid_receipt", self.make, self.plan("a"))
        self.assertEqual("x", (self.target / "a").read_text())

    def test_special_permission_bits_are_not_silently_projected(self):
        self.put("a", "x", 0o4755)
        self.expect_error("special_permission_bits", self.make, self.plan("a"))
        self.assertFalse(self.target.exists())

    def test_same_source_may_be_explicitly_projected_to_two_targets(self):
        self.put("a", "shared")
        plan = {"schema": pc.PLAN_SCHEMA, "files": [{"source": "a", "target": "one.txt"},
                                                    {"source": "a", "target": "two.txt"}]}
        self.make(plan)
        self.assertEqual("shared", (self.target / "one.txt").read_text())
        self.assertEqual("shared", (self.target / "two.txt").read_text())
        receipt = json.loads(self.receipt.read_text())
        self.assertEqual(1, len(receipt["source"]["files"]))
        self.assertEqual(2, len(receipt["candidate"]["tree"]["files"]))

    def test_receipt_tampering_and_unknown_schema_are_rejected(self):
        self.put("a", "x")
        self.make(self.plan("a"))
        value = json.loads(self.receipt.read_text())
        value["candidate"]["tree"]["files"][0]["sha256"] = "0" * 64
        self.receipt.write_text(json.dumps(value))
        self.expect_error("receipt_digest_mismatch", pc.verify, self.target, self.receipt)
        value["schema"] = "invented"
        self.receipt.write_text(json.dumps(value))
        self.expect_error("invalid_receipt", pc.verify, self.target, self.receipt)

    def test_receipt_cannot_be_reused_for_another_target(self):
        self.put("a", "x")
        self.make(self.plan("a"))
        self.expect_error("target_location_mismatch", pc.verify, self.root / "other", self.receipt)

    def test_unknown_plan_keys_duplicate_json_keys_and_bad_count_types(self):
        self.put("a", "x")
        plan = self.plan("a")
        plan["allow_network"] = True
        self.expect_error("invalid_plan", pc.validate_plan, plan)
        path = self.root / "plan.json"
        path.write_text('{"schema":"first","schema":"second","files":[]}')
        self.expect_error("duplicate_json_key", pc.load_plan, path)
        for count in (True, 1.5, "1", -1):
            plan = self.plan("a")
            plan["files"][0]["replacements"] = [{"old": "x", "new": "y", "expected_count": count}]
            self.expect_error("invalid_replacement", pc.validate_plan, plan)

    def test_bounded_files_and_output_growth_fail_before_publication(self):
        self.put("a", "x" * 20)
        with mock.patch.object(pc, "MAX_FILE_BYTES", 16):
            self.expect_error("file_size_limit", self.make, self.plan("a"))
        self.put("a", "xx")
        plan = self.plan("a")
        plan["files"][0]["replacements"] = [{"old": "x", "new": "abc", "expected_count": 2}]
        with mock.patch.object(pc, "MAX_FILE_BYTES", 5):
            self.expect_error("file_size_limit", self.make, plan)
        self.assertFalse(self.target.exists())

    def test_binary_is_copied_exactly_but_cannot_receive_text_replacement(self):
        data = b"\x00\xffbinary\x01"
        self.put("asset.bin", data)
        plan = self.plan("asset.bin")
        self.make(plan)
        self.assertEqual(data, (self.target / "asset.bin").read_bytes())
        plan["files"][0]["replacements"] = [{"old": "binary", "new": "x", "expected_count": 1}]
        self.expect_error("replacement_requires_utf8", self.make, plan)

    def test_cli_never_prints_replacement_values_or_source_contents(self):
        secret = "SECRET-FIXTURE-content-935248"
        self.put("a", "two " + secret + secret)
        plan = self.plan("a")
        plan["files"][0]["replacements"] = [{"old": secret, "new": "public", "expected_count": 1}]
        path = self.root / "plan.json"
        path.write_text(json.dumps(plan))
        result = subprocess.run([sys.executable, str(SCRIPT), "materialize", "--source", str(self.source),
                                 "--plan", str(path), "--target", str(self.target), "--receipt", str(self.receipt)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(2, result.returncode)
        self.assertNotIn(secret, result.stdout + result.stderr)
        self.assertNotIn(str(self.source), result.stdout + result.stderr)
        self.assertEqual({"status": "error", "code": "replacement_count_mismatch"}, json.loads(result.stdout))

    def test_cli_materialize_verify_and_incomplete_optional_arguments(self):
        self.put("a", "x")
        path = self.root / "plan.json"
        path.write_text(json.dumps(self.plan("a")))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = pc.main(["materialize", "--source", str(self.source), "--plan", str(path),
                            "--target", str(self.target), "--receipt", str(self.receipt)])
        self.assertEqual(0, code)
        self.assertEqual("materialized", json.loads(buf.getvalue())["status"])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = pc.main(["verify", "--target", str(self.target), "--receipt", str(self.receipt),
                            "--source", str(self.source)])
        self.assertEqual(2, code)
        self.assertEqual("source_and_plan_required_together", json.loads(buf.getvalue())["code"])

    def test_git_inventory_is_only_review_proposal_and_selects_worktree_bytes(self):
        self.put("README.md", "tracked-v1")
        self.put(".env", "private tracked config requires review")
        self.put("untracked.txt", "not automatically selected")
        subprocess.run(["git", "init", "-q", str(self.source)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.source), "add", "README.md", ".env"], check=True, capture_output=True)
        (self.source / "README.md").write_text("working-tree-v2")
        result = pc.inventory(self.source)
        self.assertEqual("review_required", result["status"])
        self.assertFalse(result["secret_screened"])
        self.assertEqual("none", result["execution_authorization"])
        self.assertEqual([".env", "README.md"], [entry["source"] for entry in result["plan"]["files"]])
        self.assertFalse(self.target.exists())
        reviewed = result["plan"]
        reviewed["files"] = [entry for entry in reviewed["files"] if entry["source"] != ".env"]
        self.make(reviewed)
        self.assertEqual("working-tree-v2", (self.target / "README.md").read_text())
        self.assertFalse((self.target / ".env").exists())

    def test_unavailable_atomic_rename_fails_closed_and_is_resumable(self):
        self.put("a", "x")
        with mock.patch.object(pc.sys, "platform", "unsupported"):
            self.expect_error("atomic_publish_unavailable", self.make, self.plan("a"))
        self.assertFalse(self.target.exists())
        self.assertEqual("prepared", json.loads(self.receipt.read_text())["state"])
        self.assertEqual("resumed", self.make(self.plan("a"))["status"])


if __name__ == "__main__":
    unittest.main()
