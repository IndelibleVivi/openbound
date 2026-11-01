#!/usr/bin/env python3
"""Project explicitly selected working-tree files into an isolated public candidate.

Python 3.10+, standard library only.  This program does not execute project code,
follow links, fetch objects, initialize Git, or authorize publication.  The plan
and receipt are private control material; keep them outside the candidate.

    inventory --source PRIVATE_ROOT
    materialize --source PRIVATE_ROOT --plan PLAN.json --target NEW_ROOT --receipt PRIVATE.json
    verify --target NEW_ROOT --receipt PRIVATE.json [--source PRIVATE_ROOT --plan PLAN.json]

``inventory`` emits a review-required envelope containing a proposed plan, not an
instruction to publish all tracked files.  Only ``materialize`` writes a candidate.
Updating a source or plan requires a new target and receipt.  Successful reruns
against an unchanged owned candidate are no-ops.  A prepared receipt supports
recovery after a lost acknowledgement or interruption around directory rename.

Receipts prove observations of selected file bytes, modes and inventory, not an
atomic source snapshot, absence of secrets, project functionality or permission.
Use a quiescent checkout for selection.  A second full source read detects drift
during preparation, but is not a filesystem transaction or security sandbox.
Linux exclusive rename is exercised by the test suite; Darwin uses the native
exclusive rename primitive and must be validated on the intended host.  Other
hosts fail closed instead of falling back to an overwriting rename.
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import stat
import subprocess
import sys
import unicodedata
from typing import Any, Iterator


PLAN_SCHEMA = "openbound-projection/1"
RECEIPT_SCHEMA = "openbound-projection-receipt/1"
ENGINE = "openbound-projector/1.0"
MAX_FILES = 4096
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_PLAN_BYTES = 4 * 1024 * 1024
MAX_RECEIPT_BYTES = 8 * 1024 * 1024
ROOT_MODE = 0o700
DIR_MODE = 0o755


class ProjectionError(Exception):
    """A deliberately content-free diagnostic; never interpolate source text."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> None:
    raise ProjectionError(code)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _bytes_digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            _fail("duplicate_json_key")
        out[key] = value
    return out


def _decode_json(data: bytes) -> dict[str, Any]:
    try:
        result = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs,
                            parse_constant=lambda _: _fail("invalid_json"))
    except (ValueError, UnicodeError, RecursionError):
        _fail("invalid_json")
    if not isinstance(result, dict):
        _fail("invalid_json_object")
    return result


