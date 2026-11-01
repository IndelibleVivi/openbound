"""Synthetic scanner adversaries; all credentials and identities are canaries.

No network, dependency installs, credentials, or git-lfs executable are needed.
The three documented baseline false-completeness cases are exercised against
the byte-exact pinned Public Repo Craft implementation as well as the extension.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
SCRIPT = PACKAGE / "skills" / "openbound" / "scripts" / "inspect_public_candidate.py"
BASELINE = PACKAGE / "provenance" / "baseline" / "inspect_public_candidate.py"
TOKEN = "ghp_" + "SYNTHETIC_CANARY_" * 2
LFS_POINTER = (
    "version https://git-lfs.github.com/spec/v1\n"
    "oid sha256:" + "a" * 64 + "\nsize 123456\n"
)


class ScannerRegressions(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="openbound-scanner-")
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.repo = self.base / "candidate"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Synthetic Inspector")
        self.git("config", "user.email", "inspector@example.invalid")
        self.write("README.md", "# A complete small project\n")
        self.commit("initial")

    def git(self, *args: str, repo: Path | None = None, data: bytes | None = None) -> str:
        result = subprocess.run(["git", "-C", str(repo or self.repo), *args],
                                input=data, capture_output=True, check=True)
        return result.stdout.decode("utf-8", errors="surrogateescape").strip()

    def write(self, relative: str, text: str) -> None:
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def run_scan(self, *args: str, repo: Path | None = None, baseline: bool = False,
                 env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(BASELINE if baseline else SCRIPT), "--repo",
             str(repo or self.repo), "--json", *args],
            capture_output=True, text=True, check=False, env=env,
        )

    def report(self, *args: str, **kwargs) -> dict:
        result = self.run_scan(*args, **kwargs)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(TOKEN, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_pinned_baseline_is_byte_exact(self) -> None:
        data = BASELINE.read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        self.assertEqual(blob, "a590ed0565b80da0d417657de456d025879fb938")

    def test_commit_message_gap_is_fixed_against_baseline(self) -> None:
        self.write("README.md", "# Updated complete project\n")
        self.commit("private note " + TOKEN)
        args = ("--candidate", "none", "--candidate-ref", "HEAD", "--history-ref", "HEAD")
        old = self.report(*args, baseline=True)
        self.assertEqual(old["findings"], [])
        self.assertTrue(old["scan_complete"])
        new = self.report(*args)
        scopes = {item["scope"] for item in new["findings"] if item["rule_id"] == "secret.github-token"}
        self.assertEqual(scopes, {"ref-metadata", "history-metadata"})
        self.assertTrue(all(item["path"].startswith("commit:") for item in new["findings"]))
        self.assertFalse(new["claims"]["no_rule_matches_on_observed_surfaces"])
        self.assertFalse(new["claims"]["publication_ready"])

    def test_candidate_ref_checks_its_metadata_without_implicitly_selecting_history(self) -> None:
        self.git("commit", "--allow-empty", "-q", "-m", TOKEN)
        report = self.report("--candidate", "none", "--candidate-ref", "HEAD")
        self.assertFalse(report["scan_scope"]["history"]["enabled"])
        self.assertTrue(any(item["scope"] == "ref-metadata" for item in report["findings"]))
        self.assertTrue(report["scan_complete"])

    def test_annotated_tag_metadata_is_selected_explicitly(self) -> None:
        self.git("tag", "-a", "v-test", "-m", "tag note " + TOKEN)
        ordinary = self.report("--candidate", "none", "--candidate-ref", "HEAD", "--history-ref", "HEAD")
        self.assertEqual(ordinary["findings"], [])
        tagged = self.report("--candidate", "none", "--candidate-ref", "v-test", "--history-ref", "v-test")
        tags = [item for item in tagged["findings"] if item["path"].startswith("tag:")]
        self.assertEqual({item["scope"] for item in tags}, {"ref-metadata", "history-metadata"})
        self.assertEqual(tagged["scan_scope"]["ref"]["metadata"]["counts"]["tag_objects_scanned"], 1)

    def shallow_clone(self) -> Path:
        self.write("removed.txt", TOKEN)
        self.commit("old private data")
        (self.repo / "removed.txt").unlink()
        self.commit("current complete project")
        clone = self.base / "shallow"
        subprocess.run(["git", "clone", "--quiet", "--depth", "1", self.repo.as_uri(), str(clone)],
                       capture_output=True, check=True)
        return clone

    def test_shallow_no_hit_is_incomplete_against_baseline(self) -> None:
        clone = self.shallow_clone()
        args = ("--candidate", "none", "--candidate-ref", "HEAD", "--history-ref", "HEAD")
        old = self.report(*args, repo=clone, baseline=True)
        self.assertTrue(old["scan_complete"])
        new = self.report(*args, repo=clone)
        self.assertEqual(new["findings"], [])
        self.assertFalse(new["scan_complete"])
        self.assertIn("history.shallow_boundary", new["coverage_limited_by"])
        facet = next(f for f in new["coverage"]["facets"] if f["surface"] == "history.ancestry")
        self.assertEqual(facet["status"], "unobserved")
        self.assertEqual(self.git("rev-list", "--count", "HEAD", repo=clone), "1")

    def test_shallow_does_not_force_unrequested_history_work(self) -> None:
        clone = self.shallow_clone()
        report = self.report("--candidate", "none", "--candidate-ref", "HEAD", repo=clone)
        self.assertTrue(report["scan_complete"])
        self.assertNotIn("history.shallow_boundary", report["coverage_limited_by"])
        facet = next(f for f in report["coverage"]["facets"] if f["surface"] == "history.ancestry")
        self.assertEqual(facet["status"], "not_selected")

    def test_lfs_pointer_never_substitutes_for_payload_against_baseline(self) -> None:
        self.write("asset.bin", LFS_POINTER)
        self.commit("publish pointer")
        args = ("--candidate-ref", "HEAD", "--history-ref", "HEAD")
        old = self.report(*args, baseline=True)
        self.assertTrue(old["scan_complete"])
        # A cached object is still not scanned implicitly and is never fetched.
        cached = self.repo / ".git" / "lfs" / "objects" / "aa" / "aa" / ("a" * 64)
        cached.parent.mkdir(parents=True)
        cached.write_text(TOKEN)
        new = self.report(*args)
        self.assertFalse(new["scan_complete"])
        for label in ("working-tree", "index", "ref", "history"):
            self.assertIn(label + ".lfs_payload", new["coverage_limited_by"])
        self.assertEqual({item["rule_id"] for item in new["findings"]}, {"lfs-payload-unobserved"})
        self.assertEqual(cached.read_text(), TOKEN)

    def test_malformed_pointer_is_not_classified_as_a_payload(self) -> None:
        self.write("asset.bin", "version https://git-lfs.github.com/spec/v1\ninvalid oid\n")
        report = self.report()
        self.assertFalse(report["scan_complete"])
        self.assertTrue(any(item["rule_id"] == "malformed-lfs-pointer" for item in report["findings"]))

    def test_explicit_symbolic_placeholders_do_not_hide_provider_shaped_keys(self) -> None:
        self.write(".env.example", "API_KEY=YOUR_API_KEY\nTOKEN=EXAMPLE_TOKEN\nsecret=<REPLACE_ME>\n")
        ordinary = self.report()
        self.assertEqual(ordinary["findings"], [])
        self.write(".env.example", "TOKEN=" + TOKEN + "\n")
        report = self.report()
        self.assertTrue(any(item["rule_id"] == "secret.github-token" for item in report["findings"]))

    def test_subject_and_rule_bindings_are_deterministic_and_follow_selected_bytes(self) -> None:
        first = self.report()
        second = self.report()
        self.assertEqual(first, second)
        self.assertEqual(first["rules"]["sha256"], hashlib.sha256(SCRIPT.read_bytes()).hexdigest())
        self.write("README.md", "# Changed working bytes\n")
        changed = self.report()
        self.assertNotEqual(first["subject"]["id"], changed["subject"]["id"])
        surfaces1, surfaces2 = first["subject"]["surfaces"], changed["subject"]["surfaces"]
        self.assertEqual(surfaces1["index"], surfaces2["index"])
        self.assertNotEqual(surfaces1["working-tree"], surfaces2["working-tree"])
        self.git("add", "README.md")
        staged = self.report()
        self.assertNotEqual(changed["subject"]["surfaces"]["index"], staged["subject"]["surfaces"]["index"])

    def test_metadata_only_change_changes_subject_with_identical_tree(self) -> None:
        first = self.report("--candidate", "none", "--candidate-ref", "HEAD")
        self.git("commit", "--allow-empty", "-q", "-m", "new public explanation")
        second = self.report("--candidate", "none", "--candidate-ref", "HEAD")
        self.assertEqual(first["scan_scope"]["ref"]["identity"], second["scan_scope"]["ref"]["identity"])
        self.assertNotEqual(first["subject"]["id"], second["subject"]["id"])

    def test_large_binary_skip_is_still_bound_to_exact_worktree_bytes(self) -> None:
        self.write("large.dat", "A" * 4096)
        (self.repo / "binary.dat").write_bytes(b"\0unreadable-text")
        first = self.report("--candidate", "working-tree", "--max-bytes", "128")
        self.assertFalse(first["scan_complete"])
        self.assertIn("working-tree.large", first["coverage_limited_by"])
        self.assertIn("working-tree.binary", first["coverage_limited_by"])
        self.write("large.dat", "A" * 4095 + "B")
        second = self.report("--candidate", "working-tree", "--max-bytes", "128")
        self.assertNotEqual(first["subject"]["id"], second["subject"]["id"])

    def test_invalid_refs_and_paths_do_not_echo_sensitive_input(self) -> None:
        for args in (("--history-ref", TOKEN), ("--candidate-ref", "--" + TOKEN),
                     ("--candidate-ref", "HEAD.." + TOKEN), ("--candidate-ref", "HEAD:" + TOKEN),
                     ("--candidate", TOKEN), ("--unknown-" + TOKEN,)):
            with self.subTest(args=args):
                result = self.run_scan(*args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertNotIn(TOKEN, result.stderr)
        result = self.run_scan(repo=self.base / TOKEN)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(TOKEN, result.stderr)

    def test_content_canaries_in_paths_branch_root_and_remotes_are_not_echoed(self) -> None:
        self.write(TOKEN + ".txt", "public contents\n")
        self.git("checkout", "-q", "-b", TOKEN)
        self.git("remote", "add", "origin", "https://example.invalid/" + TOKEN)
        renamed = self.base / ("private-" + TOKEN)
        self.repo.rename(renamed)
        self.repo = renamed
        report = self.report()
        self.assertEqual(report["repository"]["root"], "<redacted>")
        self.assertTrue(report["repository"]["branch"].startswith("redacted:"))

    def test_scanner_never_runs_filters_fsmonitor_hooks_or_auth_helpers(self) -> None:
        markers = [self.base / name for name in ("filter-ran", "monitor-ran", "hook-ran", "auth-ran")]
        self.write(".gitattributes", "*.txt filter=untrusted\n")
        self.write("document.txt", "before\n")
        self.commit("plain fixture")
        self.git("config", "filter.untrusted.clean", "touch " + str(markers[0]))
        self.git("config", "filter.untrusted.process", "touch " + str(markers[0]))
        self.git("config", "filter.untrusted.required", "true")
        self.git("config", "core.fsmonitor", "touch " + str(markers[1]))
        hook = self.repo / ".git" / "hooks" / "post-index-change"
        hook.write_text("#!/bin/sh\ntouch " + str(markers[2]) + "\n")
        hook.chmod(0o755)
        self.git("config", "credential.helper", "!touch " + str(markers[3]))
        self.git("remote", "add", "origin", "https://example.invalid/private.git")
        self.write("document.txt", "after\n")
        report = self.report()
        self.assertTrue(report["scan_scope"]["working_tree"]["enabled"])
        self.assertFalse(any(path.exists() for path in markers))

    def test_ambient_git_environment_cannot_redirect_the_candidate(self) -> None:
        outside = self.base / "outside-index"
        env = dict(os.environ, GIT_INDEX_FILE=str(outside), GIT_DIR=str(self.base / "missing"),
                   GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="core.fsmonitor", GIT_CONFIG_VALUE_0=TOKEN)
        report = self.report(env=env)
        self.assertEqual(report["scan_scope"]["index"]["counts"]["listed_paths"], 1)
        self.assertFalse(outside.exists())

    def test_symlink_payload_is_never_dereferenced(self) -> None:
        outside = self.base / "outside-secret.txt"
        outside.write_text(TOKEN)
        os.symlink(outside, self.repo / "external-link")
        report = self.report()
        self.assertTrue(any(item["rule_id"] == "external-symlink" for item in report["findings"]))
        self.assertFalse(any(item["rule_id"].startswith("secret.") for item in report["findings"]))

    def test_symlink_ancestor_cannot_read_outside_worktree(self) -> None:
        self.write("nested/data.txt", "public\n")
        self.commit("nested public file")
        shutil.rmtree(self.repo / "nested")
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "data.txt").write_text(TOKEN)
        os.symlink(outside, self.repo / "nested")
        result = self.run_scan()
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(TOKEN, result.stdout + result.stderr)

    def test_empty_selection_cannot_claim_completion(self) -> None:
        report = self.report("--candidate", "none")
        self.assertFalse(report["scan_complete"])
        self.assertIn("no-content-surface-selected", report["coverage_limited_by"])

    def test_cli_failure_exit_codes_are_separate_from_observations(self) -> None:
        self.write("secret.txt", TOKEN)
        observed = self.run_scan()
        self.assertEqual(observed.returncode, 0)
        matched = self.run_scan("--fail-on-findings")
        self.assertEqual(matched.returncode, 1)
        self.write("asset.bin", LFS_POINTER)
        incomplete = self.run_scan("--fail-on-findings", "--fail-on-incomplete")
        self.assertEqual(incomplete.returncode, 3)
        self.assertFalse(json.loads(incomplete.stdout)["scan_complete"])

    def test_read_only_scan_does_not_mutate_git_or_source_files(self) -> None:
        def snapshot() -> dict[str, str]:
            return {str(path.relative_to(self.repo)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in self.repo.rglob("*") if path.is_file()}
        before = snapshot()
        self.report("--candidate-ref", "HEAD", "--history-ref", "HEAD")
        self.assertEqual(before, snapshot())

    def test_replace_refs_cannot_hide_original_commit_metadata(self) -> None:
        self.git("commit", "--allow-empty", "-q", "-m", TOKEN)
        original = self.git("rev-parse", "HEAD")
        self.git("commit", "--amend", "--allow-empty", "-q", "-m", "benign replacement")
        replacement = self.git("rev-parse", "HEAD")
        self.git("replace", original, replacement)
        report = self.report("--candidate", "none", "--candidate-ref", original)
        self.assertTrue(any(item["rule_id"] == "secret.github-token" for item in report["findings"]))

    def test_non_utf8_metadata_reports_gap_while_retaining_ascii_signal(self) -> None:
        original = self.git("cat-file", "commit", "HEAD").encode()
        headers = original.split(b"\n\n", 1)[0]
        raw = headers + b"\n\nlatin-1 \xe9 " + TOKEN.encode() + b"\n"
        oid = self.git("hash-object", "-t", "commit", "-w", "--stdin", data=raw)
        report = self.report("--candidate", "none", "--candidate-ref", oid)
        self.assertFalse(report["scan_complete"])
        self.assertIn("ref.metadata_non_utf8", report["coverage_limited_by"])
        self.assertTrue(any(item["rule_id"] == "secret.github-token" for item in report["findings"]))

    def test_missing_promisor_object_fails_closed_without_fetch_or_helper(self) -> None:
        blob = self.git("rev-parse", "HEAD:README.md")
        marker = self.base / "transport-ran"
        self.git("remote", "add", "origin", "ext::sh -c touch% " + str(marker))
        self.git("config", "remote.origin.promisor", "true")
        self.git("config", "remote.origin.partialclonefilter", "blob:none")
        self.git("config", "protocol.ext.allow", "always")
        (self.repo / ".git" / "objects" / blob[:2] / blob[2:]).unlink()
        result = self.run_scan("--candidate", "none", "--candidate-ref", "HEAD", "--history-ref", "HEAD")
        # Some Git versions report a missing object as a coverage gap; others
        # fail during traversal. Both are honest and neither may fetch it.
        if result.returncode == 0:
            self.assertFalse(json.loads(result.stdout)["scan_complete"])
        else:
            self.assertEqual(result.returncode, 2)
        self.assertFalse(marker.exists())
        self.assertNotIn(TOKEN, result.stdout + result.stderr)

    def test_unmerged_index_is_unobserved_and_bound_to_conflict_objects(self) -> None:
        self.write("conflict.txt", "base\n")
        self.commit("base file")
        self.git("checkout", "-q", "-b", "feature")
        self.write("conflict.txt", TOKEN + "\n")
        self.commit("feature variation")
        self.git("checkout", "-q", "main")
        self.write("conflict.txt", "main variation\n")
        self.commit("main variation")
        merge = subprocess.run(["git", "-C", str(self.repo), "merge", "feature"], capture_output=True)
        self.assertNotEqual(merge.returncode, 0)
        report = self.report("--candidate", "index")
        self.assertFalse(report["scan_complete"])
        self.assertIn("index.unmerged_index", report["coverage_limited_by"])
        self.assertIsNotNone(report["subject"]["surfaces"]["index"]["unmerged_identity"])

    def test_graft_boundary_cannot_claim_complete_ancestry(self) -> None:
        self.write("earlier.txt", TOKEN)
        self.commit("earlier")
        (self.repo / "earlier.txt").unlink()
        self.commit("later")
        head = self.git("rev-parse", "HEAD")
        graft = self.repo / ".git" / "info" / "grafts"
        graft.write_text(head + "\n")
        report = self.report("--candidate", "none", "--history-ref", "HEAD")
        self.assertFalse(report["scan_complete"])
        self.assertIn("history.grafted_ancestry", report["coverage_limited_by"])

    def test_git_log_signature_config_cannot_execute_a_verifier(self) -> None:
        original = self.git("cat-file", "commit", "HEAD").encode()
        headers, message = original.split(b"\n\n", 1)
        raw = headers + b"\ngpgsig -----BEGIN PGP SIGNATURE-----\n invalid\n -----END PGP SIGNATURE-----\n\n" + message
        oid = self.git("hash-object", "-t", "commit", "-w", "--stdin", data=raw)
        self.git("update-ref", "refs/heads/signed", oid)
        marker = self.base / "verifier-ran"
        verifier = self.base / "untrusted-verifier.sh"
        verifier.write_text("#!/bin/sh\ntouch " + str(marker) + "\nexit 1\n")
        verifier.chmod(0o755)
        self.git("config", "gpg.program", str(verifier))
        self.git("config", "log.showSignature", "true")
        self.report("--candidate", "none", "--history-ref", "signed")
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
