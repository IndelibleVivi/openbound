#!/usr/bin/env python3
"""Run four complete local synthetic publication-preparation scenarios.

These are deterministic engineering scenarios, NOT model/host activation evals.
No network, installation, remote writes or source project commands are executed.
Known authored fixture checks run via verify_public_work in disposable copies.
All run data stays in a newly created --workdir. Never reuse an existing directory.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time

from fixture_factory import build_mature, build_extraction, build_research, build_maintenance, write

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/openbound/scripts"


def module(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


p = module("project_candidate")
v = module("verify_public_work")


def save(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def selection(root):
    return [{"source": x.relative_to(root).as_posix(), "target": x.relative_to(root).as_posix()}
            for x in sorted(root.rglob("*")) if x.is_file()]


def project(case, source, plan, target_name="public-candidate"):
    state = case / "state"
    state.mkdir(exist_ok=True)
    target = case / target_name
    plan_path = state / (target_name + ".plan.json")
    receipt = state / (target_name + ".projection.json")
    save(plan_path, plan)
    outcome = p.materialize(source, plan, target, receipt)
    p.verify(target, receipt, source, plan)
    return target, receipt, outcome


def verify(case, target, checks, witnesses=None, name="verification"):
    contract_path = case / "state" / (name + ".contract.json")
    receipt_path = case / "state" / (name + ".receipt.json")
    contract = {"schema": v.SCHEMA, "checks": checks, "witnesses": witnesses or [],
                "inspection": {"candidate_mode": "both"}}
    save(contract_path, contract)
    result = v.check(target, contract_path, receipt_path, execute_reviewed=True)
    require(result["fresh"], "verification binding stale")
    require(result["all_requested_checks_passed"] is not False, "requested check failed")
    require(result["scanner_findings"] == 0, "unexpected candidate scanner finding")
    require(result["scanner_selected_surfaces_exhausted"], "candidate text coverage gap")
    require(not result["publication_ready"], "runner overclaimed publication")
    return result, contract_path, receipt_path


def run_mature(case):
    source = case / "source"
    build_mature(source)
    before = v.snapshot_tree(source)
    entries = [entry for entry in selection(source)
               if entry["source"] != ".env" and not entry["source"].startswith("private/")]
    for entry in entries:
        if entry["source"] == "README.md":
            entry["replacements"] = [{"old": "cd /Users/synthetic_author/work/batch-total",
                                      "new": "cd batch-total", "expected_count": 1}]
        if entry["source"] == "batch_total/__main__.py":
            entry["replacements"] = [{"old": "/Users/synthetic_author/data/numbers.txt",
                                      "new": "examples/numbers.txt", "expected_count": 1}]
    plan = {"schema": p.PLAN_SCHEMA, "files": entries}
    target, projection, outcome = project(case, source, plan)
    checks = [{"id": "existing-tests", "argv": ["{python}", "-m", "unittest", "discover", "-s", "tests", "-v"]},
              {"id": "public-quickstart", "argv": ["{python}", "-m", "batch_total", "--file", "examples/numbers.txt"],
               "stdout_json_equals": 6.0},
              {"id": "public-default", "argv": ["{python}", "-m", "batch_total"], "stdout_json_equals": 6.0}]
    result, contract, evidence = verify(case, target, checks)
    preserved = ["LICENSE", "batch_total/core.py", "tests/test_total.py", "pyproject.toml", ".github/workflows/tests.yml"]
    require(all((source / name).read_bytes() == (target / name).read_bytes() for name in preserved),
            "mature assets unnecessarily rewritten")
    require(not (target / ".env").exists() and not (target / "private").exists(), "private selection leak")
    require(before == v.snapshot_tree(source), "private source was modified")
    repeat = p.materialize(source, plan, target, projection)
    require(repeat["status"] == "no_change", "repeat altered candidate")
    require(v.check(target, contract, evidence)["reused"], "repeat reran checks")
    return {"status": "passed", "candidate": "A/public-candidate", "preserved_files": preserved,
            "changed_files": ["README.md", "batch_total/__main__.py"],
            "excluded": [".env", "private/local.json"], "source_unchanged": True,
            "repeat": "no_change_and_receipt_reused", "verification": result,
            "workflow_ci": "source_preserved; GitHub execution not observed",
            "artifact_level_operations": {"materialize": 1, "projection_verify": 1,
                                          "verification_session": 1, "executable_checks": 3,
                                          "repeat_negative_probes": 2},
            "overhead_scope": "deterministic fixture operations only; no Agent/control speedup claim"}


PUBLIC_COMPONENT_README = """# Cursor collection reference

