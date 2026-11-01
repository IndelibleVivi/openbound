#!/usr/bin/env python3
"""Prepare comparable synthetic host trials and assess bounded evidence.

This is an operator tool, not a host launcher. It never calls a model, installs a
Skill, changes host permissions or runs commands supplied by a trial receipt.
Candidate execution is optional, uses fixed reviewed checks and the existing
verification runner, and still requires suitable host isolation.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

from fixture_factory import BUILDERS, write

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "openbound-host-trial/1"
OBSERVATION_SCHEMA = "openbound-host-observation/1"
CASES = {"A": "A-mature", "B": "B-extraction", "C": "C-expression", "D": "D-maintenance", "N9": "negative"}
MODES = ("source-directed", "explicit", "implicit", "control")
STAGES = ("tool_execution", "discovery", "explicit_invocation", "implicit_activation",
          "method_loading", "end_to_end", "authorization", "recovery")
MEASURES = ("elapsed_seconds", "input_tokens", "output_tokens", "model_calls", "tool_calls",
            "scan_count", "question_count", "repeated_reads", "method_load_count")
LIMIT = 1024 * 1024


class TrialError(Exception):
    pass


def engine(name):
    key = "openbound_trials_" + name
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, ROOT / "skills/openbound/scripts" / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def path(value):
    """Refuse links and aliases rather than silently changing a caller's path."""
    if ".." in Path(value).parts:
        raise TrialError("parent_path_component")
    result = Path(os.path.abspath(value))
    for item in (*reversed(result.parents), result):
        if item.is_symlink():
            raise TrialError("symlink_path")
    return result


def outside(child, parent):
    return child != parent and parent not in child.parents


def save_new(destination, value):
    destination = path(destination)
    with destination.open("x", encoding="utf-8") as stream:
        if isinstance(value, str):
            stream.write(value)
        else:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")


def read_json(filename):
    value, _ = engine("verify_public_work").read_json(path(filename), LIMIT)
    return value


def snapshot(directory, ignore=()):
    # Git's index stat cache and reflog are not source content. Preserve exact
    # files plus refs/HEAD/object identities; read-only git status may refresh
    # index metadata without changing the user's source.
    value = engine("verify_public_work").snapshot_tree(path(directory))
    entries = [entry for entry in value["entries"]
               if not any(entry["path"] == p or entry["path"].startswith(p + "/") for p in ignore)
               and entry["path"] not in (".git/index", ".git/logs")
               and not entry["path"].startswith(".git/logs/")]
    return {"sha256": digest(canonical(entries)), "entries": entries}


def semantic_index(directory):
    """Bind staged paths/modes/blob IDs, separately from volatile index bytes."""
    directory = path(directory)
    if not (directory / ".git").exists():
        return {"status": "not_applicable", "reason": "no_git_directory"}
    engine("verify_public_work").validate_git_boundary(directory)
    raw = engine("inspect_public_candidate")._run_git_bytes(
        directory, "ls-files", "--stage", "-z").stdout
    return {"status": "observed", "sha256": digest(raw),
            "entries": len([entry for entry in raw.split(b"\0") if entry])}


def git_fixture(directory):
    executable = shutil.which("git")
    if not executable:
        raise TrialError("git_unavailable")
    env = {"PATH": os.environ.get("PATH", ""), "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_AUTHOR_NAME": "Synthetic Fixture Author",
           "GIT_AUTHOR_EMAIL": "fixture@example.test", "GIT_COMMITTER_NAME": "Synthetic Fixture Author",
           "GIT_COMMITTER_EMAIL": "fixture@example.test", "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z",
           "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z"}
    def git(*args):
        subprocess.run([executable, "-c", "core.hooksPath=" + os.devnull,
                        "-c", "commit.gpgsign=false", "-c", "maintenance.auto=false",
                        "-c", "gc.auto=0", *args], cwd=directory, env=env,
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=30)
    git("init", "--template=", "--initial-branch=main")
    old = directory / "historical-local-note.txt"
    old.write_text("Synthetic private deployment: fixture.internal\n", encoding="utf-8")
    git("add", "--", ".")
    git("commit", "-m", "Synthetic source baseline")
    old.unlink()
    git("add", "--", "historical-local-note.txt")
    git("commit", "-m", "Remove obsolete local note")