def _relative(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 1024:
        _fail("invalid_relative_path")
    if (value.startswith("/") or "\\" in value or ":" in value
            or unicodedata.normalize("NFC", value) != value
            or any(ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in value)):
        _fail("invalid_relative_path")
    parts = value.split("/")
    for part in parts:
        if not part or part in (".", "..") or part[-1] in (" ", "."):
            _fail("invalid_relative_path")
        folded = part.casefold()
        if folded == ".git" or folded == ".openbound" or folded.startswith(".openbound-"):
            _fail("control_path_forbidden")
        # Portable destinations: avoid Windows device aliases even on POSIX.
        stem = folded.split(".", 1)[0]
        if stem in {"con", "prn", "aux", "nul"} or stem in {
                f"{prefix}{n}" for prefix in ("com", "lpt") for n in range(1, 10)}:
            _fail("invalid_relative_path")
    return value


def _collision_check(paths: list[str]) -> None:
    """Check files and directory spelling, including case-insensitive hosts."""
    files: set[str] = set()
    dirs: set[str] = set()
    spellings: dict[str, str] = {}
    for path in paths:
        bits = path.split("/")
        for depth in range(1, len(bits) + 1):
            prefix = "/".join(bits[:depth])
            folded = prefix.casefold()
            if folded in spellings and spellings[folded] != prefix:
                _fail("path_collision")
            spellings[folded] = prefix
        key = path.casefold()
        if key in files or key in dirs:
            _fail("path_collision")
        for depth in range(1, len(bits)):
            prefix = "/".join(bits[:depth]).casefold()
            if prefix in files:
                _fail("path_collision")
            dirs.add(prefix)
        files.add(key)


def validate_plan(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"schema", "files"}:
        _fail("invalid_plan")
    if value["schema"] != PLAN_SCHEMA or not isinstance(value["files"], list):
        _fail("invalid_plan")
    if not 1 <= len(value["files"]) <= MAX_FILES:
        _fail("file_count_limit")
    files: list[dict[str, Any]] = []
    for item in value["files"]:
        if (not isinstance(item, dict) or not {"source", "target"} <= set(item)
                or set(item) - {"source", "target", "replacements"}):
            _fail("invalid_plan_entry")
        entry: dict[str, Any] = {"source": _relative(item["source"]),
                                 "target": _relative(item["target"])}
        replacements = item.get("replacements", [])
        if not isinstance(replacements, list) or len(replacements) > 256:
            _fail("invalid_replacements")
        normalized = []
        for rule in replacements:
            if not isinstance(rule, dict) or set(rule) != {"old", "new", "expected_count"}:
                _fail("invalid_replacement")
            if (not isinstance(rule["old"], str) or not rule["old"]
                    or not isinstance(rule["new"], str)
                    or type(rule["expected_count"]) is not int or rule["expected_count"] < 0):
                _fail("invalid_replacement")
            try:
                old_size, new_size = len(rule["old"].encode("utf-8")), len(rule["new"].encode("utf-8"))
            except UnicodeError:
                _fail("invalid_replacement")
            if old_size > MAX_FILE_BYTES or new_size > MAX_FILE_BYTES:
                _fail("replacement_size_limit")
            normalized.append(dict(rule))
        if normalized:
            entry["replacements"] = normalized
        files.append(entry)
    _collision_check([entry["target"] for entry in files])
    # Reusing one exact source for several targets is deliberate and allowed.
    _collision_check(sorted({entry["source"] for entry in files}))
    normalized_plan = {"schema": PLAN_SCHEMA, "files": sorted(files, key=lambda item: item["target"])}
    if len(_canonical(normalized_plan)) > MAX_PLAN_BYTES:
        _fail("plan_size_limit")
    return normalized_plan


def _absolute(value: str | os.PathLike[str]) -> Path:
    path = os.fspath(value)
    if not isinstance(path, str) or "\x00" in path or ".." in Path(path).parts:
        _fail("invalid_location")
    return Path(os.path.abspath(path))


def _platform_flags() -> int:
    if not all(hasattr(os, name) for name in ("O_NOFOLLOW", "O_DIRECTORY", "O_CLOEXEC")):
        _fail("secure_filesystem_unavailable")
    return os.O_NOFOLLOW | os.O_CLOEXEC


@contextlib.contextmanager
def _directory(path: Path) -> Iterator[int]:
    """Walk absolute ancestors without following symlinks."""
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | _platform_flags())
    try:
        for component in path.parts[1:]:
            next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | _platform_flags(), dir_fd=fd)
            os.close(fd)
            fd = next_fd
        yield fd
    except OSError as exc:
        _fail("unsafe_or_missing_directory" if exc.errno in (errno.ELOOP, errno.ENOTDIR, errno.ENOENT)
              else "filesystem_error")
    finally:
        os.close(fd)


@contextlib.contextmanager
def _relative_parent(root_fd: int, rel: str) -> Iterator[tuple[int, str]]:
    bits = rel.split("/")
    fd = os.dup(root_fd)
    try:
        for component in bits[:-1]:
            next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | _platform_flags(), dir_fd=fd)
            os.close(fd)
            fd = next_fd
        yield fd, bits[-1]
    finally:
        os.close(fd)


