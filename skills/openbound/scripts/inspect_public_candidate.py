#!/usr/bin/env python3
"""Read-only signal scan for a proposed public Git repository.

The inspector intentionally emits only rule identifiers, paths, and scopes for
findings. It never emits a matched value or matching line, and its output is not
a publication-readiness certificate.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Iterator, Sequence


DEFAULT_MAX_BYTES = 2_000_000
REPORT_FORMAT = "openbound-inspection/2"
RULE_VERSION = "openbound-patterns-2026-11-01.1"

# A pointer describes a separate object. Reading this text does not read that
# object, even if git-lfs happens to be installed or the payload is cached.
LFS_HEADER = b"version https://git-lfs.github.com/spec/v1"
LFS_OID = re.compile(rb"(?m)^oid sha256:([0-9a-f]{64})\r?$")
LFS_SIZE = re.compile(rb"(?m)^size ([0-9]+)\r?$")


class InspectionError(RuntimeError):
    """Raised when the requested scan cannot be completed reliably."""


class PrivateArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse's default message includes the rejected user-supplied value.
        raise InspectionError("invalid command-line arguments; use --help")


SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "secret.private-key-block",
        re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA |PGP )?PRIVATE KEY-----"),
    ),
    (
        "secret.github-token",
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    ),
    (
        "secret.openai-key",
        re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    ),
    (
        "secret.slack-token",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    ),
    (
        "secret.aws-access-key",
        re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    ),
    (
        "secret.google-api-key",
        re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    ),
    (
        "secret.stripe-live-key",
        re.compile(r"\b(?:sk|rk)_live_[0-9A-Za-z]{16,}\b"),
    ),
    (
        "secret.gitlab-token",
        re.compile(r"\bglpat-[0-9A-Za-z_-]{20,}\b"),
    ),
    (
        "secret.huggingface-token",
        re.compile(r"\bhf_[0-9A-Za-z]{24,}\b"),
    ),
    (
        "secret.bearer-token",
        re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    ),
    (
        "secret.credential-assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|"
            r"password|passwd|secret|token)\b\s*[:=]\s*[\"']?[A-Za-z0-9_./+=-]{12,}"
        ),
    ),
)

MACHINE_LOCAL_PATH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:file://)?/Users/[^/\s]+/"),
    re.compile(r"(?:file://)?/home/[^/\s]+/"),
    re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+\\"),
    re.compile(r"(?:file://)?/Volumes/[^/\r\n]+/"),
    re.compile(r"(?:file://)?/(?:private/)?var/folders/[A-Za-z0-9_/.-]+"),
)

PUBLISH_WORKFLOW_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bpermissions:\s*write-all\b", re.I),
    re.compile(r"\b(?:contents|packages|pages|deployments|id-token):\s*write\b", re.I),
    re.compile(r"\b(?:npm|pnpm|yarn|cargo)\s+publish\b", re.I),
    re.compile(r"\b(?:twine\s+upload|gem\s+push|docker\s+push|gh\s+release\s+create)\b", re.I),
    re.compile(
        r"(?:actions/deploy-pages|peaceiris/actions-gh-pages|softprops/action-gh-release|"
        r"pypa/gh-action-pypi-publish|docker/build-push-action)",
        re.I,
    ),
    re.compile(r"\bpush:\s*true\b", re.I),
)

SENSITIVE_BASENAMES = {
    ".netrc",
    ".npmrc",
    ".pypirc",
    "cookies.json",
    "cookies.txt",
    "credentials.json",
    "credentials.yaml",
    "credentials.yml",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
    "secrets.json",
    "secrets.yaml",
    "secrets.yml",
}

KEY_MATERIAL_SUFFIXES = {
    ".der",
    ".jks",
    ".key",
    ".keystore",
    ".p12",
    ".pem",
    ".pfx",
    ".pkcs12",
}

SAFE_ENV_SUFFIXES = {".example", ".sample", ".template"}


def _decode_path(value: bytes) -> str:
    return value.decode("utf-8", errors="surrogateescape")


def _digest(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(data.encode("ascii")).hexdigest()


def _safe_label(value: str) -> str:
    """Keep ordinary relative paths useful; suppress obvious value-bearing names.

    This is output hygiene, not a guarantee that relative names are public.
    Inspection reports remain private working material until explicitly reviewed.
    """
    if (any(pattern.search(value) for _, pattern in SECRET_PATTERNS)
            or any(pattern.search(value) for pattern in MACHINE_LOCAL_PATH_PATTERNS)
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        return "redacted:" + _digest(value)
    return value


def _git_environment() -> dict[str, str]:
    # Ambient GIT_DIR/GIT_INDEX_FILE/config injection must not redirect a scan.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update({
        "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_LAZY_FETCH": "1",
        "GIT_NO_REPLACE_OBJECTS": "1", "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        # Also blocks transport on Git versions which ignore NO_LAZY_FETCH.
        "GIT_ALLOW_PROTOCOL": "", "GIT_ATTR_NOSYSTEM": "1",
    })
    return env


def _git_command(root: Path, *args: str) -> list[str]:
    return [
        "git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.devnull,
        "-c", "submodule.recurse=false", "-c", "credential.helper=",
        "-c", "core.askPass=", "-c", "diff.external=", "-c", "log.showSignature=false",
        "-c", "status.submoduleSummary=false", "-C", str(root), *args,
    ]


def _filter_overrides(root: Path) -> list[str]:
    # Even `git status` may invoke a clean/process filter. Disable every local
    # filter before status; neither source programs nor hooks may run in a scan.
    result = _run_git_bytes(
        root, "config", "--null", "--name-only", "--get-regexp",
        r"^filter\..*\.(clean|smudge|process|required)$", allow_failure=True,
    )
    overrides: list[str] = []
    for raw in result.stdout.decode("utf-8", errors="surrogateescape").split("\0"):
        if not raw:
            continue
        if re.fullmatch(r"filter\.[^\r\n=]+\.(?:clean|smudge|process|required)", raw):
            overrides.extend(["-c", raw + ("=false" if raw.endswith(".required") else "=")])
        else:
            raise InspectionError("unsupported repository filter configuration")
    return overrides


def _run_git_bytes(
    root: Path,
    *args: str,
    stdin: bytes | None = None,
    allow_failure: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    try:
        completed = subprocess.run(
            _git_command(root, *(_filter_overrides(root) if args and args[0] == "status" else []), *args),
            input=stdin,
            capture_output=True,
            check=False,
            env=_git_environment(),
        )
    except OSError as error:
        raise InspectionError("unable to execute git") from None
    if completed.returncode != 0 and not allow_failure:
        # Git stderr can contain credentials, raw refs, absolute paths, or
        # repository-controlled diagnostics. Never copy it into a report/log.
        raise InspectionError("git read operation failed")
    return completed


def _git_text(root: Path, *args: str) -> str:
    return _run_git_bytes(root, *args).stdout.decode("utf-8", errors="surrogateescape")


def _git_zpaths(root: Path, *args: str) -> list[str]:
    output = _run_git_bytes(root, *args).stdout
    return [_decode_path(item) for item in output.split(b"\0") if item]


def _sanitize_remote_url(url: str) -> str:
    """Remove embedded userinfo and credential-like query values."""

    value = url.strip()
    value = re.sub(
        r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)[^/@\s]+@",
        r"\g<scheme><redacted>@",
        value,
    )
    # Keep ordinary ``git@host:path`` legible. Redact scp-style userinfo only
    # when it has the credential-bearing ``user:password`` form.
    value = re.sub(
        r"^(?:[^/@:\s]+):(?:[^@\s]+)@(?P<host>[^:\s]+):",
        r"<redacted>@\g<host>:",
        value,
    )
    value = re.sub(
        r"^(?!git@)(?:[^/@\s]+)@(?P<host>[^:\s]+):",
        r"<redacted>@\g<host>:",
        value,
    )
    value = re.sub(
        r"([?#&](?:access[_-]?token|auth(?:[_-]?token)?|oauth[_-]?token|"
        r"private[_-]?token|refresh[_-]?token|id[_-]?token|api[_-]?key|"
        r"client[_-]?secret|credential|key|passwd|password|secret|sig|"
        r"signature|token)=)[^&#\s]+",
        r"\1<redacted>",
        value,
        flags=re.I,
    )
    return value


def _remote_inventory(root: Path) -> list[dict[str, Any]]:
    names = [name for name in _git_text(root, "remote").splitlines() if name]
    result: list[dict[str, Any]] = []
    for name in sorted(names):
        fetch = [
            _sanitize_remote_url(url)
            for url in _git_text(root, "remote", "get-url", "--all", name).splitlines()
            if url
        ]
        push = [
            _sanitize_remote_url(url)
            for url in _git_text(root, "remote", "get-url", "--push", "--all", name).splitlines()
            if url
        ]
        result.append({
            "name": _safe_label(name),
            "fetch_urls": ["<redacted>" for _ in fetch],
            "push_urls": ["<redacted>" for _ in push],
            "fetch_url_ids": [_digest(url) for url in fetch],
            "push_url_ids": [_digest(url) for url in push],
        })
    return result


def _head_and_branch(root: Path) -> tuple[str | None, str | None]:
    head_result = _run_git_bytes(root, "rev-parse", "--verify", "HEAD", allow_failure=True)
    head = (
        head_result.stdout.decode("ascii", errors="replace").strip()
        if head_result.returncode == 0
        else None
    )
    branch_result = _run_git_bytes(
        root,
        "symbolic-ref",
        "--quiet",
        "--short",
        "HEAD",
        allow_failure=True,
    )
    branch = (
        branch_result.stdout.decode("utf-8", errors="surrogateescape").strip()
        if branch_result.returncode == 0
        else None
    )
    return head, branch


def _parse_status(root: Path) -> list[dict[str, str]]:
    raw = _run_git_bytes(
        root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--ignore-submodules=all",
    ).stdout
    records = raw.split(b"\0")
    result: list[dict[str, str]] = []
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if len(record) < 3:
            raise InspectionError("git returned an unparseable status record")
        code = record[:2].decode("ascii", errors="replace")
        entry: dict[str, str] = {"code": code, "path": _decode_path(record[3:])}
        if "R" in code or "C" in code:
            if index >= len(records) or not records[index]:
                raise InspectionError("git returned an incomplete rename status record")
            entry["original_path"] = _decode_path(records[index])
            index += 1
        result.append(entry)
    return result


def _path_rules(path: str) -> set[str]:
    pure = PurePosixPath(path)
    basename = pure.name.lower()
    components = {part.lower() for part in pure.parts}
    rules: set[str] = set()

    if (
        components.intersection(
            {".private-continuity", "private-continuity", "private_continuity"}
        )
        or basename.startswith(("private-continuity.", "private_continuity."))
    ):
        rules.add("private-continuity-path")

    if basename == ".env" or (
        basename.startswith(".env.")
        and not any(basename.endswith(suffix) for suffix in SAFE_ENV_SUFFIXES)
    ):
        rules.add("raw-env-file")

    if (
        basename in SENSITIVE_BASENAMES
        or basename.startswith(("cookies.", "credentials.", "secrets."))
    ):
        rules.add("sensitive-filename")

    if basename.startswith(("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519")):
        rules.add("key-material-file")
    if pure.suffix.lower() in KEY_MATERIAL_SUFFIXES:
        rules.add("key-material-file")

    return rules


def _content_rules(text: str, path: str) -> set[str]:
    rules: set[str] = set()
    for rule_id, pattern in SECRET_PATTERNS:
        matches = list(pattern.finditer(text))
        if rule_id == "secret.credential-assignment":
            # Explicit symbolic documentation placeholders are not credentials.
            # This exception never suppresses a provider-shaped key rule.
            matches = [match for match in matches if not re.fullmatch(
                r"(?:YOUR_[A-Z_]+|EXAMPLE_[A-Z_]+|REPLACE_ME|CHANGE_ME)",
                re.split(r"\s*[:=]\s*[\"']?", match.group(), maxsplit=1)[-1],
            )]
        if matches:
            rules.add(rule_id)
    if any(pattern.search(text) for pattern in MACHINE_LOCAL_PATH_PATTERNS):
        rules.add("machine-local-absolute-path")
    if path.startswith(".github/workflows/") and any(
        pattern.search(text) for pattern in PUBLISH_WORKFLOW_PATTERNS
    ):
        rules.add("publish-capable-github-workflow")
    return rules


def _add_findings(
    findings: set[tuple[str, str, str]],
    rules: Iterable[str],
    path: str,
    scope: str,
) -> None:
    for rule_id in rules:
        findings.add((scope, rule_id, path))


def _inside_root(root: Path, target: Path) -> bool:
    try:
        return os.path.commonpath((str(root), str(target))) == str(root)
    except ValueError:
        return False


@contextmanager
def _candidate_parent(root: Path, relative: str) -> Iterator[tuple[int, str]]:
    """Open each ancestor without following symlinks (POSIX dir-fd semantics)."""
    parts = PurePosixPath(relative).parts
    if not root.is_absolute() or '..' in root.parts:
        raise InspectionError("unsafe repository path")
    if not parts or any(part in {"", ".", ".."} for part in parts) or PurePosixPath(relative).is_absolute():
        raise InspectionError("unsafe candidate path")
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise InspectionError("safe filesystem traversal is unavailable on this platform")
    descriptors: list[int] = []
    try:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        descriptor = os.open("/", flags)
        descriptors.append(descriptor)
        for part in (*root.parts[1:], *parts[:-1]):
            descriptor = os.open(part, flags, dir_fd=descriptor)
            descriptors.append(descriptor)
        yield descriptor, parts[-1]
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _candidate_lstat(root: Path, relative: str) -> os.stat_result:
    with _candidate_parent(root, relative) as (descriptor, basename):
        return os.stat(basename, dir_fd=descriptor, follow_symlinks=False)


def _candidate_readlink(root: Path, relative: str) -> str:
    with _candidate_parent(root, relative) as (descriptor, basename):
        return os.readlink(basename, dir_fd=descriptor)


def _candidate_bytes(root: Path, relative: str, max_bytes: int) -> tuple[bytes, str, int, int]:
    """Read once: bounded text sample plus a full streaming content identity."""
    with _candidate_parent(root, relative) as (descriptor, basename):
        fd = os.open(basename, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=descriptor)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise InspectionError("candidate changed type during inspection")
        digest = hashlib.sha256()
        sample = bytearray()
        size = 0
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
            if len(sample) <= max_bytes:
                sample.extend(chunk[:max_bytes + 1 - len(sample)])
        after = os.fstat(stream.fileno())
        if ((before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
            raise InspectionError("candidate changed while being read")
        return bytes(sample), digest.hexdigest(), size, stat.S_IMODE(before.st_mode)


def _index_entries(root: Path) -> dict[str, tuple[str, str]]:
    output = _run_git_bytes(root, "ls-files", "--stage", "-z").stdout
    result: dict[str, tuple[str, str]] = {}
    for record in output.split(b"\0"):
        if not record:
            continue
        raw_metadata, separator, raw_path = record.partition(b"\t")
        fields = raw_metadata.split()
        if not separator or len(fields) != 3:
            raise InspectionError("git returned an unparseable index record")
        raw_mode, raw_oid, raw_stage = fields
        if raw_stage != b"0":
            continue
        result[_decode_path(raw_path)] = (
            raw_mode.decode("ascii", errors="strict"),
            raw_oid.decode("ascii", errors="strict"),
        )
    return result


def _resolve_commit(root: Path, requested_ref: str, label: str) -> str:
    _validate_ref(requested_ref, label)
    result = _run_git_bytes(
        root,
        "rev-parse",
        "--verify",
        "--end-of-options",
        f"{requested_ref}^{{commit}}",
        allow_failure=True,
    )
    if result.returncode != 0:
        raise InspectionError(f"{label} does not resolve to a commit")
    oid = result.stdout.decode("ascii", errors="replace").strip()
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", oid):
        raise InspectionError("git returned an invalid object identity")
    return oid


def _validate_ref(requested_ref: str, label: str) -> None:
    if (not requested_ref or requested_ref.startswith("-") or ".." in requested_ref
            or ":" in requested_ref or any(char.isspace() or ord(char) < 32 or ord(char) == 127
                                          for char in requested_ref)):
        raise InspectionError(f"{label} is not a single commit-ish")


def _lfs_pointer(data: bytes) -> dict[str, Any] | None:
    if not data.startswith(LFS_HEADER):
        return None
    oid, size = LFS_OID.search(data), LFS_SIZE.search(data)
    # A malformed pointer-like file is also not evidence of a payload scan.
    valid_size = bool(size and len(size.group(1)) <= 20)
    return {
        "valid_pointer": bool(oid and valid_size),
        "oid": "sha256:" + oid.group(1).decode("ascii") if oid else None,
        "size": int(size.group(1)) if valid_size and size else None,
        "payload_observed": False,
    }


def _record_lfs(data: bytes, relative: str, scope: str,
                findings: set[tuple[str, str, str]], skipped: dict[str, int]) -> None:
    pointer = _lfs_pointer(data)
    if pointer is not None:
        skipped["lfs_payload"] = skipped.get("lfs_payload", 0) + 1
        _add_findings(findings, {"lfs-payload-unobserved"}, relative, scope)
        if not pointer["valid_pointer"]:
            _add_findings(findings, {"malformed-lfs-pointer"}, relative, scope)


def _tree_entries(root: Path, commit: str) -> dict[str, tuple[str, str]]:
    output = _run_git_bytes(
        root, "ls-tree", "-r", "-z", "--full-tree", commit
    ).stdout
    entries: dict[str, tuple[str, str]] = {}
    for record in output.split(b"\0"):
        if not record:
            continue
        raw_metadata, separator, raw_path = record.partition(b"\t")
        fields = raw_metadata.split()
        if not separator or len(fields) != 3:
            raise InspectionError("git returned an unparseable tree record")
        raw_mode, _raw_type, raw_oid = fields
        entries[_decode_path(raw_path)] = (
            raw_mode.decode("ascii", errors="strict"),
            raw_oid.decode("ascii", errors="strict"),
        )
    return entries


def _scan_blob_candidate(
    root: Path,
    entries: dict[str, tuple[str, str]],
    scope: str,
    max_bytes: int,
    findings: set[tuple[str, str, str]],
) -> dict[str, Any]:
    """Scan an index or exact tree without consulting working-tree bytes."""

    counts = {
        "listed_paths": len(entries),
        "regular_files_scanned": 0,
        "symlinks_checked": 0,
        "unique_blobs_read": 0,
    }
    skipped = {"binary": 0, "large": 0, "nonregular": 0}
    metadata = _object_metadata(root, sorted({oid for _mode, oid in entries.values()}))
    bindings: dict[str, list[tuple[str, str]]] = {}

    for relative, (mode, oid) in sorted(entries.items()):
        _add_findings(findings, _path_rules(relative), relative, scope)
        object_type, object_size = metadata.get(oid, ("missing", 0))
        if object_type != "blob" or not (mode == "120000" or mode.startswith("100")):
            skipped["nonregular"] += 1
            continue
        if object_size > max_bytes:
            skipped["large"] += 1
            continue
        bindings.setdefault(oid, []).append((relative, mode))

    for oid, data in _read_blobs(root, sorted(bindings)):
        counts["unique_blobs_read"] += 1
        for relative, mode in bindings[oid]:
            if mode == "120000":
                counts["symlinks_checked"] += 1
                link_target = data.decode("utf-8", errors="surrogateescape")
                if os.path.isabs(link_target):
                    _add_findings(findings, {"absolute-symlink"}, relative, scope)
                _add_findings(
                    findings,
                    _content_rules(link_target, relative),
                    relative,
                    scope,
                )
                continue
            _record_candidate_bytes(
                data,
                relative,
                scope,
                max_bytes,
                findings,
                counts,
                skipped,
            )

    return {
        "enabled": True, "counts": counts, "skipped": skipped,
        "identity": {"kind": "git-path-mode-oid/1", "sha256": _digest(sorted(entries.items()))},
    }


def _record_candidate_bytes(
    data: bytes,
    relative: str,
    scope: str,
    max_bytes: int,
    findings: set[tuple[str, str, str]],
    counts: dict[str, int],
    skipped: dict[str, int],
) -> None:
    _record_lfs(data, relative, scope, findings, skipped)
    if len(data) > max_bytes:
        skipped["large"] += 1
        return
    if b"\0" in data:
        skipped["binary"] += 1
        return
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        skipped["binary"] += 1
        return
    counts["regular_files_scanned"] += 1
    _add_findings(findings, _content_rules(text, relative), relative, scope)


def _scan_working_tree_candidate(
    root: Path,
    max_bytes: int,
    findings: set[tuple[str, str, str]],
    deleted_paths: set[str],
) -> dict[str, Any]:
    tracked = set(_git_zpaths(root, "ls-files", "--cached", "-z"))
    untracked = set(
        _git_zpaths(root, "ls-files", "--others", "--exclude-standard", "-z")
    )
    inventory = sorted(tracked | untracked)
    index_entries = _index_entries(root)

    counts = {
        "tracked_index_paths": len(tracked),
        "nonignored_untracked_paths": len(untracked),
        "listed_paths": len(inventory),
        "regular_files_scanned": 0,
        "index_fallback_files_scanned": 0,
        "symlinks_checked": 0,
    }
    skipped = {"binary": 0, "large": 0, "missing": 0, "nonregular": 0}
    bindings: list[Any] = []

    for relative in inventory:
        path = root / relative
        try:
            metadata = _candidate_lstat(root, relative)
        except FileNotFoundError:
            if relative in deleted_paths:
                # An actual working-tree deletion is not in the proposed
                # current tree. Sparse/skip-worktree absence has no deletion
                # status and must be scanned from the index instead.
                skipped["missing"] += 1
                bindings.append([relative, "deleted"])
                continue
            entry = index_entries.get(relative) if relative in tracked else None
            if entry is None:
                raise InspectionError(
                    "listed candidate path is unavailable for inspection"
                )
            mode, oid = entry
            bindings.append([relative, "index-fallback", mode, oid])
            _add_findings(findings, _path_rules(relative), relative, "working-tree")
            object_type, object_size = _object_metadata(root, [oid]).get(
                oid, ("missing", 0)
            )
            if object_type != "blob":
                skipped["nonregular"] += 1
                continue
            if object_size > max_bytes:
                skipped["large"] += 1
                continue
            data = _run_git_bytes(root, "cat-file", "blob", oid).stdout
            if mode == "120000":
                counts["symlinks_checked"] += 1
                link_target = data.decode("utf-8", errors="surrogateescape")
                if os.path.isabs(link_target):
                    _add_findings(
                        findings, {"absolute-symlink"}, relative, "working-tree"
                    )
                _add_findings(
                    findings,
                    _content_rules(link_target, relative),
                    relative,
                    "working-tree",
                )
                continue
            if not mode.startswith("100"):
                skipped["nonregular"] += 1
                continue
            counts["index_fallback_files_scanned"] += 1
            _record_candidate_bytes(
                data,
                relative,
                "working-tree",
                max_bytes,
                findings,
                counts,
                skipped,
            )
            continue
        except OSError as error:
            raise InspectionError("unable to inspect candidate path without following ancestors") from None

        _add_findings(findings, _path_rules(relative), relative, "working-tree")

        if stat.S_ISLNK(metadata.st_mode):
            counts["symlinks_checked"] += 1
            try:
                link_target = _candidate_readlink(root, relative)
                bindings.append([relative, "symlink", hashlib.sha256(os.fsencode(link_target)).hexdigest()])
            except OSError as error:
                raise InspectionError(
                    "unable to read symlink target"
                ) from None
            if os.path.isabs(link_target):
                _add_findings(
                    findings, {"absolute-symlink"}, relative, "working-tree"
                )
            _add_findings(
                findings,
                _content_rules(link_target, relative),
                relative,
                "working-tree",
            )
            try:
                resolved = path.resolve(strict=True)
            except (FileNotFoundError, RuntimeError, OSError):
                _add_findings(
                    findings, {"broken-symlink"}, relative, "working-tree"
                )
                continue
            if not _inside_root(root, resolved):
                _add_findings(
                    findings, {"external-symlink"}, relative, "working-tree"
                )
            continue

        if not stat.S_ISREG(metadata.st_mode):
            skipped["nonregular"] += 1
            bindings.append([relative, "unobserved-nonregular", metadata.st_mode])
            continue
        try:
            data, content_digest, size, mode = _candidate_bytes(root, relative, max_bytes)
            bindings.append([relative, "file", mode, size, content_digest])
        except OSError as error:
            raise InspectionError("unable to read candidate path") from None
        _record_candidate_bytes(
            data,
            relative,
            "working-tree",
            max_bytes,
            findings,
            counts,
            skipped,
        )

    return {
        "enabled": True, "counts": counts, "skipped": skipped,
        "identity": {"kind": "observed-path-mode-content-sha256/1", "sha256": _digest(bindings)},
    }


def _historical_blob_paths(
    root: Path,
    commit: str,
) -> tuple[set[str], dict[str, set[str]]]:
    """Return all changed tree paths and every observed object-to-path binding.

    ``-m`` expands merge commits against each parent, while ``--root`` exposes
    the initial trees. This keeps blob reads unique without collapsing a blob
    that appeared under multiple path-sensitive names.
    """

    output = _run_git_bytes(
        root,
        "log",
        "--format=",
        "--raw",
        "--no-renames",
        "--no-abbrev",
        "--no-ext-diff",
        "--no-textconv",
        "--root",
        "-m",
        "-z",
        commit,
    ).stdout
    records = output.split(b"\0")
    paths: set[str] = set()
    object_paths: dict[str, set[str]] = {}
    index = 0
    while index < len(records):
        header = records[index]
        index += 1
        if not header:
            continue
        if not header.startswith(b":") or index >= len(records):
            raise InspectionError("git returned unparseable historical path data")
        fields = header[1:].split()
        if len(fields) != 5:
            raise InspectionError("git returned unparseable historical diff metadata")
        old_mode, new_mode, old_oid, new_oid, _status = fields
        raw_path = records[index]
        index += 1
        if not raw_path:
            raise InspectionError("git returned an empty historical path")
        path = _decode_path(raw_path)
        paths.add(path)
        for mode, raw_oid in ((old_mode, old_oid), (new_mode, new_oid)):
            if mode == b"000000" or not raw_oid.strip(b"0"):
                continue
            oid = raw_oid.decode("ascii", errors="strict")
            object_paths.setdefault(oid, set()).add(path)
    return paths, object_paths


def _reachable_objects(root: Path, commit: str) -> list[str]:
    output = _run_git_bytes(
        root, "rev-list", "--objects", "--no-object-names", commit
    ).stdout
    object_ids: list[str] = []
    seen: set[str] = set()
    for raw_line in output.splitlines():
        if not raw_line:
            continue
        oid = raw_line.decode("ascii", errors="strict")
        if oid not in seen:
            object_ids.append(oid)
            seen.add(oid)
    return object_ids


def _object_metadata(root: Path, object_ids: Sequence[str]) -> dict[str, tuple[str, int]]:
    if not object_ids:
        return {}
    payload = ("\n".join(object_ids) + "\n").encode("ascii")
    output = _run_git_bytes(
        root,
        "cat-file",
        "--batch-check=%(objectname) %(objecttype) %(objectsize)",
        stdin=payload,
    ).stdout
    result: dict[str, tuple[str, int]] = {}
    for line in output.splitlines():
        parts = line.decode("ascii", errors="strict").split()
        if len(parts) == 2 and parts[1] == "missing":
            result[parts[0]] = ("missing", 0)
            continue
        if len(parts) != 3:
            raise InspectionError("git returned unparseable object metadata")
        oid, object_type, raw_size = parts
        try:
            result[oid] = (object_type, int(raw_size))
        except ValueError as error:
            raise InspectionError("git returned invalid object size metadata") from error
    return result


def _read_exact(stream: Any, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise InspectionError("git ended blob output unexpectedly")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _read_blobs(
    root: Path,
    object_ids: Sequence[str],
    object_types: tuple[str, ...] = ("blob",),
) -> Iterator[tuple[str, bytes]]:
    """Reuse one read-only cat-file transport for blobs or raw metadata."""
    if not object_ids:
        return
    try:
        process = subprocess.Popen(
            _git_command(root, "cat-file", "--batch"),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_git_environment(),
        )
    except OSError as error:
        raise InspectionError("unable to execute git cat-file") from None
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    try:
        for requested_oid in object_ids:
            process.stdin.write(requested_oid.encode("ascii") + b"\n")
            process.stdin.flush()
            header = process.stdout.readline()
            parts = header.decode("ascii", errors="replace").strip().split()
            if len(parts) != 3 or parts[1] not in object_types:
                raise InspectionError("git returned invalid object data")
            returned_oid, _, raw_size = parts
            if returned_oid != requested_oid:
                raise InspectionError("git returned an unexpected blob identity")
            try:
                size = int(raw_size)
            except ValueError as error:
                raise InspectionError("git returned invalid blob size") from error
            data = _read_exact(process.stdout, size)
            if process.stdout.read(1) != b"\n":
                raise InspectionError("git returned malformed blob framing")
            yield returned_oid, data
    finally:
        try:
            process.stdin.close()
        except OSError:
            pass
        stderr = process.stderr.read()
        returncode = process.wait()
        process.stdout.close()
        process.stderr.close()
        if returncode != 0 and sys.exc_info()[0] is None:
            raise InspectionError("git cat-file failed")


def _scan_metadata(
    root: Path,
    requested_ref: str,
    commits: Sequence[str],
    max_bytes: int,
    findings: set[tuple[str, str, str]],
    scope: str,
) -> dict[str, Any]:
    """Scan raw commit headers/messages and the explicitly selected tag chain.

    Raw objects retain messages, names and encoding declarations exactly; Git
    pretty formats could silently replace bytes or omit metadata. Other tags
    and refs are not implicitly selected merely because they target a commit.
    """
    raw = _run_git_bytes(root, "rev-parse", "--verify", "--end-of-options", requested_ref).stdout
    selected = raw.decode("ascii", errors="replace").strip()
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", selected):
        raise InspectionError("git returned an invalid selected object identity")
    if commits and _resolve_commit(root, selected, "selected object") != commits[0]:
        raise InspectionError("selected ref changed during inspection")
    pending = list(dict.fromkeys([selected, *commits]))
    seen: set[str] = set()
    counts = {"commit_objects_scanned": 0, "tag_objects_scanned": 0}
    skipped = {"metadata_large": 0, "metadata_non_utf8": 0, "metadata_missing": 0}
    bindings: list[list[Any]] = []
    while pending:
        batch = sorted(set(pending) - seen)
        pending = []
        seen.update(batch)
        metadata = _object_metadata(root, batch)
        readable: list[str] = []
        for oid in batch:
            kind, size = metadata.get(oid, ("missing", 0))
            if kind not in {"commit", "tag"}:
                if kind == "missing":
                    skipped["metadata_missing"] += 1
                continue
            bindings.append([oid, kind, size])
            if size > max_bytes:
                skipped["metadata_large"] += 1
                continue
            readable.append(oid)
        for oid, data in _read_blobs(root, readable, object_types=("commit", "tag")):
            kind, size = metadata[oid]
            if len(data) != size:
                raise InspectionError("git returned inconsistent metadata size")
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                # Preserve ASCII-rule detection, but never claim full decoded text.
                text = data.decode("utf-8", errors="replace")
                skipped["metadata_non_utf8"] += 1
            counts[kind + "_objects_scanned"] += 1
            _add_findings(findings, _content_rules(text, ""), kind + ":" + oid, scope)
            if kind == "tag":
                target = re.match(rb"object ([0-9a-f]{40}|[0-9a-f]{64})\n", data)
                if target is None:
                    raise InspectionError("invalid tag metadata")
                pending.append(target.group(1).decode("ascii"))
    return {
        "enabled": True, "counts": counts, "skipped": skipped,
        "identity": {"kind": "git-metadata-objects/1", "sha256": _digest(sorted(bindings))},
        "selected_object": selected,
        "selection": "selected commit objects and explicitly selected annotated tag chain",
    }


def _scan_history(
    root: Path,
    requested_ref: str,
    max_bytes: int,
    findings: set[tuple[str, str, str]],
) -> dict[str, Any]:
    commit = _resolve_commit(root, requested_ref, "history ref")

    historical_paths, blob_paths = _historical_blob_paths(root, commit)
    for path in historical_paths:
        _add_findings(findings, _path_rules(path), path, "history")

    object_ids = _reachable_objects(root, commit)
    metadata = _object_metadata(root, object_ids)
    blobs = [oid for oid in object_ids if metadata.get(oid, (None, 0))[0] == "blob"]
    small_blobs = [oid for oid in blobs if metadata[oid][1] <= max_bytes]

    counts = {
        "historical_paths_observed": len(historical_paths),
        "reachable_objects": len(object_ids),
        "unique_blobs": len(blobs),
        "text_blobs_scanned": 0,
    }
    skipped = {
        "binary": 0,
        "large": len(blobs) - len(small_blobs),
        "without_path": 0,
        "missing_object": sum(1 for oid in object_ids if metadata.get(oid, ("missing", 0))[0] == "missing"),
    }

    shallow = _git_text(root, "rev-parse", "--is-shallow-repository").strip() == "true"
    if shallow:
        # This is a coverage boundary, regardless of whether a visible commit
        # happens to contain a match. Never fetch to repair it during inspection.
        skipped["shallow_boundary"] = 1
    graft_path = Path(_git_text(root, "rev-parse", "--git-path", "info/grafts").strip())
    if not graft_path.is_absolute():
        graft_path = root / graft_path
    grafted = graft_path.is_file() and graft_path.stat().st_size > 0
    if grafted:
        skipped["grafted_ancestry"] = 1

    for oid, data in _read_blobs(root, small_blobs):
        paths = blob_paths.get(oid)
        if not paths:
            skipped["without_path"] += 1
            continue
        for path in paths:
            _record_lfs(data, path, "history", findings, skipped)
        if b"\0" in data:
            skipped["binary"] += 1
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            skipped["binary"] += 1
            continue
        counts["text_blobs_scanned"] += 1
        for path in paths:
            _add_findings(findings, _content_rules(text, path), path, "history")

    metadata_scan = _scan_metadata(
        root, requested_ref,
        [commit, *[oid for oid in object_ids if metadata.get(oid, (None, 0))[0] == "commit" and oid != commit]],
        max_bytes, findings, "history-metadata",
    )
    skipped.update(metadata_scan["skipped"])

    return {
        "enabled": True,
        "requested_ref": _safe_label(requested_ref),
        "resolved_commit": commit,
        "counts": counts,
        "skipped": skipped,
        "repository_shallow": shallow,
        "repository_grafted": grafted,
        "metadata": metadata_scan,
        "identity": {"kind": "reachable-git-object-set/1", "sha256": _digest(sorted(object_ids))},
    }


def _empty_working_tree_scan() -> dict[str, Any]:
    return {
        "enabled": False,
        "counts": {
            "tracked_index_paths": 0,
            "nonignored_untracked_paths": 0,
            "listed_paths": 0,
            "regular_files_scanned": 0,
            "index_fallback_files_scanned": 0,
            "symlinks_checked": 0,
        },
        "skipped": {"binary": 0, "large": 0, "missing": 0, "nonregular": 0},
    }


def _empty_blob_scan() -> dict[str, Any]:
    return {
        "enabled": False,
        "counts": {
            "listed_paths": 0,
            "regular_files_scanned": 0,
            "symlinks_checked": 0,
            "unique_blobs_read": 0,
        },
        "skipped": {"binary": 0, "large": 0, "nonregular": 0},
    }


def _empty_history_scan() -> dict[str, Any]:
    return {
        "enabled": False,
        "requested_ref": None,
        "resolved_commit": None,
        "counts": {
            "historical_paths_observed": 0,
            "reachable_objects": 0,
            "unique_blobs": 0,
            "text_blobs_scanned": 0,
        },
        "skipped": {"binary": 0, "large": 0, "without_path": 0},
    }


def _coverage_limitations(scans: dict[str, dict[str, Any]]) -> list[str]:
    limitations: list[str] = []
    for label, scan in scans.items():
        if not scan["enabled"]:
            continue
        for reason, count in scan["skipped"].items():
            # A tracked working-tree deletion is intentionally absent from that
            # candidate; the index scan still reports what would be committed.
            if label == "working-tree" and reason == "missing":
                continue
            if count:
                limitations.append(f"{label}.{reason}")
    if not any(scan["enabled"] for scan in scans.values()):
        limitations.append("no-content-surface-selected")
    return sorted(limitations)


def _coverage_facets(scans: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    facets: list[dict[str, Any]] = []
    for name, scan in scans.items():
        selected = scan["enabled"]
        skipped = {reason: count for reason, count in scan["skipped"].items()
                   if count and not (name == "working-tree" and reason == "missing")}
        text_gaps = {reason: count for reason, count in skipped.items()
                     if not reason.startswith("metadata_") and reason not in {"shallow_boundary", "grafted_ancestry", "lfs_payload"}}
        facets.extend([
            {"surface": name + ".paths", "status": "observed" if selected else "not_selected"},
            {"surface": name + ".content", "status":
             "not_selected" if not selected else "unobserved" if text_gaps else "observed",
             "unobserved_reasons": text_gaps,
             "observation": "UTF-8 text and symlink target bytes evaluated by the listed rules"},
        ])
        meta = scan.get("metadata")
        if name in {"ref", "history"}:
            gaps = {reason: count for reason, count in (meta or {}).get("skipped", {}).items() if count}
            facets.append({"surface": name + ".commit-and-selected-tag-metadata", "status":
                           "not_selected" if not meta else "unobserved" if gaps else "observed",
                           "unobserved_reasons": gaps})
        facets.append({"surface": name + ".lfs-payloads", "status":
                       "unobserved" if skipped.get("lfs_payload") else "not_selected",
                       "pointer_bindings_observed": skipped.get("lfs_payload", 0),
                       "observation": "Pointer text does not attest its separately stored object"})
    history = scans["history"]
    facets.append({
        "surface": "history.ancestry", "status": "not_selected" if not history["enabled"] else
        "unobserved" if history.get("repository_shallow") or history.get("repository_grafted") else "observed",
        "observation": "Local ancestry of the explicitly selected history ref; no fetch attempted",
    })
    for surface in ("ignored-worktree-files", "unselected-refs-and-tags", "remote-release-assets",
                    "submodule-contents", "human-identity-rights-and-composed-disclosure"):
        facets.append({"surface": surface, "status": "not_selected"})
    return facets


def _inspect(
    repo: Path,
    history_ref: str | None,
    candidate_ref: str | None,
    candidate_mode: str,
    max_bytes: int,
) -> dict[str, Any]:
    if max_bytes <= 0:
        raise InspectionError("max bytes must be positive")
    if candidate_mode not in {"working-tree", "index", "both", "none"}:
        raise InspectionError("unsupported candidate mode")
    requested = repo.expanduser()
    if '..' in requested.parts:
        raise InspectionError("unsafe repository path")
    requested = Path(os.path.abspath(requested))
    # Validate before Git or resolve() can hide a symlinked input ancestor.
    with _candidate_parent(requested, ".git"):
        pass
    root_text = _git_text(requested, "rev-parse", "--show-toplevel").strip()
    root = Path(root_text)
    with _candidate_parent(root, ".git"):
        pass
    head, branch = _head_and_branch(root)
    status = _parse_status(root)
    findings: set[tuple[str, str, str]] = set()

    deleted_paths = {
        entry["path"] for entry in status if "D" in entry["code"]
    }
    working_tree = (
        _scan_working_tree_candidate(root, max_bytes, findings, deleted_paths)
        if candidate_mode in {"working-tree", "both"}
        else _empty_working_tree_scan()
    )
    index = (
        _scan_blob_candidate(root, _index_entries(root), "index", max_bytes, findings)
        if candidate_mode in {"index", "both"}
        else _empty_blob_scan()
    )
    if candidate_ref is None:
        ref = _empty_blob_scan()
        ref.update({"requested_ref": None, "resolved_commit": None})
    else:
        resolved_ref = _resolve_commit(root, candidate_ref, "candidate ref")
        ref = _scan_blob_candidate(
            root,
            _tree_entries(root, resolved_ref),
            "ref",
            max_bytes,
            findings,
        )
        ref.update({"requested_ref": candidate_ref, "resolved_commit": resolved_ref})
        ref["requested_ref"] = _safe_label(candidate_ref)
        ref["metadata"] = _scan_metadata(
            root, candidate_ref, [resolved_ref], max_bytes, findings, "ref-metadata",
        )
        ref["skipped"].update(ref["metadata"]["skipped"])
    history = (
        _scan_history(root, history_ref, max_bytes, findings)
        if history_ref is not None
        else _empty_history_scan()
    )

    scans = {
        "working-tree": working_tree,
        "index": index,
        "ref": ref,
        "history": history,
    }
    if candidate_mode in {"working-tree", "index", "both"}:
        unmerged = _run_git_bytes(root, "ls-files", "--unmerged", "-z").stdout
        if unmerged:
            for name in ("working-tree", "index"):
                if scans[name]["enabled"]:
                    scans[name]["skipped"]["unmerged_index"] = 1
                    scans[name]["unmerged_identity"] = hashlib.sha256(unmerged).hexdigest()
    for requested_ref, scan in ((candidate_ref, ref), (history_ref, history)):
        if requested_ref is not None:
            final_ref = _run_git_bytes(root, "rev-parse", "--verify", "--end-of-options", requested_ref).stdout.decode("ascii").strip()
            if final_ref != scan["metadata"]["selected_object"]:
                raise InspectionError("selected ref changed during inspection")
    coverage_limited_by = _coverage_limitations(scans)
    surfaces = {
        name: {"selected": scan["enabled"], "identity": scan.get("identity"),
               "resolved_commit": scan.get("resolved_commit"),
               "metadata_identity": scan.get("metadata", {}).get("identity"),
               "unmerged_identity": scan.get("unmerged_identity")}
        for name, scan in scans.items()
    }
    rules = {"version": RULE_VERSION,
             "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             "digest_basis": "complete-inspector-implementation"}

    ordered_findings = sorted(findings)
    return {
        "schema_version": 2,
        "report_format": REPORT_FORMAT,
        "inspection_kind": "read-only-publication-candidate-signal-scan",
        "subject": {
            "id": "sha256:" + _digest(surfaces), "surfaces": surfaces,
            "binding": "selected path/content identities and resolved Git objects",
            "atomic_snapshot": not working_tree["enabled"] and not index["enabled"],
        },
        "rules": rules,
        "repository": {
            "root": "<redacted>",
            "head": head,
            "branch": _safe_label(branch) if branch else None,
            "detached": branch is None and head is not None,
            "clean": not status,
            "status": [{key: _safe_label(value) for key, value in entry.items()} for entry in status],
            "remotes": _remote_inventory(root),
        },
        "scan_scope": {
            "candidate_mode": candidate_mode,
            "working_tree": working_tree,
            "index": index,
            "ref": ref,
            "history": history,
            "max_text_blob_bytes": max_bytes,
        },
        "counts": {
            "findings": len(ordered_findings),
            "working_tree": working_tree["counts"],
            "index": index["counts"],
            "ref": ref["counts"],
            "history": history["counts"],
        },
        "skips": {
            "working_tree": working_tree["skipped"],
            "index": index["skipped"],
            "ref": ref["skipped"],
            "history": history["skipped"],
        },
        "findings": [
            {"rule_id": rule_id, "path": _safe_label(path), "scope": scope}
            for scope, rule_id, path in ordered_findings
        ],
        "scan_complete": not coverage_limited_by,
        "coverage_limited_by": coverage_limited_by,
        "coverage": {"facets": _coverage_facets(scans), "limitations": coverage_limited_by},
        "claims": {
            "selected_text_surfaces_exhausted": not coverage_limited_by,
            "no_rule_matches_on_observed_surfaces": bool(any(scan["enabled"] for scan in scans.values())) and not ordered_findings,
            "publication_ready": False,
        },
        "scan_complete_semantics": "Compatibility alias for selected_text_surfaces_exhausted; not a safety or publication claim",
        "report_handling": "Private review material: relative names and object digests may themselves disclose context",
        "manual_review_required": True,
        "readiness_certificate": False,
        "publication_readiness_claimed": False,
    }


def inspect(
    repo: Path,
    history_ref: str | None,
    candidate_ref: str | None,
    candidate_mode: str,
    max_bytes: int,
) -> dict[str, Any]:
    """Return deterministic observations or raise a value-free InspectionError.

    No result certifies public safety. A mutable worktree read is not an atomic
    snapshot; a caller must bind/recheck its candidate before later actions.
    Safe worktree traversal currently requires POSIX dir-fd/O_NOFOLLOW support.
    """
    try:
        return _inspect(repo, history_ref, candidate_ref, candidate_mode, max_bytes)
    except InspectionError:
        raise
    except (OSError, ValueError):
        raise InspectionError("filesystem or object data unavailable") from None


def _print_human(result: dict[str, Any]) -> None:
    repository = result["repository"]
    working_tree = result["scan_scope"]["working_tree"]
    index = result["scan_scope"]["index"]
    ref = result["scan_scope"]["ref"]
    history = result["scan_scope"]["history"]
    print(f"repository.root: {repository['root']}")
    print(f"repository.head: {repository['head'] or '(unborn)'}")
    print(f"repository.branch: {repository['branch'] or '(detached)'}")
    print(f"repository.clean: {str(repository['clean']).lower()}")
    print(f"candidate.mode: {result['scan_scope']['candidate_mode']}")
    print(f"working_tree.enabled: {str(working_tree['enabled']).lower()}")
    print(f"index.enabled: {str(index['enabled']).lower()}")
    print(f"ref.enabled: {str(ref['enabled']).lower()}")
    if ref["enabled"]:
        print(f"ref.resolved_commit: {ref['resolved_commit']}")
    print(f"history.enabled: {str(history['enabled']).lower()}")
    if history["enabled"]:
        print(f"history.resolved_commit: {history['resolved_commit']}")
    print(f"counts.findings: {result['counts']['findings']}")
    print(
        "counts.working_tree.regular_files_scanned: "
        f"{result['counts']['working_tree']['regular_files_scanned']}"
    )
    print(
        "counts.index.regular_files_scanned: "
        f"{result['counts']['index']['regular_files_scanned']}"
    )
    print(f"counts.history.unique_blobs: {result['counts']['history']['unique_blobs']}")
    print(f"scan_complete: {str(result['scan_complete']).lower()}")
    print(
        "coverage_limited_by: "
        + (", ".join(result["coverage_limited_by"]) or "none")
    )
    print("manual_review_required: true")
    print("readiness_certificate: false")
    print("publication_readiness_claimed: false")
    print("findings:")
    for finding in result["findings"]:
        print(f"  - [{finding['scope']}] {finding['rule_id']}: {finding['path']}")


def _build_parser() -> argparse.ArgumentParser:
    parser = PrivateArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path, help="Git worktree to inspect")
    parser.add_argument(
        "--candidate",
        choices=("working-tree", "index", "both", "none"),
        default="both",
        help="Candidate state to scan before any optional exact ref or history scan",
    )
    parser.add_argument(
        "--candidate-ref",
        help="Optional commit-ish whose exact tree should be scanned with scope 'ref'",
    )
    parser.add_argument(
        "--history-ref",
        help="Optional commit-ish whose locally reachable history, commit metadata and selected tag chain are scanned",
    )
    parser.add_argument("--json", action="store_true", help="Emit structured JSON")
    parser.add_argument(
        "--fail-on-incomplete",
        action="store_true",
        help="Return exit status 3 for unobserved selected coverage (takes priority over status 1)",
    )
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Return exit status 1 when review findings are present",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_BYTES,
        help="Largest regular file or history blob to inspect as text",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        result = inspect(
            args.repo,
            args.history_ref,
            args.candidate_ref,
            args.candidate,
            args.max_bytes,
        )
    except InspectionError as error:
        print(f"inspection failed: {error}", file=sys.stderr)
        return 2
    except (OSError, ValueError):
        print("inspection failed: filesystem or object data unavailable", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _print_human(result)
    if args.fail_on_incomplete and not result["scan_complete"]:
        return 3
    if args.fail_on_findings and result["findings"]:
        return 1
    # By default, findings remain review signals rather than tool failures.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