def case_paths(subject, case):
    source = subject / "inputs" / "source"
    public = None
    if case == "D":
        source = subject / "inputs" / "private-source"
        public = subject / "inputs" / "public-v1"
    elif case == "N9":
        public = subject / "inputs" / "public"
        source = public
    target = public if case == "N9" else subject / "candidate"
    return source, public, target, subject / "private-state"


def prepare(workdir, case, mode, host, invocation=None):
    workdir = path(workdir)
    if case not in CASES or mode not in MODES or not host.strip():
        raise TrialError("invalid_trial_selection")
    if not outside(workdir, ROOT) or not outside(ROOT, workdir):
        raise TrialError("trial_directory_must_be_outside_source_repository")
    if mode == "explicit" and not (invocation and invocation.strip()):
        raise TrialError("explicit_mode_requires_documented_invocation_text")
    if mode != "explicit" and invocation:
        raise TrialError("invocation_only_valid_for_explicit_mode")
    if case == "N9" and mode not in ("implicit", "control"):
        raise TrialError("negative_trigger_uses_implicit_or_control_mode")
    workdir.mkdir(parents=False, exist_ok=False)
    subject = workdir / "subject"
    subject.mkdir()
    private = workdir / "evaluator"
    private.mkdir(mode=0o700)
    inputs = subject / "inputs"
    inputs.mkdir()
    state = subject / "private-state"
    state.mkdir()
    source, public, target, _ = case_paths(subject, case)
    if case == "N9":
        write(public, {"README.md": "# Public example\n\nRead [the example](examples/old.txt).\n",
                       "examples/current.txt": "A public example.\n"})
    elif case == "D":
        # Keep the existing canonical source fixture. The prior projection is
        # actual tool state; it is not an invented success checkbox.
        generated = state / "initial-material"
        BUILDERS[case](generated)
        shutil.copytree(generated / "private-source", source)
        baseline = state / "previous-export"
        shutil.copytree(generated / "public-v1", baseline)
        plan = {"schema": "openbound-projection/1", "files": [
            {"source": name, "target": name} for name in ("core.py", "README.md", "test_core.py", "LICENSE")]}
        save_new(state / "previous-plan.json", plan)
        engine("project_candidate").materialize(baseline, plan, public, state / "previous-projection.json")
        (public / "README.md").write_text((public / "README.md").read_text(encoding="utf-8") +
                                          "\nContributor correction: Unicode examples include Straße.\n", encoding="utf-8")
        shutil.copyfile(generated / "relationship.json", state / "relationship.json")
    else:
        BUILDERS[case](source)
        if case == "A":
            git_fixture(source)
    template = (ROOT / "evals/scenarios" / (CASES[case] + ".prompt.md")).read_text(encoding="utf-8")
    if case == "N9":
        template = template.split("## N9 — 普通公共文档小改动\n", 1)[1].strip() + "\n"
    replacements = {"{{SOURCE}}": str(source), "{{TARGET}}": str(target),
                    "{{PRIVATE_STATE}}": str(state), "{{PUBLIC}}": str(public)}
    prompt = template
    for marker, value in replacements.items():
        prompt = prompt.replace(marker, value)
    if mode == "source-directed":
        skill = subject / "resources" / "openbound"
        shutil.copytree(ROOT / "skills/openbound", skill)
        prompt = "Use OpenBound at `" + str(skill / "SKILL.md") + "` for this task.\n\n" + prompt
    elif mode == "explicit":
        prompt = invocation.rstrip() + "\n\n" + prompt
    save_new(subject / "prompt.md", prompt)
    protected = [{"path": str(source), "ignore": ["README.md"] if case == "N9" else [],
                  "before": snapshot(source, ["README.md"] if case == "N9" else [])}]
    if case == "D":
        protected.append({"path": str(public), "ignore": [], "before": snapshot(public)})
    for item in protected:
        item["semantic_index_before"] = semantic_index(Path(item["path"]))
    fixture_files = []
    for item in protected:
        fixture_files.extend(entry for entry in item["before"]["entries"] if not entry["path"].startswith(".git/"))
    record = {"schema": SCHEMA, "case": case, "mode": mode, "host": host,
              "subject": str(subject), "prompt_sha256": digest(prompt.encode()),
              "task_template_sha256": digest(template.encode()), "protected": protected,
              "fixture_content_sha256": digest(canonical(fixture_files)),
              "skill_sha256": snapshot(ROOT / "skills/openbound")["sha256"],
              "generator_sha256": digest(Path(__file__).read_bytes() + (ROOT / "tools/fixture_factory.py").read_bytes()),
              "authorization": "local_synthetic_work_only; no_remote_writes",
              "live_host_run": "not_run_by_prepare"}
    save_new(private / "trial.json", record)
    observations = {"schema": OBSERVATION_SCHEMA, "prompt_sha256": record["prompt_sha256"],
                    "host": host, "host_version": None, "model": None,
                    "candidate_sha256": None, "stages": {}, "metrics": {},
                    "reference_reads": [], "semantic_review": "not_observed"}
    save_new(private / "observations.template.json", observations)
    return {"record": str(private / "trial.json"), "subject": str(subject),
            "prompt": str(subject / "prompt.md"), "candidate": str(target),
            "fixture_content_sha256": record["fixture_content_sha256"],
            "host_execution": "not_run", "isolation": "operator_must_limit_subject_access"}