def _signature(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _read_at(root_fd: int, rel: str, limit: int) -> tuple[bytes, int]:
    try:
        with _relative_parent(root_fd, rel) as (parent_fd, name):
            fd = os.open(name, os.O_RDONLY | _platform_flags() | os.O_NONBLOCK, dir_fd=parent_fd)
            try:
                before = os.fstat(fd)
                if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                    _fail("nonregular_or_linked_file")
                if stat.S_IMODE(before.st_mode) & 0o7000:
                    _fail("special_permission_bits")
                if before.st_size > limit:
                    _fail("file_size_limit")
                chunks: list[bytes] = []
                size = 0
                while True:
                    chunk = os.read(fd, min(65536, limit + 1 - size))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > limit:
                        _fail("file_size_limit")
                after = os.fstat(fd)
                linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                if _signature(before) != _signature(after) or _signature(after) != _signature(linked):
                    _fail("file_changed_during_read")
                return b"".join(chunks), stat.S_IMODE(after.st_mode)
            finally:
                os.close(fd)
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            _fail("selected_file_missing")
        if exc.errno in (errno.ELOOP, errno.ENOTDIR):
            _fail("symlink_or_invalid_ancestor")
        _fail("filesystem_error")


def _read_private(path: Path, limit: int) -> bytes:
    with _directory(path.parent) as parent_fd:
        data, _ = _read_at(parent_fd, path.name, limit)
        return data


def load_plan(path: str | os.PathLike[str]) -> dict[str, Any]:
    return validate_plan(_decode_json(_read_private(_absolute(path), MAX_PLAN_BYTES)))


def _file_record(path: str, data: bytes, mode: int) -> dict[str, Any]:
    return {"path": path, "sha256": _bytes_digest(data), "size": len(data), "mode": mode}


def _source_observation(source: Path, plan: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, tuple[bytes, int]]]:
    records = []
    blobs: dict[str, tuple[bytes, int]] = {}
    total = 0
    with _directory(source) as root_fd:
        for rel in sorted({item["source"] for item in plan["files"]}):
            data, mode = _read_at(root_fd, rel, MAX_FILE_BYTES)
            total += len(data)
            if total > MAX_TOTAL_BYTES:
                _fail("total_size_limit")
            records.append(_file_record(rel, data, mode))
            blobs[rel] = (data, mode)
    return records, blobs


def _transform(plan: dict[str, Any], source_blobs: dict[str, tuple[bytes, int]]) -> dict[str, tuple[bytes, int]]:
    result = {}
    total = 0
    for entry in plan["files"]:
        data, mode = source_blobs[entry["source"]]
        if entry.get("replacements"):
            try:
                content = data.decode("utf-8")
            except UnicodeError:
                _fail("replacement_requires_utf8")
            for rule in entry["replacements"]:
                count = content.count(rule["old"])
                if count != rule["expected_count"]:
                    _fail("replacement_count_mismatch")
                # Bound allocations before replacing an attacker-controlled value.
                projected_size = len(content.encode("utf-8")) + count * (
                    len(rule["new"].encode("utf-8")) - len(rule["old"].encode("utf-8")))
                if projected_size > MAX_FILE_BYTES:
                    _fail("file_size_limit")
                content = content.replace(rule["old"], rule["new"])
            data = content.encode("utf-8")
        total += len(data)
        if len(data) > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
            _fail("total_size_limit")
        result[entry["target"]] = (data, mode)
    return result


def _expected_tree(blobs: dict[str, tuple[bytes, int]]) -> dict[str, Any]:
    dirs: set[str] = set()
    for rel in blobs:
        bits = rel.split("/")
        dirs.update("/".join(bits[:index]) for index in range(1, len(bits)))
    return {"root_mode": ROOT_MODE,
            "directories": [{"path": path, "mode": DIR_MODE} for path in sorted(dirs)],
            "files": [_file_record(path, data, mode) for path, (data, mode) in sorted(blobs.items())]}


def _observe_tree(target: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    dirs: list[dict[str, Any]] = []
    total = 0

    def walk(fd: int, prefix: str) -> None:
        nonlocal total
        for name in sorted(os.listdir(fd)):
            rel = f"{prefix}/{name}" if prefix else name
            _relative(rel)
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                dirs.append({"path": rel, "mode": stat.S_IMODE(info.st_mode)})
                if len(dirs) > MAX_FILES * 32:
                    _fail("inventory_limit")
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | _platform_flags(), dir_fd=fd)
                try:
                    walk(child, rel)
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                data, mode = _read_at(fd, name, MAX_FILE_BYTES)
                total += len(data)
                files.append(_file_record(rel, data, mode))
                if len(files) > MAX_FILES or total > MAX_TOTAL_BYTES:
                    _fail("inventory_limit")
            else:
                _fail("nonregular_or_linked_file")

    try:
        with _directory(target) as fd:
            root_mode = stat.S_IMODE(os.fstat(fd).st_mode)
            walk(fd, "")
    except (OSError, RecursionError):
        _fail("candidate_inventory_failed")
    return {"root_mode": root_mode, "directories": sorted(dirs, key=lambda item: item["path"]),
            "files": sorted(files, key=lambda item: item["path"])}


