from __future__ import annotations

# The 11 Public Repo Craft baseline cases are retained. Only the relocated
# script path and intentional v2 output redaction expectations differ.

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "openbound" / "scripts" / "inspect_public_candidate.py"


class InspectPublicCandidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.repo = self.base / "candidate"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Inspector Test")
        self.git("config", "user.email", "inspector@example.invalid")

    def git(self, *args: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(self.repo), *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout

    def write_text(self, relative: str, content: str) -> Path:
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def commit_all(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def run_inspector(
        self,
        *extra: str,
        repo: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repo",
                str(repo or self.repo),
                "--json",
                *extra,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_scans_tracked_and_nonignored_untracked_current_candidate(self) -> None:
        fake_github_token = "ghp_" + ("A" * 32)
        self.write_text("README.md", "# Candidate\n")
        self.write_text(".gitignore", ".env.ignored\n")
        self.write_text(".env", f"TOKEN={fake_github_token}\n")
        self.write_text("docs/local.md", "See /Users/example/workbench/output.json\n")
        self.write_text(
            ".github/workflows/release.yml",
            "permissions:\n  contents: write\nsteps:\n  - run: gh release create v1\n",
        )
        self.commit_all("add current candidate")

        self.write_text("private-continuity/session.md", "owner-only notes\n")
        self.write_text(".env.ignored", f"TOKEN={fake_github_token}\n")
        (self.repo / "binary.dat").write_bytes(b"\x00binary")
        outside = self.base / "outside.txt"
        outside.write_text("outside\n", encoding="utf-8")
        os.symlink(outside, self.repo / "external-link")
        os.symlink(self.base / "missing.txt", self.repo / "broken-link")
        os.symlink(self.repo / "README.md", self.repo / "absolute-internal-link")

        completed = self.run_inspector()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        findings = {
            (item["scope"], item["rule_id"], item["path"])
            for item in result["findings"]
        }

        self.assertIn(("working-tree", "raw-env-file", ".env"), findings)
        self.assertIn(("working-tree", "secret.github-token", ".env"), findings)
        self.assertIn(("index", "secret.github-token", ".env"), findings)
        self.assertIn(
            (
                "working-tree",
                "private-continuity-path",
                "private-continuity/session.md",
            ),
            findings,
        )
        self.assertIn(
            ("working-tree", "machine-local-absolute-path", "docs/local.md"),
            findings,
        )
        self.assertIn(
            (
                "working-tree",
                "publish-capable-github-workflow",
                ".github/workflows/release.yml",
            ),
            findings,
        )
        self.assertIn(
            ("working-tree", "external-symlink", "external-link"), findings
        )
        self.assertIn(("working-tree", "broken-symlink", "broken-link"), findings)
        self.assertIn(
            ("working-tree", "absolute-symlink", "absolute-internal-link"),
            findings,
        )
        self.assertNotIn(
            ("working-tree", "raw-env-file", ".env.ignored"),
            findings,
        )
        self.assertGreaterEqual(
            result["counts"]["working_tree"]["nonignored_untracked_paths"],
            4,
        )
        self.assertGreaterEqual(result["skips"]["working_tree"]["binary"], 1)
        self.assertEqual(result["scan_scope"]["candidate_mode"], "both")
        self.assertFalse(result["scan_complete"])
        self.assertIn("working-tree.binary", result["coverage_limited_by"])
        self.assertFalse(result["scan_scope"]["history"]["enabled"])
        self.assertTrue(result["manual_review_required"])
        self.assertFalse(result["readiness_certificate"])
        self.assertFalse(result["publication_readiness_claimed"])
        self.assertTrue(
            all(set(item) == {"rule_id", "path", "scope"} for item in result["findings"])
        )
        self.assertNotIn(fake_github_token, completed.stdout)

    def test_scans_missing_skip_worktree_file_from_index(self) -> None:
        fake_github_token = "ghp_" + ("S" * 32)
        hidden = self.write_text(".env", f"TOKEN={fake_github_token}\n")
        self.write_text("README.md", "# Candidate\n")
        self.commit_all("add sparse candidate")
        self.git("update-index", "--skip-worktree", ".env")
        hidden.unlink()

        completed = self.run_inspector()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        findings = {
            (item["scope"], item["rule_id"], item["path"])
            for item in result["findings"]
        }
        self.assertTrue(result["repository"]["clean"])
        self.assertIn(("working-tree", "raw-env-file", ".env"), findings)
        self.assertIn(("working-tree", "secret.github-token", ".env"), findings)
        self.assertIn(("index", "secret.github-token", ".env"), findings)
        self.assertEqual(
            result["counts"]["working_tree"]["index_fallback_files_scanned"],
            1,
        )
        self.assertNotIn(fake_github_token, completed.stdout)

    def test_optional_history_scan_finds_removed_path_and_secret(self) -> None:
        fake_github_token = "ghp_" + ("H" * 32)
        self.write_text("README.md", "# Candidate\n")
        self.commit_all("initial")
        historical = self.write_text("archive/.env", f"TOKEN={fake_github_token}\n")
        self.commit_all("add historical secret")
        historical.unlink()
        self.commit_all("remove historical secret")

        current_only = self.run_inspector()
        self.assertEqual(current_only.returncode, 0, current_only.stderr)
        self.assertNotIn("archive/.env", current_only.stdout)

        completed = self.run_inspector("--history-ref", "HEAD")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        findings = {
            (item["scope"], item["rule_id"], item["path"])
            for item in result["findings"]
        }
        self.assertIn(("history", "raw-env-file", "archive/.env"), findings)
        self.assertIn(("history", "secret.github-token", "archive/.env"), findings)
        self.assertTrue(result["scan_scope"]["history"]["enabled"])
        self.assertEqual(
            result["scan_scope"]["history"]["resolved_commit"],
            self.git("rev-parse", "HEAD").strip(),
        )
        self.assertGreater(result["counts"]["history"]["unique_blobs"], 0)
        self.assertGreater(result["counts"]["history"]["text_blobs_scanned"], 0)
        self.assertNotIn(fake_github_token, completed.stdout)

    def test_history_scan_includes_merge_only_paths(self) -> None:
        self.write_text("README.md", "# Candidate\n")
        self.commit_all("initial")
        self.git("checkout", "-q", "-b", "feature")
        self.write_text("feature.txt", "feature\n")
        self.commit_all("feature")
        self.git("checkout", "-q", "main")
        self.write_text("main.txt", "main\n")
        self.commit_all("main")
        self.git("merge", "--no-commit", "feature")
        merge_only = self.write_text("archive/.env", "MERGE_ONLY=true\n")
        self.commit_all("merge with resolution-only path")
        merge_only.unlink()
        self.commit_all("remove merge-only path")

        completed = self.run_inspector("--history-ref", "HEAD")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertIn(
            {"rule_id": "raw-env-file", "path": "archive/.env", "scope": "history"},
            result["findings"],
        )

    def test_history_applies_path_rules_to_every_path_for_a_unique_blob(self) -> None:
        workflow = "permissions:\n  contents: write\nsteps:\n  - run: gh release create v1\n"
        self.write_text("README.md", "# Candidate\n")
        self.write_text("template.txt", workflow)
        self.commit_all("add workflow template")
        published_path = self.write_text(".github/workflows/release.yml", workflow)
        self.commit_all("reuse workflow blob")
        published_path.unlink()
        self.commit_all("remove workflow path")

        completed = self.run_inspector("--history-ref", "HEAD")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertIn(
            {
                "rule_id": "publish-capable-github-workflow",
                "path": ".github/workflows/release.yml",
                "scope": "history",
            },
            result["findings"],
        )

    def test_sanitizes_remote_credentials_and_never_echoes_secret_values(self) -> None:
        remote_password = "REMOTE_PASSWORD_MUST_NOT_APPEAR"
        remote_query_secret = "REMOTE_QUERY_MUST_NOT_APPEAR"
        remote_client_secret = "REMOTE_CLIENT_SECRET_MUST_NOT_APPEAR"
        remote_oauth_token = "REMOTE_OAUTH_TOKEN_MUST_NOT_APPEAR"
        file_secret = "sk-proj-" + ("B" * 32)
        self.write_text("README.md", "# Candidate\n")
        self.write_text("config.txt", f"api_key={file_secret}\n")
        self.commit_all("add candidate")
        self.git(
            "remote",
            "add",
            "origin",
            (
                f"https://robot:{remote_password}@github.com/example/candidate.git"
                f"?token={remote_query_secret}&client_secret={remote_client_secret}"
                f"&oauth_token={remote_oauth_token}"
            ),
        )

        nested = self.repo / "nested"
        nested.mkdir()
        completed = self.run_inspector(repo=nested)
        combined = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn(remote_password, combined)
        self.assertNotIn(remote_query_secret, combined)
        self.assertNotIn(remote_client_secret, combined)
        self.assertNotIn(remote_oauth_token, combined)
        self.assertNotIn(file_secret, combined)

        result = json.loads(completed.stdout)
        self.assertEqual(result["repository"]["root"], "<redacted>")
        self.assertEqual(result["repository"]["branch"], "main")
        self.assertEqual(result["repository"]["head"], self.git("rev-parse", "HEAD").strip())
        remote = result["repository"]["remotes"][0]
        self.assertEqual(remote["name"], "origin")
        self.assertEqual(
            remote["fetch_urls"],
            ["<redacted>"],
        )
        self.assertEqual(remote["push_urls"], remote["fetch_urls"])
        self.assertIn(
            {
                "rule_id": "secret.openai-key",
                "path": "config.txt",
                "scope": "working-tree",
            },
            result["findings"],
        )

    def test_scans_staged_index_independently_from_cleaned_working_tree(self) -> None:
        fake_github_token = "ghp_" + ("I" * 32)
        self.write_text("config.txt", "mode=clean\n")
        self.commit_all("add clean config")

        self.write_text("config.txt", f"token={fake_github_token}\n")
        self.git("add", "config.txt")
        self.write_text("config.txt", "mode=clean\n")

        completed = self.run_inspector()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        findings = {
            (item["scope"], item["rule_id"], item["path"])
            for item in result["findings"]
        }
        self.assertIn(("index", "secret.github-token", "config.txt"), findings)
        self.assertNotIn(
            ("working-tree", "secret.github-token", "config.txt"), findings
        )
        self.assertFalse(result["repository"]["clean"])
        self.assertNotIn(fake_github_token, completed.stdout + completed.stderr)

    def test_scans_exact_candidate_ref_separately_from_worktree_and_index(self) -> None:
        fake_github_token = "ghp_" + ("R" * 32)
        self.write_text("config.txt", f"token={fake_github_token}\n")
        self.commit_all("add unsafe candidate")
        unsafe_commit = self.git("rev-parse", "HEAD").strip()
        self.write_text("config.txt", "mode=clean\n")
        self.commit_all("clean candidate")

        completed = self.run_inspector(
            "--candidate",
            "none",
            "--candidate-ref",
            unsafe_commit,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertFalse(result["scan_scope"]["working_tree"]["enabled"])
        self.assertFalse(result["scan_scope"]["index"]["enabled"])
        self.assertTrue(result["scan_scope"]["ref"]["enabled"])
        self.assertEqual(
            result["scan_scope"]["ref"]["resolved_commit"], unsafe_commit
        )
        self.assertTrue(result["scan_complete"])
        self.assertIn(
            {"rule_id": "secret.github-token", "path": "config.txt", "scope": "ref"},
            result["findings"],
        )
        self.assertNotIn(fake_github_token, completed.stdout + completed.stderr)

    def test_fail_on_findings_returns_review_failure_status(self) -> None:
        self.write_text(".env", "MODE=test\n")
        self.commit_all("add review finding")
        completed = self.run_inspector("--fail-on-findings")
        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertIn("raw-env-file", completed.stdout)

    def test_history_skip_counts_cover_binary_and_large_unique_blobs(self) -> None:
        self.write_text("README.md", "ok\n")
        (self.repo / "binary.dat").write_bytes(b"\x00tiny")
        (self.repo / "large.txt").write_text("L" * 128, encoding="utf-8")
        self.commit_all("add skipped history blobs")

        completed = self.run_inspector("--history-ref", "HEAD", "--max-bytes", "64")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertGreaterEqual(result["skips"]["history"]["binary"], 1)
        self.assertGreaterEqual(result["skips"]["history"]["large"], 1)

    def test_invalid_history_ref_is_a_tool_error(self) -> None:
        self.write_text("README.md", "# Candidate\n")
        self.commit_all("initial")
        completed = self.run_inspector("--history-ref", "does-not-exist")
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")
        self.assertIn("history ref does not resolve", completed.stderr)


if __name__ == "__main__":
    unittest.main()