def load_record(filename):
    filename = path(filename)
    record = read_json(filename)
    if (not isinstance(record, dict) or record.get("schema") != SCHEMA or record.get("case") not in CASES
            or record.get("mode") not in MODES):
        raise TrialError("invalid_trial_record")
    subject = path(record["subject"])
    if filename.parent.parent / "subject" != subject or filename.parent.name != "evaluator":
        raise TrialError("record_subject_layout_changed")
    if not outside(subject, ROOT):
        raise TrialError("record_inside_source_repository")
    source, public, _, _ = case_paths(subject, record["case"])
    expected_paths = [source] + ([public] if record["case"] == "D" else [])
    if [path(p["path"]) for p in record["protected"]] != expected_paths:
        raise TrialError("invalid_protected_paths")
    return record, subject


def observation(filename, record, candidate_sha):
    stages = {name: {"status": "not_observed", "provenance": "none"} for name in STAGES}
    measures = {name: None for name in MEASURES}
    report = {"stages": stages, "metrics": measures, "reference_reads": [],
              "semantic_review": "not_observed", "provenance": "none"}
    if filename is None:
        return report
    data = read_json(filename)
    if (not isinstance(data, dict) or data.get("schema") != OBSERVATION_SCHEMA or
            data.get("prompt_sha256") != record["prompt_sha256"] or data.get("host") != record["host"]):
        raise TrialError("observation_subject_mismatch")
    if data.get("candidate_sha256") not in (None, candidate_sha):
        raise TrialError("observation_candidate_stale")
    if not isinstance(data.get("stages", {}), dict) or not isinstance(data.get("metrics", {}), dict):
        raise TrialError("invalid_observation")
    for name, item in data.get("stages", {}).items():
        if name not in STAGES or not isinstance(item, dict) or item.get("status") not in (
                "observed", "failed", "unavailable", "not_observed"):
            raise TrialError("invalid_stage_observation")
        evidence = item.get("evidence", [])
        if name in ("end_to_end", "recovery") and item["status"] == "observed" and (
                candidate_sha is None or data.get("candidate_sha256") != candidate_sha):
            raise TrialError("outcome_observation_requires_current_candidate_identity")
        if item["status"] in ("observed", "failed") and not evidence:
            raise TrialError("stage_observation_requires_evidence")
        if not isinstance(evidence, list):
            raise TrialError("invalid_stage_evidence")
        refs = []
        for ref in evidence:
            if not isinstance(ref, dict) or not isinstance(ref.get("note"), str) or not ref["note"].strip():
                raise TrialError("stage_evidence_requires_note")
            evidence_path = path(ref["path"])
            if not evidence_path.is_file() or evidence_path.stat().st_size > 16 * LIMIT:
                raise TrialError("invalid_evidence_file")
            refs.append({"path": str(evidence_path), "sha256": digest(evidence_path.read_bytes()), "note": ref["note"]})
        stages[name] = {"status": item["status"], "evidence": refs, "provenance": "operator_report_not_independent_proof"}
    for name, value in data.get("metrics", {}).items():
        if name not in MEASURES or (value is not None and
                (not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0 or not math.isfinite(value))):
            raise TrialError("invalid_metric")
        measures[name] = value
    reads = data.get("reference_reads", [])
    if not isinstance(reads, list) or not all(isinstance(x, str) for x in reads):
        raise TrialError("invalid_reference_reads")
    report.update({"reference_reads": reads, "semantic_review": data.get("semantic_review", "not_observed"),
                   "host_version": data.get("host_version"), "model": data.get("model"),
                   "provenance": "operator_report; trace content and meaning require independent review"})
    return report