def _locations(source: Path, target: Path, receipt: Path) -> None:
    if source == target or source in target.parents or target in source.parents:
        _fail("source_target_overlap")
    if receipt in (source, target) or source in receipt.parents or target in receipt.parents:
        _fail("receipt_must_be_outside_roots")
    if receipt == target.parent or not target.name or not receipt.name:
        _fail("invalid_location")
    # Compare real directory identities as well as spelling.  A case-insensitive
    # volume (or a bind-mounted directory alias) must not turn an apparently
    # separate destination into writes inside the source.
    source_ancestors = _ancestor_identities(source)
    source_identity = source_ancestors[-1]
    target_ancestors = _ancestor_identities(target.parent)
    receipt_ancestors = _ancestor_identities(receipt.parent)
    if source_identity in target_ancestors:
        _fail("source_target_overlap")
    if source_identity in receipt_ancestors:
        _fail("receipt_must_be_outside_roots")
    with _directory(target.parent) as parent_fd:
        if _exists_at(parent_fd, target.name):
            info = os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                target_identity = (info.st_dev, info.st_ino)
                if target_identity in source_ancestors:
                    _fail("source_target_overlap")
                if target_identity in receipt_ancestors:
                    _fail("receipt_must_be_outside_roots")


def _ancestor_identities(path: Path) -> list[tuple[int, int]]:
    identities = []
    # The path is short, and each open validates symlink-free ancestry.  This is
    # local metadata only; no directory contents or project hooks are evaluated.
    for parent in [*reversed(path.parents), path]:
        with _directory(parent) as fd:
            info = os.fstat(fd)
            identities.append((info.st_dev, info.st_ino))
    return identities


def _make_receipt(source: Path, target: Path, plan: dict[str, Any], records: list[dict[str, Any]],
                  tree: dict[str, Any]) -> dict[str, Any]:
    return {"schema": RECEIPT_SCHEMA, "engine": ENGINE, "state": "prepared",
            "plan_sha256": _digest(plan), "source_root_sha256": _digest(str(source)),
            "target_root_sha256": _digest(str(target)),
            "source": {"identity_kind": "observed-selected-files", "atomic_snapshot": False,
                       "files": records, "sha256": _digest(records)},
            "candidate": {"identity_kind": "files-bytes-modes-inventory", "tree": tree,
                          "sha256": _digest(tree)}}


def _sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _validate_records(records: Any) -> None:
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_FILES:
        _fail("invalid_receipt")
    total = 0
    for entry in records:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256", "size", "mode"}:
            _fail("invalid_receipt")
        _relative(entry["path"])
        if (not _sha(entry["sha256"]) or type(entry["size"]) is not int
                or not 0 <= entry["size"] <= MAX_FILE_BYTES
                or type(entry["mode"]) is not int or not 0 <= entry["mode"] <= 0o777):
            _fail("invalid_receipt")
        total += entry["size"]
    if total > MAX_TOTAL_BYTES or records != sorted(records, key=lambda item: item["path"]):
        _fail("invalid_receipt")
    _collision_check([entry["path"] for entry in records])


def _load_receipt(path: Path) -> dict[str, Any]:
    value = _decode_json(_read_private(path, MAX_RECEIPT_BYTES))
    try:
        if (set(value) != {"schema", "engine", "state", "plan_sha256", "source_root_sha256",
                           "target_root_sha256", "source", "candidate"}
                or value["schema"] != RECEIPT_SCHEMA or value["engine"] != ENGINE
                or value["state"] not in ("prepared", "complete")
                or any(not _sha(value[key]) for key in
                       ("plan_sha256", "source_root_sha256", "target_root_sha256"))):
            _fail("invalid_receipt")
        src = value["source"]
        candidate = value["candidate"]
        if (not isinstance(src, dict) or set(src) != {"identity_kind", "atomic_snapshot", "files", "sha256"}
                or src["identity_kind"] != "observed-selected-files" or src["atomic_snapshot"] is not False
                or not isinstance(candidate, dict) or set(candidate) != {"identity_kind", "tree", "sha256"}
                or candidate["identity_kind"] != "files-bytes-modes-inventory"):
            _fail("invalid_receipt")
        _validate_records(src["files"])
        tree = candidate["tree"]
        if (not isinstance(tree, dict) or set(tree) != {"root_mode", "files", "directories"}
                or tree["root_mode"] != ROOT_MODE or not isinstance(tree["directories"], list)):
            _fail("invalid_receipt")
        _validate_records(tree["files"])
        expected_dirs = set()
        for entry in tree["files"]:
            bits = entry["path"].split("/")
            expected_dirs.update("/".join(bits[:i]) for i in range(1, len(bits)))
        if tree["directories"] != [{"path": p, "mode": DIR_MODE} for p in sorted(expected_dirs)]:
            _fail("invalid_receipt")
        if src["sha256"] != _digest(src["files"]) or candidate["sha256"] != _digest(tree):
            _fail("receipt_digest_mismatch")
    except (TypeError, KeyError):
        _fail("invalid_receipt")
    return value


