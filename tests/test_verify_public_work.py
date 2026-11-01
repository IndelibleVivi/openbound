import importlib.util
import json
import os
from pathlib import Path
import stat
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/openbound/scripts/verify_public_work.py"
SPEC = importlib.util.spec_from_file_location("verify_public_work", SCRIPT)
v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v)


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.candidate = self.base / "candidate"
        self.candidate.mkdir()
        (self.candidate / "README.md").write_text("A useful local tool.\n")
        self.contract = self.base / "contract.json"
        self.receipt = self.base / "receipt.json"
        self.inspector = mock.patch.object(v, "run_inspection", return_value={
            "findings": [], "scan_complete": True, "publication_ready": False})
        self.inspector.start()
        self.addCleanup(self.inspector.stop)
        self.addCleanup(self.tmp.cleanup)

    def plan(self, checks=None, witnesses=None):
        value = {"schema": v.SCHEMA, "checks": checks or [], "witnesses": witnesses or []}
        self.contract.write_text(json.dumps(value))

    def command(self, code, **extra):
        return {"id": "exercise", "argv": ["{python}", "-c", code], **extra}

    def run_check(self, reviewed=True):
        return v.check(self.candidate, self.contract, self.receipt, reviewed)

    def error(self, code, callback):
        with self.assertRaises(v.WorkError) as raised:
            callback()
        self.assertEqual(raised.exception.code, code)

    def test_runs_real_program_in_independent_copy_and_preserves_candidate(self):
        before = v.snapshot_tree(self.candidate)
        self.plan([self.command("from pathlib import Path; Path('generated').write_text('x'); print('37')",
                                stdout_json_equals=37)])
        result = self.run_check()
        self.assertTrue(result["all_requested_checks_passed"])
        self.assertEqual(before, v.snapshot_tree(self.candidate))
        self.assertFalse(result["publication_ready"])
        self.assertEqual(stat.S_IMODE(self.receipt.stat().st_mode), 0o600)

    def test_requires_reviewed_execution_flag_and_never_creates_receipt(self):
        self.plan([self.command("raise SystemExit(0)")])
        self.error("reviewed_execution_flag_required", lambda: self.run_check(False))
        self.assertFalse(self.receipt.exists())

    def test_empty_research_contract_does_not_claim_executable_validation(self):
        self.plan()
        result = self.run_check(False)
        self.assertIsNone(result["all_requested_checks_passed"])
        self.assertEqual(result["executed_checks"], 0)
        self.assertFalse(result["publication_ready"])

    def test_host_secret_is_not_inherited(self):
        self.plan([self.command("import os,json; print(json.dumps('OPENBOUND_FAKE_SECRET' in os.environ))",
                                stdout_json_equals=False)])
        with mock.patch.dict(os.environ, {"OPENBOUND_FAKE_SECRET": "synthetic-private-value"}):
            self.assertTrue(self.run_check()["all_requested_checks_passed"])

    def test_stdout_and_stderr_secrets_absent_from_receipt_and_summary(self):
        secret = "SYNTHETIC_ONLY_do_not_echo_92034"
        self.plan([self.command("import sys; print('" + secret + "'); print('" + secret + "',file=sys.stderr)")])
        result = self.run_check()
        self.assertNotIn(secret, json.dumps(result))
        self.assertNotIn(secret, self.receipt.read_text())
        self.assertTrue(result["all_requested_checks_passed"])

    def test_arguments_are_not_shell_expanded(self):
        literal = "$(touch SHOULD_NOT_EXIST); echo unsafe"
        self.plan([{"id": "literal", "argv": ["{python}", "-c", "import sys,json; print(json.dumps(sys.argv[1]))", literal],
                    "stdout_json_equals": literal}])
        self.assertTrue(self.run_check()["all_requested_checks_passed"])
        self.assertFalse((self.candidate / "SHOULD_NOT_EXIST").exists())

    def test_real_failed_command_is_recorded_as_failed(self):
        self.plan([self.command("raise SystemExit(7)")])
        result = self.run_check()
        self.assertFalse(result["all_requested_checks_passed"])
        self.assertEqual(json.loads(self.receipt.read_text())["checks"][0]["exit_code"], 7)

    def test_expected_failure_is_explicit(self):
        self.plan([self.command("raise SystemExit(7)", expected_exit=7)])
        self.assertTrue(self.run_check()["all_requested_checks_passed"])

    def test_timeout_fails_without_exposing_output(self):
        self.plan([self.command("import time; time.sleep(30)", timeout_seconds=0.1)])
        result = self.run_check()
        self.assertFalse(result["all_requested_checks_passed"])
        self.assertTrue(json.loads(self.receipt.read_text())["checks"][0]["timed_out"])

    def test_unbounded_output_fails_with_bounded_capture(self):
        self.plan([self.command("import sys; sys.stdout.write('x'*1200000)")])
        self.assertFalse(self.run_check()["all_requested_checks_passed"])
        check = json.loads(self.receipt.read_text())["checks"][0]
        self.assertTrue(check["output_limited"])
        self.assertLessEqual(check["stdout"]["captured_bytes"], v.MAX_OUTPUT_BYTES)

    def test_json_assertion_rejects_incorrect_output(self):
        self.plan([self.command("print('8')", stdout_json_equals=37)])
        self.assertFalse(self.run_check()["all_requested_checks_passed"])

    def test_json_duplicate_keys_rejected(self):
        self.plan([self.command("print('{\"x\":1,\"x\":37}')", stdout_json_equals={"x": 37})])
        self.assertFalse(self.run_check()["all_requested_checks_passed"])

    def test_mechanism_witness_distinguishes_naive_limit_from_pagination(self):
        self.plan([
            {"id": "complete", "argv": ["{python}", "-c", "print('37')"], "stdout_json_equals": 37},
            {"id": "naive", "argv": ["{python}", "-c", "print('8')"], "stdout_json_equals": 8}],
            [{"id": "backlog", "positive": "complete", "negative": "naive", "relation": "different_json"}])
        self.assertTrue(self.run_check()["all_requested_checks_passed"])

    def test_witness_rejects_a_synthetic_example_that_erases_difference(self):
        self.plan([
            {"id": "complete", "argv": ["{python}", "-c", "print('5')"]},
            {"id": "naive", "argv": ["{python}", "-c", "print('5')"]}],
            [{"id": "backlog", "positive": "complete", "negative": "naive", "relation": "different_json"}])
        result = self.run_check()
        self.assertFalse(result["all_requested_checks_passed"])
        self.assertEqual(result["failed_witnesses"], 1)

    def test_each_command_receives_fresh_copy(self):
        self.plan([
            {"id": "writer", "argv": ["{python}", "-c", "from pathlib import Path; Path('leak').touch()"]},
            {"id": "reader", "argv": ["{python}", "-c", "from pathlib import Path; assert not Path('leak').exists()"]}])
        self.assertTrue(self.run_check()["all_requested_checks_passed"])

    def test_unchanged_repeat_reuses_receipt_without_execution_or_scan(self):
        self.plan([self.command("print('37')", stdout_json_equals=37)])
        self.run_check()
        with mock.patch.object(v, "run_command", side_effect=AssertionError("rerun")), \
             mock.patch.object(v, "run_inspection", side_effect=AssertionError("rescan")):
            self.assertTrue(self.run_check(False)["reused"])

    def test_changed_candidate_invalidates_receipt(self):
        self.plan()
        self.run_check(False)
        (self.candidate / "README.md").write_text("changed\n")
        self.assertFalse(v.status(self.candidate, self.contract, self.receipt)["fresh"])
        self.error("receipt_stale_choose_new_path", lambda: self.run_check(False))

    def test_added_empty_directory_invalidates_receipt(self):
        self.plan()
        self.run_check(False)
        (self.candidate / "empty").mkdir()
        self.assertFalse(v.status(self.candidate, self.contract, self.receipt)["fresh"])

    def test_changed_contract_invalidates_receipt(self):
        self.plan()
        self.run_check(False)
        self.contract.write_text(self.contract.read_text() + "\n")
        self.assertFalse(v.status(self.candidate, self.contract, self.receipt)["fresh"])

    def test_changed_tool_invalidates_receipt(self):
        self.plan()
        self.run_check(False)
        with mock.patch.object(v, "tool_identity", return_value={"version": "changed"}):
            self.assertFalse(v.status(self.candidate, self.contract, self.receipt)["fresh"])

    def test_forged_ready_flag_is_not_accepted(self):
        self.plan()
        self.run_check(False)
        data = json.loads(self.receipt.read_text())
        data["publication_ready"] = True
        self.receipt.write_text(json.dumps(data))
        self.error("inconsistent_receipt", lambda: v.status(self.candidate, self.contract, self.receipt))

    def test_forged_pass_field_contradicting_exit_is_rejected(self):
        self.plan([self.command("raise SystemExit(4)")])
        self.run_check()
        data = json.loads(self.receipt.read_text())
        data["checks"][0]["passed"] = True
        self.receipt.write_text(json.dumps(data))
        self.error("inconsistent_receipt", lambda: v.status(self.candidate, self.contract, self.receipt))

    def test_state_inside_candidate_rejected(self):
        self.plan()
        self.receipt = self.candidate / "receipt.json"
        self.error("private_state_inside_candidate", lambda: self.run_check(False))

    def test_symlink_and_hardlink_are_refused(self):
        (self.candidate / "shortcut").symlink_to("README.md")
        self.error("candidate_contains_symlink", lambda: v.snapshot_tree(self.candidate))
        (self.candidate / "shortcut").unlink()
        os.link(self.candidate / "README.md", self.candidate / "hardlink")
        self.error("candidate_contains_nonordinary_file", lambda: v.snapshot_tree(self.candidate))

    def test_candidate_mutation_during_check_invalidates_all_evidence(self):
        self.plan([self.command("print('37')")])
        real = v.run_command
        def mutate(*args):
            result = real(*args)
            (self.candidate / "README.md").write_text("mutation")
            return result
        with mock.patch.object(v, "run_command", side_effect=mutate):
            self.error("candidate_changed_during_verification", self.run_check)
        self.assertFalse(self.receipt.exists())

    def test_invalid_json_and_unknown_fields_fail_without_raw_values(self):
        self.contract.write_text('{"schema":"openbound-verification/1", "private": "sensitive"}')
        self.error("unknown_contract_field", lambda: self.run_check(False))

    def test_cli_redacts_missing_secret_path(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "check", "--candidate", str(self.candidate),
                               "--contract", str(self.base / "synthetic-secret-value"),
                               "--receipt", str(self.receipt)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("synthetic-secret-value", proc.stdout + proc.stderr)

    def test_cli_argument_errors_do_not_echo_input(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "synthetic-secret-value"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("synthetic-secret-value", proc.stdout + proc.stderr)

    def git(self, root, *args):
        return subprocess.run([shutil.which('git'), '-C', str(root), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_git_core_worktree_cannot_redirect_inspection(self):
        outside = self.base / 'outside'
        outside.mkdir()
        self.git(self.candidate, 'init', '-q')
        self.git(outside, 'init', '-q')
        self.git(self.candidate, 'config', 'core.worktree', str(outside))
        self.plan()
        self.error('git_root_outside_candidate', lambda: self.run_check(False))
        self.assertFalse(self.receipt.exists())

    def test_absolute_worktree_cannot_escape_execution_copy(self):
        self.git(self.candidate, 'init', '-q')
        self.git(self.candidate, 'config', 'core.worktree', str(self.candidate))
        self.plan([self.command("print(37)")])
        self.error('git_root_outside_candidate', self.run_check)
        self.assertFalse(self.receipt.exists())

    def test_external_git_object_store_is_explicitly_refused(self):
        self.git(self.candidate, 'init', '-q')
        (self.candidate / '.git/objects/info/alternates').write_text('/private/example/objects\n')
        self.plan()
        self.error('external_git_storage_requires_explicit_inspection', lambda: self.run_check(False))

    def test_changed_external_executable_invalidates_evidence(self):
        program = self.base / 'reviewed-helper'
        program.write_text('#!/bin/sh\nexit 0\n')
        program.chmod(0o755)
        self.plan([{'id': 'helper', 'argv': [str(program)]}])
        self.assertTrue(self.run_check()['all_requested_checks_passed'])
        program.write_text('#!/bin/sh\nexit 7\n')
        self.assertFalse(v.status(self.candidate, self.contract, self.receipt)['fresh'])
        self.error('receipt_stale_choose_new_path', lambda: self.run_check(False))

    def test_changed_absolute_script_argument_invalidates_evidence(self):
        program = self.base / 'reviewed.py'
        program.write_text('raise SystemExit(0)\n')
        self.plan([{'id': 'helper', 'argv': ['{python}', str(program)]}])
        self.run_check()
        program.write_text('raise SystemExit(7)\n')
        self.assertFalse(v.status(self.candidate, self.contract, self.receipt)['fresh'])

    def test_inspection_git_program_change_invalidates_empty_check_receipt(self):
        programs = self.base / 'programs'
        programs.mkdir()
        git = programs / 'git'
        git.write_text('#!/bin/sh\nexit 0\n')
        git.chmod(0o755)
        self.plan()
        with mock.patch.dict(os.environ, {'PATH': str(programs) + os.pathsep + os.environ['PATH']}):
            self.run_check(False)
            git.write_text('#!/bin/sh\nexit 99\n')
            self.assertFalse(v.status(self.candidate, self.contract, self.receipt)['fresh'])

    def test_declared_external_input_drift_invalidates_evidence(self):
        dependency = self.base / 'environment-description.txt'
        dependency.write_text('known dependency revision one')
        self.plan()
        value = json.loads(self.contract.read_text())
        value['dependencies'] = [str(dependency)]
        self.contract.write_text(json.dumps(value))
        self.run_check(False)
        dependency.write_text('changed revision two')
        self.assertFalse(v.status(self.candidate, self.contract, self.receipt)['fresh'])

    def test_large_legitimate_receipt_is_readable_and_reusable(self):
        for i in range(3500):
            (self.candidate / (str(i).zfill(4) + 'x' * 190)).write_text('x')
        self.plan()
        self.run_check(False)
        self.assertGreater(self.receipt.stat().st_size, 1024 * 1024)
        self.assertTrue(v.status(self.candidate, self.contract, self.receipt)['fresh'])
        self.assertTrue(self.run_check(False)['reused'])

    def test_fifo_contract_fails_without_waiting_for_writer(self):
        os.mkfifo(self.contract)
        proc = subprocess.run([sys.executable, str(SCRIPT), 'check', '--candidate', str(self.candidate),
                               '--contract', str(self.contract), '--receipt', str(self.receipt)],
                              capture_output=True, text=True, timeout=2)
        self.assertEqual(proc.returncode, 2)
        self.assertIn('unsafe_or_oversize_json', proc.stdout)


if __name__ == "__main__":
    unittest.main()
