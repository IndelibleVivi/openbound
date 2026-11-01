"""Deterministic harness-eval infrastructure tests; no host/model is invoked."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import host_trials as trials


class HostTrialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve())
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def prepare(self, case="A", mode="implicit", name="trial", host="test-host", invocation=None):
        result = trials.prepare(self.root / name, case, mode, host, invocation)
        return result, Path(result["record"]), Path(result["subject"])

    def mature_candidate(self, subject):
        target = subject / "candidate"
        shutil.copytree(subject / "inputs/source", target,
                        ignore=shutil.ignore_patterns(".git", ".env", "private"))
        readme = target / "README.md"
        readme.write_text(readme.read_text().replace("cd /Users/synthetic_author/work/batch-total", "cd batch-total"))
        entry = target / "batch_total/__main__.py"
        entry.write_text(entry.read_text().replace("/Users/synthetic_author/data/numbers.txt", "examples/numbers.txt"))
        return target

    def test_fixture_commits_do_not_launch_background_maintenance(self):
        source = self.root / "git source"
        source.mkdir()
        (source / "README.md").write_text("Synthetic source.\n")
        trace = self.root / "git-trace.json"
        run = subprocess.run

        def traced(*args, **kwargs):
            # Observe real Git children without inheriting operator settings in
            # the fixture's deliberately minimal environment.
            kwargs["env"] = dict(kwargs["env"], GIT_TRACE2_EVENT=str(trace))
            return run(*args, **kwargs)

        with mock.patch.object(trials.subprocess, "run", side_effect=traced):
            trials.git_fixture(source)
        events = [json.loads(line) for line in trace.read_text().splitlines()]
        children = [event.get("argv", []) for event in events if event.get("event") == "child_start"]
        self.assertFalse(any("maintenance" in argv or "gc" in argv for argv in children), children)

    def test_prepare_never_claims_live_discovery_or_outcome(self):
        result, record, subject = self.prepare()
        self.assertEqual(result["host_execution"], "not_run")
        assessment = trials.assess(record)
        self.assertFalse(assessment["facts"]["candidate_exists"])
        self.assertEqual(assessment["deterministic_status"], "failed")
        self.assertEqual(assessment["operator_observations"]["stages"]["discovery"]["status"], "not_observed")
        self.assertIsNone(assessment["operator_observations"]["metrics"]["tool_calls"])

    def test_implicit_and_control_have_no_skill_or_reviewer_cue_and_same_fixture(self):
        first, first_record, first_subject = self.prepare(mode="implicit", name="implicit")
        second, second_record, second_subject = self.prepare(mode="control", name="control")
        self.assertEqual(first["fixture_content_sha256"], second["fixture_content_sha256"])
        for subject in (first_subject, second_subject):
            prompt = (subject / "prompt.md").read_text()
            self.assertNotIn("OpenBound", prompt)
            self.assertNotIn("$openbound", prompt)
            self.assertFalse((subject / "resources").exists())
            self.assertFalse(list(subject.rglob("*.review.md")))
            self.assertFalse(list(subject.rglob("trial.json")))
        left = trials.read_json(first_record)
        right = trials.read_json(second_record)
        self.assertEqual(left["task_template_sha256"], right["task_template_sha256"])

    def test_source_directed_has_one_complete_skill_and_explicit_requires_documented_text(self):
        _, _, subject = self.prepare(mode="source-directed")
        self.assertTrue((subject / "resources/openbound/scripts/project_candidate.py").is_file())
        self.assertTrue((subject / "resources/openbound/references/delivery.md").is_file())
        self.assertEqual(len(list(subject.rglob("SKILL.md"))), 1)
        with self.assertRaisesRegex(trials.TrialError, "requires_documented"):
            self.prepare(mode="explicit", name="invalid")
        _, _, explicit = self.prepare(mode="explicit", name="explicit", invocation="/openbound")
        self.assertTrue((explicit / "prompt.md").read_text().startswith("/openbound\n"))

    def test_never_overwrites_existing_trial_or_uses_repo_or_symlink_target(self):
        self.prepare()
        with self.assertRaises(FileExistsError):
            self.prepare()
        with self.assertRaisesRegex(trials.TrialError, "outside_source_repository"):
            trials.prepare(ROOT / "bad-eval", "A", "implicit", "host")
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(trials.TrialError, "symlink"):
            trials.prepare(alias / "bad", "A", "implicit", "host")
        with self.assertRaisesRegex(trials.TrialError, "parent_path_component"):
            trials.path(self.root / "missing" / ".." / "otherwise-valid")

    def test_assessment_default_does_not_execute_candidate_or_invent_behavior(self):
        _, record, subject = self.prepare()
        target = self.mature_candidate(subject)
        marker = self.root / "execution-marker"
        entry = target / "batch_total/__main__.py"
        entry.write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('ran')\n")
        result = trials.assess(record)
        self.assertFalse(marker.exists())
        self.assertEqual(result["runtime"]["status"], "not_run")
        self.assertEqual(result["behavior_acceptance"], "not_automatically_decided")
        self.assertEqual(result["operator_observations"]["stages"]["end_to_end"]["status"], "not_observed")

    def test_mature_result_has_actual_candidate_execution_when_authorized(self):
        _, record, subject = self.prepare()
        target = self.mature_candidate(subject)
        before = trials.snapshot(target)
        result = trials.assess(record, execute_reviewed=True)
        self.assertEqual(result["deterministic_status"], "passed_limited_checks")
        self.assertTrue(result["facts"]["fixed_runtime_checks_passed"])
        self.assertEqual(result["runtime"]["result"]["executed_checks"], 2)
        self.assertEqual(before, trials.snapshot(target))
        self.assertEqual(result["operator_observations"]["stages"]["authorization"]["status"], "not_observed")

    def test_mature_packaging_edit_is_reported_for_review_without_claiming_removal(self):
        _, record, subject = self.prepare()
        target = self.mature_candidate(subject)
        metadata = target / "pyproject.toml"
        metadata.write_text(metadata.read_text() + '\n[build-system]\nrequires = ["setuptools>=61"]\nbuild-backend = "setuptools.build_meta"\n')
        result = trials.assess(record, execute_reviewed=True)
        self.assertTrue(result["facts"]["mature_artifacts_present"])
        self.assertTrue(result["facts"]["existing_license_preserved"])
        self.assertEqual(result["deterministic_status"], "passed_limited_checks")
        self.assertEqual(result["baseline_file_changes"]["pyproject.toml"]["status"], "changed")
        self.assertEqual(result["baseline_file_changes"]["pyproject.toml"]["review"], "independent_review_required")
        self.assertEqual(result["baseline_file_changes"]["batch_total/core.py"]["status"], "unchanged")
        self.assertEqual(result["behavior_acceptance"], "not_automatically_decided")

    def test_documented_portable_default_is_reviewer_owned(self):
        _, record, subject = self.prepare()
        target = self.mature_candidate(subject)
        entry = target / "batch_total/__main__.py"
        entry.write_text(entry.read_text().replace("'examples/numbers.txt'", "'numbers.txt'"))
        readme = target / "README.md"
        readme.write_text(readme.read_text() + "\nWithout --file or BATCH_TOTAL_INPUT, create numbers.txt in the current directory.\n")
        result = trials.assess(record, execute_reviewed=True)
        self.assertEqual(result["deterministic_status"], "passed_limited_checks")
        self.assertEqual(result["runtime"]["result"]["executed_checks"], 2)
        self.assertIn("documented default/env/explicit behavior and installed use", result["required_review"])
        self.assertEqual(result["behavior_acceptance"], "not_automatically_decided")

    def test_removed_mature_asset_and_replaced_license_remain_hard_failures(self):
        _, record, subject = self.prepare()
        target = self.mature_candidate(subject)
        (target / "tests/test_total.py").unlink()
        (target / "LICENSE").write_text("A different grant.\n")
        result = trials.assess(record)
        self.assertFalse(result["facts"]["mature_artifacts_present"])
        self.assertFalse(result["facts"]["existing_license_preserved"])
        self.assertEqual(result["baseline_file_changes"]["tests/test_total.py"]["status"], "missing")
        self.assertEqual(result["baseline_file_changes"]["LICENSE"]["status"], "changed")
        self.assertEqual(result["deterministic_status"], "failed")

    def test_source_check_runs_after_reviewed_candidate_code(self):
        _, record, subject = self.prepare()
        target = self.mature_candidate(subject)
        source_note = subject / "inputs/source/README.md"
        entry = target / "batch_total/__main__.py"
        entry.write_text("from pathlib import Path\nPath(" + repr(str(source_note)) +
                         ").write_text('candidate side effect')\nprint('6.00')\n")
        result = trials.assess(record, execute_reviewed=True)
        self.assertFalse(result["facts"]["source_preserved"])
        self.assertEqual(result["deterministic_status"], "failed")

    def test_cli_refuses_writing_evaluator_result_into_subject_before_execution(self):
        _, record, subject = self.prepare()
        target = self.mature_candidate(subject)
        before = trials.snapshot(target)
        result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/host_trials.py"),
                                 "assess", "--record", str(record), "--execute-reviewed", "--output",
                                 str(subject / "assessment.json")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("evaluator_directory", result.stdout)
        self.assertFalse((subject / "assessment.json").exists())
        self.assertFalse(list(record.parent.glob("checks-*.json")))
        self.assertEqual(before, trials.snapshot(target))

    def test_source_mutation_or_private_sentinel_fails(self):
        _, record, subject = self.prepare()
        target = self.mature_candidate(subject)
        (target / "extra.txt").write_text("fixture.internal")
        (subject / "inputs/source/batch_total/core.py").write_text("changed")
        result = trials.assess(record)
        self.assertFalse(result["facts"]["source_preserved"])
        self.assertFalse(result["facts"]["known_private_sentinels_absent"])
        self.assertEqual(result["deterministic_status"], "failed")

    def test_existing_blob_index_change_is_detected_without_worktree_or_object_change(self):
        _, record, subject = self.prepare()
        self.mature_candidate(subject)
        source = subject / "inputs/source"
        before = trials.snapshot(source)
        scanner = trials.engine("inspect_public_candidate")
        blob = scanner._run_git_bytes(source, "rev-parse", "HEAD:LICENSE").stdout.decode().strip()
        scanner._run_git_bytes(source, "update-index", "--cacheinfo", "100644," + blob + ",README.md")
        self.assertEqual(before, trials.snapshot(source), "Only index storage should change in this counterexample")
        result = trials.assess(record)
        self.assertFalse(result["facts"]["source_preserved"])
        self.assertFalse(result["facts"]["source_index_preserved"])
        self.assertEqual(result["source_index_observations"][0]["status"], "changed")

    def test_benign_index_stat_refresh_keeps_semantic_source_identity(self):
        _, record, subject = self.prepare()
        self.mature_candidate(subject)
        source = subject / "inputs/source"
        index = source / ".git/index"
        old_index = index.read_bytes()
        before = trials.snapshot(source)
        readme = source / "README.md"
        stat = readme.stat()
        os.utime(readme, ns=(stat.st_atime_ns, stat.st_mtime_ns + 3_000_000_000))
        trials.engine("inspect_public_candidate")._run_git_bytes(source, "update-index", "--refresh")
        self.assertNotEqual(old_index, index.read_bytes())
        self.assertEqual(before, trials.snapshot(source))
        result = trials.assess(record)
        self.assertTrue(result["facts"]["source_preserved"])
        self.assertTrue(result["facts"]["source_index_preserved"])
        self.assertEqual(result["source_index_observations"][0]["status"], "unchanged")

    def test_legacy_trial_does_not_claim_an_unrecorded_index_baseline(self):
        _, record, subject = self.prepare()
        self.mature_candidate(subject)
        legacy = trials.read_json(record)
        for item in legacy["protected"]:
            del item["semantic_index_before"]
        record.write_text(json.dumps(legacy))
        result = trials.assess(record)
        self.assertNotIn("source_index_preserved", result["facts"])
        self.assertEqual(result["source_index_observations"][0]["status"], "not_observed")
        self.assertTrue(any("no semantic index baseline" in item for item in result["limits"]))

    def test_operator_checkbox_without_trace_cannot_claim_discovery(self):
        _, record, subject = self.prepare()
        data = trials.read_json(record.parent / "observations.template.json")
        data["stages"]["discovery"] = {"status": "observed"}
        filename = record.parent / "observations.json"
        filename.write_text(json.dumps(data))
        with self.assertRaisesRegex(trials.TrialError, "requires_evidence"):
            trials.assess(record, filename)
        trace = record.parent / "trace.txt"
        trace.write_text("Synthetic trace placeholder for infrastructure unit test.\n")
        data["stages"]["discovery"]["evidence"] = [{"path": str(trace), "note": "Unit-test evidence reference; no live host."}]
        filename.write_text(json.dumps(data))
        result = trials.assess(record, filename)
        self.assertEqual(result["operator_observations"]["stages"]["discovery"]["provenance"],
                         "operator_report_not_independent_proof")
        self.assertEqual(result["behavior_acceptance"], "not_automatically_decided")

    def test_observation_binding_rejects_wrong_subject_and_changed_candidate(self):
        _, record, subject = self.prepare()
        target = self.mature_candidate(subject)
        data = trials.read_json(record.parent / "observations.template.json")
        data["candidate_sha256"] = trials.snapshot(target)["sha256"]
        filename = record.parent / "observations.json"
        filename.write_text(json.dumps(data))
        (target / "late-change.txt").write_text("new work")
        with self.assertRaisesRegex(trials.TrialError, "candidate_stale"):
            trials.assess(record, filename)
        data["candidate_sha256"] = None
        data["prompt_sha256"] = "wrong"
        filename.write_text(json.dumps(data))
        with self.assertRaisesRegex(trials.TrialError, "subject_mismatch"):
            trials.assess(record, filename)

    def test_tampered_fixed_contract_is_never_executed(self):
        _, record, subject = self.prepare()
        target = self.mature_candidate(subject)
        sha = trials.snapshot(target)["sha256"]
        expected = {"schema": "openbound-verification/1", "checks": trials.fixed_checks("A")}
        filename = record.parent / ("checks-" + trials.fixed_check_identity(sha, expected) + ".json")
        filename.write_text(json.dumps({"schema": "openbound-verification/1", "checks": []}))
        with self.assertRaisesRegex(trials.TrialError, "fixed_check_contract_changed"):
            trials.assess(record, execute_reviewed=True)

    def test_trusted_contract_or_engine_changes_keep_previous_evidence_immutable(self):
        _, record, subject = self.prepare()
        self.mature_candidate(subject)
        first = trials.assess(record, execute_reviewed=True)
        old_paths = [Path(first["runtime"][key]) for key in ("contract_path", "receipt_path")]
        old_bytes = [item.read_bytes() for item in old_paths]
        revised = trials.fixed_checks("A") + [{"id": "additional-reviewed-check",
                   "argv": ["{python}", "-B", "-c", "print(123)"], "stdout_json_equals": 123}]
        with mock.patch.object(trials, "fixed_checks", return_value=revised):
            second = trials.assess(record, execute_reviewed=True)
        self.assertNotEqual(first["runtime"]["check_identity"], second["runtime"]["check_identity"])
        verifier = trials.engine("verify_public_work")
        new_tool_identity = dict(verifier.tool_identity(), runner_sha256="0" * 64)
        with mock.patch.object(verifier, "tool_identity", return_value=new_tool_identity):
            third = trials.assess(record, execute_reviewed=True)
        self.assertNotEqual(first["runtime"]["check_identity"], third["runtime"]["check_identity"])
        self.assertEqual(old_bytes, [item.read_bytes() for item in old_paths])
        self.assertEqual(first["candidate_sha256"], second["candidate_sha256"])
        self.assertEqual(first["candidate_sha256"], third["candidate_sha256"])

    def test_changed_candidate_resume_preserves_scope_without_revealing_hidden_edit(self):
        _, record, subject = self.prepare()
        target = self.mature_candidate(subject)
        checkpoint_file = record.parent / "checkpoint.json"
        trials.save_new(checkpoint_file, trials.checkpoint(record))
        (target / "hidden-reader-edit.txt").write_text("A retained reader correction.")
        result = trials.resume(record, checkpoint_file)
        self.assertFalse(result["prior_candidate_identity_matches"])
        self.assertNotIn("hidden-reader-edit", result["prompt"])
        self.assertIn("prior scope and permissions still apply", result["prompt"])
        self.assertTrue((target / "hidden-reader-edit.txt").exists())

    def test_candidate_stage_only_change_invalidates_observation_and_recovery_identity(self):
        _, record, subject = self.prepare()
        target = self.mature_candidate(subject)
        trials.git_fixture(target)
        before = trials.assess(record)
        checkpoint_file = record.parent / "checkpoint.json"
        trials.save_new(checkpoint_file, trials.checkpoint(record))
        data = trials.read_json(record.parent / "observations.template.json")
        data["candidate_sha256"] = before["candidate_sha256"]
        observations = record.parent / "observations.json"
        trials.save_new(observations, data)
        normalized = trials.snapshot(target)
        scanner = trials.engine("inspect_public_candidate")
        blob = scanner._run_git_bytes(target, "rev-parse", "HEAD:LICENSE").stdout.decode().strip()
        scanner._run_git_bytes(target, "update-index", "--cacheinfo", "100644," + blob + ",README.md")
        self.assertEqual(normalized, trials.snapshot(target), "Counterexample must alter only the index")
        with self.assertRaisesRegex(trials.TrialError, "candidate_stale"):
            trials.assess(record, observations)
        resumed = trials.resume(record, checkpoint_file)
        self.assertFalse(resumed["prior_candidate_identity_matches"])
        self.assertNotEqual(before["candidate_sha256"], trials.assess(record)["candidate_sha256"])

    def test_candidate_index_refresh_gets_new_immutable_runtime_receipt(self):
        _, record, subject = self.prepare()
        target = self.mature_candidate(subject)
        trials.git_fixture(target)
        first = trials.assess(record, execute_reviewed=True)
        old_paths = [Path(first["runtime"][key]) for key in ("contract_path", "receipt_path")]
        old_bytes = [item.read_bytes() for item in old_paths]
        normalized = trials.snapshot(target)
        readme = target / "README.md"
        info = readme.stat()
        os.utime(readme, ns=(info.st_atime_ns, info.st_mtime_ns + 3_000_000_000))
        trials.engine("inspect_public_candidate")._run_git_bytes(target, "update-index", "--refresh")
        self.assertEqual(normalized, trials.snapshot(target))
        second = trials.assess(record, execute_reviewed=True)
        self.assertNotEqual(first["candidate_sha256"], second["candidate_sha256"])
        self.assertNotEqual(first["runtime"]["check_identity"], second["runtime"]["check_identity"])
        self.assertNotEqual(first["runtime"]["receipt_path"], second["runtime"]["receipt_path"])
        self.assertTrue(second["facts"]["fixed_runtime_checks_passed"])
        self.assertTrue(second["facts"]["candidate_unchanged_by_assessment"])
        self.assertEqual(old_bytes, [item.read_bytes() for item in old_paths])

    def test_readme_directory_is_not_accepted_as_a_public_work_file(self):
        for case in ("B", "C"):
            with self.subTest(case=case):
                _, record, subject = self.prepare(case=case, name="case-" + case)
                target = subject / "candidate"
                (target / "README.md").mkdir(parents=True)
                (target / "notes.txt").write_text("A separate file cannot make README.md a document.\n")
                result = trials.assess(record)
                self.assertFalse(result["facts"]["candidate_has_readme"])
                self.assertEqual(result["deterministic_status"], "failed")

    def test_maintenance_has_real_prior_projection_and_preserves_public_correction(self):
        _, record, subject = self.prepare(case="D")
        self.assertTrue((subject / "private-state/previous-projection.json").is_file())
        public = subject / "inputs/public-v1"
        target = subject / "candidate"
        shutil.copytree(public, target)
        shutil.copyfile(subject / "inputs/private-source/core.py", target / "core.py")
        result = trials.assess(record, execute_reviewed=True)
        self.assertTrue(result["facts"]["source_preserved"])
        self.assertTrue(result["facts"]["public_artifacts_present"])
        self.assertEqual(result["baseline_file_changes"]["README.md"]["status"], "unchanged")
        self.assertTrue(result["facts"]["fixed_runtime_checks_passed"])

    def test_maintenance_guide_adaptation_needs_review_without_automatic_rejection(self):
        _, record, subject = self.prepare(case="D")
        public = subject / "inputs/public-v1"
        target = subject / "candidate"
        shutil.copytree(public, target)
        shutil.copyfile(subject / "inputs/private-source/core.py", target / "core.py")
        guide = target / "README.md"
        guide.write_text(guide.read_text() + "\nUnicode normalization now uses casefold.\n")
        result = trials.assess(record, execute_reviewed=True)
        self.assertTrue(result["facts"]["public_artifacts_present"])
        self.assertEqual(result["baseline_file_changes"]["README.md"]["status"], "changed")
        self.assertEqual(result["baseline_file_changes"]["README.md"]["review"], "independent_review_required")
        self.assertEqual(result["deterministic_status"], "passed_limited_checks")

    def test_negative_trigger_tests_link_fix_not_file_reading(self):
        _, record, subject = self.prepare(case="N9")
        self.assertNotIn("OpenBound", (subject / "prompt.md").read_text())
        before = trials.assess(record)
        self.assertFalse(before["facts"]["requested_link_repaired"])
        readme = subject / "inputs/public/README.md"
        readme.write_text(readme.read_text().replace("examples/old.txt", "examples/current.txt"))
        after = trials.assess(record)
        self.assertEqual(after["deterministic_status"], "passed_limited_checks")
        self.assertEqual(after["operator_observations"]["stages"]["implicit_activation"]["status"], "not_observed")

    def test_blueprint_structural_checks_never_establish_research_claims(self):
        _, record, subject = self.prepare(case="C")
        target = subject / "candidate"
        target.mkdir()
        (target / "README.md").write_text("# A blueprint\n\nAn intentionally inadequate artifact.\n")
        result = trials.assess(record, execute_reviewed=True)
        self.assertEqual(result["runtime"]["status"], "no_fixed_checks_for_this_case")
        self.assertEqual(result["behavior_acceptance"], "not_automatically_decided")
        self.assertIn("semantic fidelity and evidence claims", result["required_review"])


if __name__ == "__main__":
    unittest.main()