def _target_matches(target: Path, receipt: dict[str, Any]) -> None:
    if receipt["target_root_sha256"] != _digest(str(target)):
        _fail("target_location_mismatch")
    if _observe_tree(target) != receipt["candidate"]["tree"]:
        _fail("candidate_changed")


def _source_matches(source: Path, plan: dict[str, Any], receipt: dict[str, Any]) -> None:
    if receipt["source_root_sha256"] != _digest(str(source)):
        _fail("source_location_mismatch")
    if receipt["plan_sha256"] != _digest(plan):
        _fail("plan_changed")
    records, _ = _source_observation(source, plan)
    if records != receipt["source"]["files"]:
        _fail("source_changed")


def _exists_at(fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=fd, follow_symlinks=False)
        return True
    except FileNotFoundError:
        return False


@contextlib.contextmanager
def _receipt_lock(parent_fd: int, name: str) -> Iterator[None]:
    try:
        import fcntl
    except ImportError:
        _fail("secure_filesystem_unavailable")
    fd = os.open(f".{name}.openbound-lock", os.O_CREAT | os.O_RDWR | _platform_flags(), 0o600,
                 dir_fd=parent_fd)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            _fail("unsafe_receipt_lock")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            _fail("receipt_busy")
        os.fchmod(fd, 0o600)
        yield
    finally:
        os.close(fd)
    # Retain the private empty lock file: unlinking it creates a lock-inode race.


def _write_receipt(parent_fd: int, name: str, value: dict[str, Any], replace: bool) -> None:
    temp_name = f".{name}.tmp-{secrets.token_hex(8)}"
    fd = os.open(temp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _platform_flags(), 0o600,
                 dir_fd=parent_fd)
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(_canonical(value) + b"\n")
            stream.flush()
            os.fsync(fd)
        if replace:
            # Only an already parsed, operation-bound receipt is replaced while
            # holding this receipt's cooperative process lock.
            info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                _fail("unsafe_receipt")
            os.replace(temp_name, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        else:
            # link+unlink is an atomic no-clobber file publication on POSIX.
            os.link(temp_name, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd, follow_symlinks=False)
            os.unlink(temp_name, dir_fd=parent_fd)
        os.fsync(parent_fd)
    finally:
        os.close(fd)
        if _exists_at(parent_fd, temp_name):
            os.unlink(temp_name, dir_fd=parent_fd)


def _mkdirs(root_fd: int, rel: str) -> None:
    fd = os.dup(root_fd)
    try:
        for component in rel.split("/"):
            try:
                os.mkdir(component, DIR_MODE, dir_fd=fd)
            except FileExistsError:
                pass
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | _platform_flags(), dir_fd=fd)
            os.fchmod(child, DIR_MODE)
            os.close(fd)
            fd = child
    finally:
        os.close(fd)


def _write_tree(root_fd: int, blobs: dict[str, tuple[bytes, int]]) -> None:
    for rel, (data, mode) in sorted(blobs.items()):
        parent = str(PurePosixPath(rel).parent)
        if parent != ".":
            _mkdirs(root_fd, parent)
        with _relative_parent(root_fd, rel) as (parent_fd, name):
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _platform_flags(), 0o600,
                         dir_fd=parent_fd)
            try:
                with os.fdopen(fd, "wb", closefd=False) as stream:
                    stream.write(data)
                    stream.flush()
                os.fchmod(fd, mode)
                os.fsync(fd)
                os.fsync(parent_fd)
            finally:
                os.close(fd)
    os.fsync(root_fd)