Collect a stable paginated sequence through an injected `fetch_batch(cursor, limit)`
callback. The callback returns `(items, next_cursor)`, using `None` for completion.
The package has no private client dependency and uses only Python 3.10+.

```sh
python3 -m unittest discover -s tests -v
python3 witness.py complete
python3 witness.py naive
```

Both commands use the same newly authored synthetic queue: 37 ordered records,
page limit 8. The complete loop returns 37 and the intentionally naive first-page
reader returns 8. This demonstrates the boundary mechanism; it does not reproduce
the author's private environment or measure production performance.

Stable cursors and stable record identities are required. Concurrent mutation,
expired/repeating cursors and exactly-once side effects remain outside this
reference implementation. This is a reference component, not a hosted service.
Derived from the author's private `services/pager.py`, retaining its MIT license;
the public seam, synthetic client, tests and explanations are new adaptations.
"""

COMPONENT_WITNESS = """import json
import sys
from pager import collect

records = list(range(37))
def fetch_batch(cursor, limit):
    start = 0 if cursor is None else cursor
    end = min(start + limit, len(records))
    return records[start:end], (end if end < len(records) else None)

mode = sys.argv[1]
result = collect(fetch_batch, 8) if mode == 'complete' else fetch_batch(None, 8)[0]
print(json.dumps({'count': len(result), 'ids': result}))
"""

COMPONENT_TEST = """import unittest
from pager import collect

class PagerTests(unittest.TestCase):
    def test_all_pages_and_order(self):
        rows = list(range(37))
        def fetch(cursor, limit):
            start = cursor or 0
            end = min(start + limit, len(rows))
            return rows[start:end], end if end < len(rows) else None
        self.assertEqual(collect(fetch, 8), rows)
    def test_empty(self):
        self.assertEqual(collect(lambda cursor, limit: ([], None)), [])
"""


def run_extraction(case):
    source = case / "source"
    build_extraction(source)
    before = v.snapshot_tree(source)
    # Private editorial workspace: copied original + newly authored public files.
    # Its receipt binds this workspace. The original-copy hashes remain separate.
    workspace = case / "editorial-workspace"
    write(workspace, {"original/pager.py": (source / "services/pager.py").read_text(),
                      "LICENSE": (source / "LICENSE").read_text(),
                      "README.md": PUBLIC_COMPONENT_README,
                      "witness.py": COMPONENT_WITNESS,
                      "tests/test_pager.py": COMPONENT_TEST})
    original_digest = v.digest((source / "services/pager.py").read_bytes())
    entries = selection(workspace)
    entry = next(x for x in entries if x["source"] == "original/pager.py")
    entry["target"] = "pager.py"
    entry["replacements"] = [
        {"old": "from private_ops.client import fetch_batch\n", "new": "# Public callback supplied by caller.\n", "expected_count": 1},
        {"old": "def collect(limit=8):", "new": "def collect(fetch_batch, limit=8):", "expected_count": 1}]
    target, _, _ = project(case, workspace, {"schema": p.PLAN_SCHEMA, "files": entries})
    checks = [{"id": "independent-tests", "argv": ["{python}", "-m", "unittest", "discover", "-s", "tests", "-v"]},
              {"id": "complete", "argv": ["{python}", "witness.py", "complete"],
               "stdout_json_equals": {"count": 37, "ids": list(range(37))}},
              {"id": "naive", "argv": ["{python}", "witness.py", "naive"],
               "stdout_json_equals": {"count": 8, "ids": list(range(8))}}]
    witnesses = [{"id": "page-limit-is-not-backlog", "positive": "complete", "negative": "naive", "relation": "different_json"}]
    result, _, _ = verify(case, target, checks, witnesses)
    require(before == v.snapshot_tree(source), "private source modified")
    require("private_ops" not in (target / "pager.py").read_text(), "private import remains")
    # Deliberately bad synthetic data erases the distinction. It must fail.
    bad = case / "bad-example"
    shutil.copytree(target, bad)
    (bad / "witness.py").write_text(COMPONENT_WITNESS.replace("range(37)", "range(5)"))
    bad_contract = case / "state" / "bad.contract.json"
    save(bad_contract, {"schema": v.SCHEMA,
                        "checks": [{"id": "complete", "argv": ["{python}", "witness.py", "complete"]},
                                   {"id": "naive", "argv": ["{python}", "witness.py", "naive"]}],
                        "witnesses": witnesses})
    rejected = v.check(bad, bad_contract, case / "state" / "bad.receipt.json", True)
    require(rejected["failed_witnesses"] == 1, "mechanism-erasing example accepted")
    return {"status": "passed", "candidate": "B/public-candidate", "original_component_sha256": original_digest,
            "source_unchanged": True, "private_dependency_removed": True, "verification": result,
            "counterexample": "5-item substitution rejected: both implementations return all 5",
            "provenance_scope": "original component copied to private editorial workspace; authored additions identified above"}


PUBLIC_BLUEPRINT = """# A continuation ledger for interrupted queue work