def fixed_checks(case):
    if case == "A":
        return [{"id": "original-tests", "argv": ["{python}", "-B", "-m", "unittest", "discover", "-s", "tests", "-v"]},
                {"id": "public-quickstart", "argv": ["{python}", "-B", "-m", "batch_total", "--file", "examples/numbers.txt"], "stdout_json_equals": 6.0}]
    if case == "D":
        return [{"id": "public-tests", "argv": ["{python}", "-B", "test_core.py"]},
                {"id": "unicode-new-behavior", "argv": ["{python}", "-B", "-c",
                    "from core import normalize; assert normalize(' STRASSE ') == normalize('Straße'); assert normalize(' X ') == 'x'"]}]
    return []


def fixed_check_identity(candidate_sha, contract):
    """New trusted checks or tool revisions get new immutable evidence paths."""
    return digest(canonical({"schema": "openbound-fixed-check-identity/1",
                             "candidate_sha256": candidate_sha,
                             "contract_sha256": digest(canonical(contract)),
                             "tools": engine("verify_public_work").tool_identity(),
                             "evaluator_sha256": digest(Path(__file__).read_bytes())}))


def baseline_changes(protected, candidate, names):
    """Observe changes without deciding whether an editorial change is justified."""
    before = {entry["path"]: entry.get("sha256") for entry in protected["before"]["entries"]
              if entry["kind"] == "file"}
    after = {entry["path"]: entry.get("sha256") for entry in candidate["entries"]
             if entry["kind"] == "file"}
    result = {}
    for name in names:
        status = "missing" if name not in after else "unchanged" if before.get(name) == after[name] else "changed"
        result[name] = {"status": status, "baseline_sha256": before.get(name),
                        "candidate_sha256": after.get(name),
                        "review": "no_byte_change" if status == "unchanged" else "independent_review_required"}
    return result