def _publish_directory(parent_fd: int, stage_name: str, target_name: str) -> None:
    """An existing empty directory must survive even a concurrent publication."""
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        fn, flag = libc.renameat2, 1  # RENAME_NOREPLACE
    elif sys.platform == "darwin" and hasattr(libc, "renameatx_np"):
        fn, flag = libc.renameatx_np, 0x00000004  # RENAME_EXCL
    else:
        _fail("atomic_publish_unavailable")
    fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    fn.restype = ctypes.c_int
    if fn(parent_fd, os.fsencode(stage_name), parent_fd, os.fsencode(target_name), flag) != 0:
        err = ctypes.get_errno()
        if err in (errno.EEXIST, errno.ENOTEMPTY):
            _fail("candidate_already_exists")
        if err in (errno.ENOSYS, errno.EINVAL, errno.ENOTSUP):
            _fail("atomic_publish_unavailable")
        _fail("atomic_publish_failed")
    os.fsync(parent_fd)


def _remove_owned_stage(parent_fd: int, name: str, identity: tuple[int, int]) -> None:
    try:
        info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    if (info.st_dev, info.st_ino) != identity or not stat.S_ISDIR(info.st_mode):
        return  # Never remove a substituted directory.

    def clear(fd: int) -> None:
        for entry in os.listdir(fd):
            item = os.stat(entry, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(item.st_mode):
                child = os.open(entry, os.O_RDONLY | os.O_DIRECTORY | _platform_flags(), dir_fd=fd)
                try:
                    clear(child)
                finally:
                    os.close(child)
                os.rmdir(entry, dir_fd=fd)
            else:
                os.unlink(entry, dir_fd=fd)

    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | _platform_flags(), dir_fd=parent_fd)
    try:
        clear(fd)
    finally:
        os.close(fd)
    os.rmdir(name, dir_fd=parent_fd)


def _summary(status: str, receipt: dict[str, Any], source_checked: bool = True) -> dict[str, Any]:
    return {"status": status, "candidate_sha256": receipt["candidate"]["sha256"],
            "plan_sha256": receipt["plan_sha256"], "file_count": len(receipt["candidate"]["tree"]["files"]),
            "source_checked": source_checked, "atomic_source_snapshot": False,
            "scope": "selected-bytes-modes-inventory; no safety, functionality, or publication approval"}


def materialize(source: str | os.PathLike[str], plan: dict[str, Any], target: str | os.PathLike[str],
                receipt: str | os.PathLike[str]) -> dict[str, Any]:
    """Create once; do not update/clean an existing candidate or change the source."""
    source_path, target_path, receipt_path = map(_absolute, (source, target, receipt))
    _locations(source_path, target_path, receipt_path)
    plan = validate_plan(plan)
    records, source_blobs = _source_observation(source_path, plan)
    blobs = _transform(plan, source_blobs)
    expected = _make_receipt(source_path, target_path, plan, records, _expected_tree(blobs))
    with _directory(target_path.parent) as target_parent, _directory(receipt_path.parent) as receipt_parent:
        with _receipt_lock(receipt_parent, receipt_path.name):
            existing = _exists_at(receipt_parent, receipt_path.name)
            previous = _load_receipt(receipt_path) if existing else None
            if previous is not None:
                # All operation identity fields must still agree.  State alone is mutable.
                for key in expected.keys() - {"state"}:
                    if previous[key] != expected[key]:
                        _fail("receipt_operation_changed")
            if _exists_at(target_parent, target_path.name):
                if previous is None:
                    _fail("candidate_already_exists")
                _target_matches(target_path, previous)
                _source_matches(source_path, plan, previous)
                if previous["state"] == "prepared":
                    previous["state"] = "complete"
                    _write_receipt(receipt_parent, receipt_path.name, previous, replace=True)
                    return _summary("recovered", previous)
                return _summary("no_change", previous)
            if previous is not None and previous["state"] == "complete":
                _fail("owned_candidate_missing")
            stage_name = f".openbound-stage-{secrets.token_hex(12)}"
            os.mkdir(stage_name, ROOT_MODE, dir_fd=target_parent)
            stage_fd = os.open(stage_name, os.O_RDONLY | os.O_DIRECTORY | _platform_flags(), dir_fd=target_parent)
            stage_info = os.fstat(stage_fd)
            stage_identity = (stage_info.st_dev, stage_info.st_ino)
            try:
                os.fchmod(stage_fd, ROOT_MODE)
                _write_tree(stage_fd, blobs)
                # A fresh observation catches changes after selection and before publish.
                _source_matches(source_path, plan, expected)
                if _observe_tree(target_path.parent / stage_name) != expected["candidate"]["tree"]:
                    _fail("staged_candidate_changed")
                if previous is None:
                    _write_receipt(receipt_parent, receipt_path.name, expected, replace=False)
                _publish_directory(target_parent, stage_name, target_path.name)
                # Bind successful completion to an observation at the final
                # location too, not merely to the bytes in the staging name.
                _target_matches(target_path, expected)
                expected["state"] = "complete"
                _write_receipt(receipt_parent, receipt_path.name, expected, replace=True)
            finally:
                os.close(stage_fd)
                _remove_owned_stage(target_parent, stage_name, stage_identity)
    return _summary("materialized" if previous is None else "resumed", expected)