**Status: research blueprint; the proposed ledger is unimplemented.**

## The problem

A query page limit controls the size of one response. A backlog describes work
remaining across responses. Confusing them can silently drop most of the work.
The intended reader is an engineer designing resumable processing who needs a
testable question before committing to a more elaborate architecture.

## What is known, and how

The author reports one private manual simulation with 37 items and a page limit
of 8: the first response contained 8, while continued cursor reads reached 37.
The underlying private trace is unavailable for publication. This is an attributed
observation, not an independently verified experiment or production benchmark.

The 37/8 numbers below are a newly authored synthetic illustration. They preserve
the distinction between page size and backlog. They do not establish a speedup,
delivery guarantee or outcome in the original private environment.

## Proposed mechanism

Maintain four explicit concepts: total intended work, page boundary, identities
whose effects were accepted, and the resume cursor. After interruption, reconcile
identities before accepting the next cursor. The conjecture is that this ledger
could make duplicate handling more explicit. No implementation or measured
benefit is claimed.

| Boundary | Proposed retained fact | Open question |
| --- | --- | --- |
| Fetch | Page and next cursor | Can the cursor expire? |
| Accept effect | Stable item identity | What makes identity stable? |
| Resume | Accepted identities plus cursor | Which operation is atomic? |

## Counterexample and falsification plan

Replacement or reordering of item IDs can cause a ledger to skip new work or
repeat old effects while the cursor still appears valid. Stable IDs cannot be
assumed without an explicit source contract.

Build a fake provider with 37 records and limit 8; compare one-page collection
with cursor traversal. Then interrupt after the first accepted effect, restart,
replace an ID, reorder a page, expire a cursor, and inject a failure between effect
and checkpoint. Count accepted effects per semantic item. A duplicate or missing
effect falsifies an exactly-once claim under those conditions. Passing one stable
queue would only support that bounded case, not the general conjecture.

## Invitation and provenance