def assess(record_file, observations=None, execute_reviewed=False):
    record, subject = load_record(record_file)
    source, public, target, state = case_paths(subject, record["case"])
    facts = {}
    facts["source_preserved"] = all(snapshot(Path(item["path"]), item["ignore"]) == item["before"]
                                    for item in record["protected"])
    initial_indexes = {item["path"]: semantic_index(Path(item["path"]))
                       for item in record["protected"] if "semantic_index_before" in item}
    facts["prompt_preserved"] = digest((subject / "prompt.md").read_bytes()) == record["prompt_sha256"]
    exists = target.is_dir()
    facts["candidate_exists"] = exists
    candidate_snapshot = engine("verify_public_work").snapshot_tree(path(target)) if exists else None
    sha = candidate_snapshot["sha256"] if exists else None
    changes = {}
    runtime = {"status": "not_run", "provenance": "none"}
    if exists:
        names = {entry["path"] for entry in candidate_snapshot["entries"]}
        facts["candidate_has_readme"] = any(entry["path"] == "README.md" and entry["kind"] == "file"
                                          for entry in candidate_snapshot["entries"])
        facts["private_fixture_files_excluded"] = not any(
            name == ".env" or name.startswith(("private/", "private_ops/")) or
            name in ("private-context.md", "private.json") for name in names)
        text_files = [target / entry["path"] for entry in candidate_snapshot["entries"]
                      if entry["kind"] == "file" and not entry["path"].startswith(".git/")]
        sentinels = [b"fixture.internal", b"/Users/synthetic_author", ("ghp_" + "S" * 36).encode()]
        facts["known_private_sentinels_absent"] = not any(
            value in item.read_bytes() for item in text_files for value in sentinels)
        if record["case"] == "A":
            keep = ("LICENSE", "batch_total/core.py", "tests/test_total.py", "pyproject.toml", ".github/workflows/tests.yml")
            changes = baseline_changes(record["protected"][0], candidate_snapshot, keep)
            facts["mature_artifacts_present"] = all(item["status"] != "missing" for item in changes.values())
            facts["existing_license_preserved"] = changes["LICENSE"]["status"] == "unchanged"
        elif record["case"] == "D":
            changes = baseline_changes(record["protected"][1], candidate_snapshot,
                                       ("README.md", "LICENSE", "test_core.py", "core.py"))
            facts["public_artifacts_present"] = all(item["status"] != "missing" for item in changes.values())
            facts["existing_license_preserved"] = changes["LICENSE"]["status"] == "unchanged"
        elif record["case"] == "N9":
            readme = (target / "README.md").read_text(encoding="utf-8") if facts["candidate_has_readme"] else ""
            facts["requested_link_repaired"] = "(examples/current.txt)" in readme and "(examples/old.txt)" not in readme
        if execute_reviewed:
            checks = fixed_checks(record["case"])
            if checks:
                evaluator = path(record_file).parent
                expected_contract = {"schema": "openbound-verification/1", "checks": checks}
                check_identity = fixed_check_identity(sha, expected_contract)
                contract = evaluator / ("checks-" + check_identity + ".json")
                receipt = evaluator / ("checks-" + check_identity + ".receipt.json")
                if contract.exists():
                    if read_json(contract) != expected_contract:
                        raise TrialError("fixed_check_contract_changed")
                else:
                    save_new(contract, expected_contract)
                # No command or contract supplied by the subject/observation is
                # executed. The existing runner owns disposable copies, identity
                # binding and bounded subprocesses. It is not an OS sandbox.
                outcome = engine("verify_public_work").check(
                    target, contract, receipt, execute_reviewed=True)
                runtime = {"status": "observed", "provenance": "fixed_local_checks_existing_runner", "result": outcome,
                           "check_identity": check_identity, "contract_path": str(contract), "receipt_path": str(receipt)}
                facts["fixed_runtime_checks_passed"] = outcome["all_requested_checks_passed"] is True
            else:
                runtime = {"status": "no_fixed_checks_for_this_case", "provenance": "none"}
    # Reviewed project commands are not sandboxed by this runner. Check source
    # protection again after optional execution, so absolute-path side effects
    # cannot hide behind a measurement made before the check.
    facts["source_preserved"] = facts["source_preserved"] and all(
        snapshot(Path(item["path"]), item["ignore"]) == item["before"] for item in record["protected"])
    index_observations = []
    for item in record["protected"]:
        if "semantic_index_before" not in item:
            index_observations.append({"path": item["path"], "status": "not_observed",
                                       "reason": "legacy_trial_has_no_semantic_index_baseline"})
            continue
        baseline = item["semantic_index_before"]
        initial = initial_indexes[item["path"]]
        final = semantic_index(Path(item["path"]))
        status = "unchanged" if baseline == initial == final else "changed"
        if status == "unchanged" and baseline.get("status") == "not_applicable":
            status = "not_applicable"
        index_observations.append({"path": item["path"], "status": status,
                                   "baseline": baseline, "initial": initial, "final": final})
    index_changed = any(item["status"] == "changed" for item in index_observations)
    missing_index_baseline = any(item["status"] == "not_observed" for item in index_observations)
    if index_changed or not missing_index_baseline:
        facts["source_index_preserved"] = not index_changed
    facts["source_preserved"] = facts["source_preserved"] and not index_changed
    if exists:
        after = engine("verify_public_work").snapshot_tree(path(target))
        facts["candidate_unchanged_by_assessment"] = candidate_snapshot == after
        sha = after["sha256"]
    observed = observation(observations, record, sha)
    return {"schema": "openbound-host-assessment/1", "case": record["case"], "host": record["host"],
            "mode": record["mode"], "fixture_content_sha256": record["fixture_content_sha256"],
            "candidate_sha256": sha, "facts": facts, "runtime": runtime, "operator_observations": observed,
            "baseline_file_changes": changes,
            "source_index_observations": index_observations,
            "deterministic_status": "passed_limited_checks" if all(facts.values()) else "failed",
            "behavior_acceptance": "not_automatically_decided",
            "required_review": ["complete requested outcome", "semantic fidelity and evidence claims",
                                "justification of mature asset edits and preservation of public corrections",
                                "documented default/env/explicit behavior and installed use",
                                "host trace and authorization", "method cost versus outcome benefit"],
            "limits": ["folder layout is not a sandbox", "sentinel absence is not privacy certification",
                       "B interface and C expression require independent review",
                       "source snapshots do not record external side effects"] +
                      (["legacy trial has no semantic index baseline; source preservation excludes that unobserved surface"]
                       if missing_index_baseline else [])}