def verify(target: str | os.PathLike[str], receipt: str | os.PathLike[str],
           source: str | os.PathLike[str] | None = None, plan: dict[str, Any] | None = None) -> dict[str, Any]:
    """Verify only a complete receipt; use materialize to recover prepared state."""
    if (source is None) != (plan is None):
        _fail("source_and_plan_required_together")
    target_path, receipt_path = _absolute(target), _absolute(receipt)
    if target_path == receipt_path or target_path in receipt_path.parents:
        _fail("receipt_must_be_outside_roots")
    value = _load_receipt(receipt_path)
    if value["state"] != "complete":
        _fail("receipt_incomplete")
    _target_matches(target_path, value)
    if source is not None:
        source_path = _absolute(source)
        _locations(source_path, target_path, receipt_path)
        _source_matches(source_path, validate_plan(plan), value)
    return _summary("verified", value, source_checked=source is not None)


def inventory(source: str | os.PathLike[str]) -> dict[str, Any]:
    """Propose tracked paths for review; no content screening or implicit approval."""
    root = _absolute(source)
    with _directory(root):
        pass
    env = {"PATH": os.environ.get("PATH", os.defpath), "LC_ALL": "C", "LANG": "C",
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_LAZY_FETCH": "1", "GIT_NO_REPLACE_OBJECTS": "1",
           "GIT_TERMINAL_PROMPT": "0"}
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
             "-C", str(root), "ls-files", "--cached", "-z"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            check=False, timeout=30, env=env)
    except (OSError, subprocess.TimeoutExpired):
        _fail("tracked_inventory_failed")
    if result.returncode or len(result.stdout) > MAX_PLAN_BYTES:
        _fail("tracked_inventory_failed")
    try:
        paths = sorted(set(part.decode("utf-8") for part in result.stdout.split(b"\x00") if part))
    except UnicodeError:
        _fail("inventory_requires_utf8_paths")
    plan = validate_plan({"schema": PLAN_SCHEMA,
                          "files": [{"source": path, "target": path} for path in paths]})
    # This also rejects submodules, symlinks, hardlinks and missing worktree files.
    records, _ = _source_observation(root, plan)
    return {"status": "review_required", "execution_authorization": "none",
            "selection": "git-index-tracked-paths-with-current-working-tree-bytes",
            "untracked_included": False, "secret_screened": False,
            "source_observation_sha256": _digest(records), "plan": plan}


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        _fail("invalid_arguments")


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subs = parser.add_subparsers(dest="command", required=True)
    inv = subs.add_parser("inventory")
    inv.add_argument("--source", required=True)
    mat = subs.add_parser("materialize")
    mat.add_argument("--source", required=True)
    mat.add_argument("--plan", required=True)
    mat.add_argument("--target", required=True)
    mat.add_argument("--receipt", required=True)
    ver = subs.add_parser("verify")
    ver.add_argument("--target", required=True)
    ver.add_argument("--receipt", required=True)
    ver.add_argument("--source")
    ver.add_argument("--plan")
    try:
        args = parser.parse_args(argv)
        if args.command == "inventory":
            result = inventory(args.source)
        elif args.command == "materialize":
            result = materialize(args.source, load_plan(args.plan), args.target, args.receipt)
        else:
            result = verify(args.target, args.receipt, args.source, load_plan(args.plan) if args.plan else None)
        print(json.dumps(result, sort_keys=True, ensure_ascii=True))
        return 0
    except ProjectionError as exc:
        print(json.dumps({"status": "error", "code": exc.code}))
        return 2
    except (OSError, UnicodeError, RecursionError, ValueError, OverflowError):
        print(json.dumps({"status": "error", "code": "filesystem_or_encoding_error"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