This text develops the author's unfinished private notes. The structured mechanism,
table and proposed falsification procedure are new editorial elaborations. Feedback
on assumptions and counterexamples is useful; there is no runtime API or maintenance
promise. Rights for public distribution of the original notes remain for the author
to decide; this local candidate is prepared for review, not represented as published.
"""


def run_research(case):
    source = case / "source"
    build_research(source)
    before = v.snapshot_tree(source)
    workspace = case / "editorial-workspace"
    write(workspace, {"README.md": PUBLIC_BLUEPRINT})
    target, _, _ = project(case, workspace, {"schema": p.PLAN_SCHEMA, "files": selection(workspace)})
    result, _, _ = verify(case, target, [])
    text = (target / "README.md").read_text()
    required = ["unimplemented", "author reports", "unavailable for publication", "newly authored",
                "Replacement or reordering", "falsifies", "Rights for public distribution"]
    require(all(item in text for item in required), "editorial fixture lost evidence boundary")
    require("fixture.internal" not in text and "/Users/" not in text, "private context copied")
    require(result["all_requested_checks_passed"] is None, "blueprint asserted executable success")
    require(before == v.snapshot_tree(source), "private notes changed")
    return {"status": "passed", "candidate": "C/public-candidate", "source_unchanged": True,
            "verification": result, "editorial_check": "controlled fixture assertions only",
            "not_proven": ["human comprehension", "model semantic judgment", "research hypothesis", "license grant"],
            "agent_evaluation": "separately recorded if run; not inferred from this deterministic scenario"}


def run_maintenance(case):
    source = case / "source"
    build_maintenance(source)
    before = v.snapshot_tree(source)
    workspace = case / "editorial-workspace"
    shutil.copytree(source / "public-v1", workspace)
    (workspace / "core.py").write_bytes((source / "private-source/core.py").read_bytes())
    (workspace / "test_core.py").write_text((workspace / "test_core.py").read_text().replace(
        "print('ok')", "assert normalize(' STRASSE ') == normalize('Straße')\nprint('ok')"))
    target, projection, _ = project(case, workspace, {"schema": p.PLAN_SCHEMA, "files": selection(workspace)})
    result, contract, receipt = verify(case, target, [{"id": "existing-and-new-behavior", "argv": ["{python}", "test_core.py"]}])
    require((target / "README.md").read_bytes() == (source / "public-v1/README.md").read_bytes(), "public-owned guide overwritten")
    require(before == v.snapshot_tree(source), "private or public v1 source modified")
    require(not (target / "private.json").exists(), "private settings leaked")
    # The previous valid receipt cannot endorse an independently edited candidate.
    (target / "UNREVIEWED.md").write_text("A new public edit needs review.\n")
    try:
        p.verify(target, projection)
    except p.ProjectionError:
        drift_rejected = True
    else:
        drift_rejected = False
    require(drift_rejected, "projection drift undetected")
    require(not v.status(target, contract, receipt)["fresh"], "verification drift undetected")
    # This file is deliberately introduced by this scenario and is removed only
    # after the refusal is observed; no production/user files are cleaned.
    (target / "UNREVIEWED.md").unlink()
    require(v.status(target, contract, receipt)["fresh"], "restored exact candidate remains stale")
    return {"status": "passed", "candidate": "D/public-candidate", "source_unchanged": True,
            "public_v1_unchanged": True, "public_owned_readme_preserved": True,
            "verification": result, "unexpected_public_edit": "refused_and_evidence_stale",
            "inbound_code_execution": "not attempted; host sandbox required for untrusted contributions",
            "independent_public_future": "relationship can end without copying private control material into public repo"}


def run(workdir):
    workdir.mkdir(parents=True, exist_ok=False)
    results = {}
    for name, operation in (("A", run_mature), ("B", run_extraction), ("C", run_research), ("D", run_maintenance)):
        case = workdir / name
        case.mkdir()
        begin = time.monotonic()
        result = operation(case)
        result["elapsed_seconds"] = round(time.monotonic() - begin, 6)
        results[name] = result
    report = {"schema": "openbound-scenario-results/1", "kind": "deterministic_synthetic_e2e",
              "results": results, "external_writes": "none", "model_activation": "not_tested_by_this_runner"}
    save(workdir / "results.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = run(args.workdir)
    except FileExistsError:
        print(json.dumps({"error": "workdir_exists_choose_new_directory"}))
        return 2
    except Exception as error:
        print(json.dumps({"error": "scenario_failed", "type": type(error).__name__}))
        return 1
    print(json.dumps({"passed_scenarios": list(report["results"]), "kind": report["kind"], "external_writes": "none"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