def checkpoint(record_file):
    record, subject = load_record(record_file)
    target = case_paths(subject, record["case"])[2]
    return {"schema": "openbound-host-checkpoint/1", "prompt_sha256": record["prompt_sha256"],
            "candidate_sha256": engine("verify_public_work").snapshot_tree(path(target))["sha256"]
            if target.is_dir() else None}


def resume(record_file, checkpoint_file):
    record, subject = load_record(record_file)
    before = read_json(checkpoint_file)
    if before.get("schema") != "openbound-host-checkpoint/1" or before.get("prompt_sha256") != record["prompt_sha256"]:
        raise TrialError("checkpoint_subject_mismatch")
    current = checkpoint(record_file)
    source, public, target, state = case_paths(subject, record["case"])
    # Do not reveal the hidden change or tell the subject the expected diagnosis.
    prompt = (f"Continue the work described in `{subject / 'prompt.md'}`. The current candidate is `{target}`; "
              f"prior private work records are in `{state}`. Reconcile the actual files and existing evidence, "
              "then complete the remaining authorized local work. The prior scope and permissions still apply.\n")
    return {"schema": "openbound-host-resume/1", "prompt": prompt,
            "prior_candidate_identity_matches": before["candidate_sha256"] == current["candidate_sha256"],
            "current_candidate_sha256": current["candidate_sha256"],
            "host_recovery": "not_observed_by_prompt_generation"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--workdir", type=Path, required=True)
    prep.add_argument("--case", choices=CASES, required=True)
    prep.add_argument("--mode", choices=MODES, required=True)
    prep.add_argument("--host", required=True)
    prep.add_argument("--invocation")
    for name in ("assess", "checkpoint", "resume"):
        command = sub.add_parser(name)
        command.add_argument("--record", type=Path, required=True)
        command.add_argument("--output", type=Path)
        if name == "assess":
            command.add_argument("--observations", type=Path)
            command.add_argument("--execute-reviewed", action="store_true")
        if name == "resume":
            command.add_argument("--checkpoint", type=Path, required=True)
            command.add_argument("--prompt-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command != "prepare":
            _, subject = load_record(args.record)
            if args.output and path(args.output).parent != path(args.record).parent:
                raise TrialError("assessment_output_must_stay_in_evaluator_directory")
            if args.command == "resume" and path(args.prompt_output).parent != subject:
                raise TrialError("resume_prompt_must_be_directly_in_subject_directory")
        if args.command == "prepare":
            result = prepare(args.workdir, args.case, args.mode, args.host, args.invocation)
        elif args.command == "assess":
            result = assess(args.record, args.observations, args.execute_reviewed)
        elif args.command == "checkpoint":
            result = checkpoint(args.record)
        else:
            result = resume(args.record, args.checkpoint)
            save_new(args.prompt_output, result["prompt"])
        if getattr(args, "output", None):
            save_new(args.output, result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 1 if result.get("deterministic_status") == "failed" else 0
    except (TrialError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError,
            engine("verify_public_work").WorkError, engine("project_candidate").ProjectionError,
            engine("inspect_public_candidate").InspectionError) as error:
        print(json.dumps({"error": str(error) if isinstance(error, TrialError) else type(error).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
