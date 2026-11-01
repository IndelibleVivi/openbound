#!/usr/bin/env python3
"""Bind reviewed executable checks and inspection to an exact local candidate.

stdlib only, Python 3.10+. This is an evidence runner, NOT a security sandbox or
an authority service. An executable can access everything the host permits.
Outputs are bounded and represented by digests; no command output is printed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time

SCHEMA = "openbound-verification/1"
RECEIPT_SCHEMA = "openbound-verification-receipt/1"
VERSION = "1.0.0"
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TREE_BYTES = 256 * 1024 * 1024
MAX_OUTPUT_BYTES = 1024 * 1024
MAX_RECEIPT_BYTES = 16 * 1024 * 1024
ID = re.compile(r"[a-z][a-z0-9_.-]{0,63}\Z")


class WorkError(Exception):
    """A fixed, non-sensitive diagnostic code."""

    def __init__(self, code: str, exit_code: int = 2):
        super().__init__(code)
        self.code = code
        self.exit_code = exit_code


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _pairs(values):
    result = {}
    for key, value in values:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def decode_json(data: bytes):
    return json.loads(data.decode("utf-8"), object_pairs_hook=_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))


def read_json(path: Path, limit: int = MAX_OUTPUT_BYTES):
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise WorkError("unsafe_or_oversize_json")
        chunks = []
        count = 0
        while True:
            chunk = os.read(descriptor, min(65536, limit + 1 - count))
            if not chunk:
                break
            count += len(chunk)
            if count > limit:
                raise WorkError("unsafe_or_oversize_json")
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise WorkError("json_changed_during_read", 3)
        data = b"".join(chunks)
        return decode_json(data), digest(data)
    except WorkError:
        raise
    except (OSError, ValueError, UnicodeError, RecursionError):
        raise WorkError("unreadable_or_invalid_json") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _outside(path: Path, candidate: Path):
    try:
        path.resolve().relative_to(candidate.resolve())
    except ValueError:
        return
    raise WorkError("private_state_inside_candidate")


def snapshot_tree(root: Path) -> dict:
    """Hash all files and empty directories, including .git if present.

    Symlinks, hardlinked regular files and special nodes are deliberately refused.
    This detects ordinary drift, not adversarial concurrent mutation/ABA attacks.
    """
    if root.is_symlink() or not root.is_dir():
        raise WorkError("candidate_not_plain_directory")
    entries = []
    total = 0
    try:
        for current, dirs, files in os.walk(root, followlinks=False):
            dirs.sort()
            files.sort()
            for name in dirs + files:
                path = Path(current) / name
                info = path.lstat()
                rel = path.relative_to(root).as_posix()
                if stat.S_ISLNK(info.st_mode):
                    raise WorkError("candidate_contains_symlink")
                mode = stat.S_IMODE(info.st_mode)
                if stat.S_ISDIR(info.st_mode):
                    entries.append({"path": rel, "kind": "directory", "mode": mode})
                    continue
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise WorkError("candidate_contains_nonordinary_file")
                total += info.st_size
                if info.st_size > MAX_FILE_BYTES or total > MAX_TREE_BYTES:
                    raise WorkError("candidate_exceeds_verification_budget")
                data = path.read_bytes()
                after = path.lstat()
                before_key = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
                              info.st_ctime_ns, info.st_mode)
                after_key = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
                             after.st_ctime_ns, after.st_mode)
                if before_key != after_key or len(data) != info.st_size:
                    raise WorkError("candidate_changed_during_read", 3)
                entries.append({"path": rel, "kind": "file", "mode": mode,
                                "bytes": len(data), "sha256": digest(data)})
    except WorkError:
        raise
    except OSError:
        raise WorkError("candidate_unreadable") from None
    entries.sort(key=lambda x: x["path"])
    return {"scheme": "openbound-tree/1", "sha256": digest(canonical(entries)),
            "files": sum(e["kind"] == "file" for e in entries),
            "bytes": total, "entries": entries}


def tool_identity() -> dict:
    here = Path(__file__).resolve()
    scanner = here.with_name("inspect_public_candidate.py")
    try:
        return {"version": VERSION, "runner_sha256": digest(here.read_bytes()),
                "scanner_sha256": digest(scanner.read_bytes())}
    except OSError:
        raise WorkError("inspector_unavailable") from None


def load_contract(path: Path) -> tuple[dict, str]:
    data, sha = read_json(path)
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise WorkError("invalid_contract_schema")
    if set(data) - {"schema", "checks", "witnesses", "inspection", "dependencies"}:
        raise WorkError("unknown_contract_field")
    dependencies = data.get("dependencies", [])
    if not isinstance(dependencies, list) or len(dependencies) > 100 or any(
        not isinstance(p, str) or not os.path.isabs(p) or "\0" in p or len(p) > 8192 for p in dependencies
    ):
        raise WorkError("invalid_dependency_files")
    checks = data.get("checks", [])
    witnesses = data.get("witnesses", [])
    if not isinstance(checks, list) or len(checks) > 50 or not isinstance(witnesses, list):
        raise WorkError("invalid_check_list")
    ids = set()
    for check in checks:
        if not isinstance(check, dict) or set(check) - {
            "id", "argv", "expected_exit", "timeout_seconds", "stdout_json_equals"
        }:
            raise WorkError("invalid_check")
        cid = check.get("id")
        if not isinstance(cid, str) or not ID.fullmatch(cid) or cid in ids:
            raise WorkError("invalid_or_duplicate_check_id")
        ids.add(cid)
        argv = check.get("argv")
        if not isinstance(argv, list) or not argv or len(argv) > 100 or any(
            not isinstance(a, str) or not a or "\0" in a or len(a) > 8192 for a in argv
        ):
            raise WorkError("invalid_command_arguments")
        timeout = check.get("timeout_seconds", 60)
        expected = check.get("expected_exit", 0)
        if type(timeout) not in (int, float) or not 0.1 <= timeout <= 600:
            raise WorkError("invalid_timeout")
        if type(expected) is not int or not 0 <= expected <= 255:
            raise WorkError("invalid_expected_exit")
    witness_ids = set()
    for witness in witnesses:
        if not isinstance(witness, dict) or set(witness) != {
            "id", "positive", "negative", "relation"
        }:
            raise WorkError("invalid_witness")
        wid = witness["id"]
        if not isinstance(wid, str) or not ID.fullmatch(wid) or wid in witness_ids:
            raise WorkError("invalid_or_duplicate_witness_id")
        witness_ids.add(wid)
        if witness["positive"] not in ids or witness["negative"] not in ids or (
            witness["positive"] == witness["negative"]
        ):
            raise WorkError("unbound_witness")
        if witness["relation"] not in {"equal_json", "different_json"}:
            raise WorkError("invalid_witness_relation")
    inspection = data.get("inspection", {})
    if not isinstance(inspection, dict) or set(inspection) - {
        "candidate_mode", "candidate_ref", "history_ref", "max_bytes"
    }:
        raise WorkError("invalid_inspection")
    if inspection.get("candidate_mode", "both") not in {
        "working-tree", "index", "both", "none"
    }:
        raise WorkError("invalid_inspection_mode")
    for ref in ("candidate_ref", "history_ref"):
        if ref in inspection and (not isinstance(inspection[ref], str) or not inspection[ref]):
            raise WorkError("invalid_inspection_ref")
    size = inspection.get("max_bytes", 2_000_000)
    if type(size) is not int or not 1 <= size <= MAX_FILE_BYTES:
        raise WorkError("invalid_inspection_budget")
    return data, sha


def execution_identity(contract: dict, candidate: Path) -> dict:
    """Bind direct programs, runtime and explicit external files, not an entire OS."""
    records = []
    def observe(path, role):
        resolved = Path(path).resolve()
        try:
            info = resolved.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES:
                raise WorkError("execution_dependency_unavailable")
            data = resolved.read_bytes()
            after = resolved.stat()
            if (info.st_size, info.st_mtime_ns, info.st_ctime_ns) != (
                    after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise WorkError("execution_dependency_changed", 3)
            records.append({"role": role, "path_sha256": digest(str(resolved).encode()),
                            "sha256": digest(data), "bytes": len(data),
                            "mode": stat.S_IMODE(info.st_mode)})
        except WorkError:
            raise
        except OSError:
            raise WorkError("execution_dependency_unavailable") from None
    observe(sys.executable, "runner-python")
    inspection_git = shutil.which("git")
    if inspection_git:
        observe(inspection_git, "inspection-git")
    else:
        records.append({"role": "inspection-git", "available": False})
    for command in contract.get("checks", []):
        executable = command["argv"][0]
        if executable == "{python}":
            resolved = sys.executable
        elif "{candidate}" in executable:
            resolved = executable.replace("{candidate}", str(candidate))
        elif "/" in executable:
            resolved = executable if os.path.isabs(executable) else str(candidate / executable)
        else:
            resolved = shutil.which(executable, path=os.defpath)
        if not resolved:
            # Preserve a real launch-failure observation instead of calling an
            # absent executable a successful/usable check.
            records.append({"role": command["id"] + ":executable", "available": False})
        else:
            observe(resolved, command["id"] + ":executable")
        for index, arg in enumerate(command["argv"][1:], 1):
            if os.path.isabs(arg) and Path(arg).is_file():
                observe(arg, command["id"] + ":absolute-argument:" + str(index))
    for index, path in enumerate(contract.get("dependencies", [])):
        observe(path, "declared-dependency:" + str(index))
    return {"records": records, "python_version": sys.version,
            "platform": sys.platform,
            "scope": "direct-executables-runtime-absolute-file-arguments-declared-dependencies",
            "ambient_packages_services_and_hardware": "not_attested"}


def validate_git_boundary(candidate: Path):
    control = candidate / ".git"
    if not control.exists() and not control.is_symlink():
        return
    if not control.is_dir() or control.is_symlink():
        raise WorkError("indirect_git_worktree_requires_explicit_inspection")
    for path in (control / "commondir", control / "objects/info/alternates",
                 control / "objects/info/http-alternates"):
        if path.exists() or path.is_symlink():
            raise WorkError("external_git_storage_requires_explicit_inspection")
    git = shutil.which("git")
    if not git:
        raise WorkError("git_unavailable")
    env = {"PATH": os.defpath, "HOME": os.devnull, "LC_ALL": "C", "LANG": "C",
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_LAZY_FETCH": "1",
           "GIT_TERMINAL_PROMPT": "0", "GIT_ALLOW_PROTOCOL": ""}
    try:
        result = subprocess.run([git, "-C", str(candidate), "rev-parse", "--show-toplevel", "--absolute-git-dir"],
                                env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=10)
        lines = result.stdout.decode("utf-8").splitlines()
        if (result.returncode or len(lines) != 2 or Path(lines[0]).resolve() != candidate.resolve()
                or Path(lines[1]).resolve() != control.resolve()):
            raise WorkError("git_root_outside_candidate")
    except WorkError:
        raise
    except (OSError, UnicodeError, subprocess.SubprocessError):
        raise WorkError("git_boundary_unverifiable") from None


def _stop(process: subprocess.Popen):
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        elif process.poll() is None:
            process.kill()
    except ProcessLookupError:
        pass


def run_command(check: dict, work: Path, temp: Path) -> dict:
    argv = [sys.executable if a == "{python}" else a.replace("{candidate}", str(work))
            for a in check["argv"]]
    home = temp / "home"
    home.mkdir()
    env = {"PATH": os.defpath, "HOME": str(home), "TMPDIR": str(temp),
           "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_TERMINAL_PROMPT": "0", "GIT_NO_LAZY_FETCH": "1"}
    result = {"id": check["id"], "argv_sha256": digest(canonical(check["argv"])),
              "expected_exit": check.get("expected_exit", 0), "exit_code": None,
              "timed_out": False, "output_limited": False, "launch_failed": False}
    streams = {"stdout": bytearray(), "stderr": bytearray()}
    begin = time.monotonic()
    process = None
    try:
        process = subprocess.Popen(argv, cwd=work, env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   shell=False, start_new_session=(os.name == "posix"))
        with selectors.DefaultSelector() as select:
            select.register(process.stdout, selectors.EVENT_READ, "stdout")
            select.register(process.stderr, selectors.EVENT_READ, "stderr")
            deadline = begin + check.get("timeout_seconds", 60)
            while select.get_map():
                if time.monotonic() >= deadline:
                    result["timed_out"] = True
                    _stop(process)
                    break
                for key, _ in select.select(min(0.1, max(0, deadline - time.monotonic()))):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        select.unregister(key.fileobj)
                    elif sum(map(len, streams.values())) + len(chunk) > MAX_OUTPUT_BYTES:
                        result["output_limited"] = True
                        _stop(process)
                        break
                    else:
                        streams[key.data].extend(chunk)
                if result["output_limited"]:
                    break
        if process.poll() is None:
            remaining = max(0.01, deadline - time.monotonic())
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                result["timed_out"] = True
                _stop(process)
        process.wait(timeout=5)
        result["exit_code"] = process.returncode
    except OSError:
        result["launch_failed"] = True
    finally:
        if process is not None:
            _stop(process)
            for stream in (process.stdout, process.stderr):
                if stream:
                    stream.close()
    result["elapsed_seconds"] = round(time.monotonic() - begin, 6)
    for stream, value in streams.items():
        result[stream] = {"sha256": digest(bytes(value)), "captured_bytes": len(value),
                          "complete": not result["output_limited"] and not result["timed_out"]}
    parsed = None
    json_ok = False
    if result["stdout"]["complete"]:
        try:
            parsed = decode_json(bytes(streams["stdout"]))
            result["stdout_json_sha256"] = digest(canonical(parsed))
            json_ok = True
        except (ValueError, UnicodeError):
            pass
    result["json_assertion"] = None
    if "stdout_json_equals" in check:
        result["json_assertion"] = json_ok and canonical(parsed) == canonical(check["stdout_json_equals"])
    result["passed"] = (not any(result[k] for k in ("launch_failed", "timed_out", "output_limited"))
                        and result["exit_code"] == result["expected_exit"]
                        and result["json_assertion"] is not False)
    return result


def _invoke_inspection(candidate: Path, settings: dict) -> dict:
    path = Path(__file__).resolve().with_name("inspect_public_candidate.py")
    spec = importlib.util.spec_from_file_location("openbound_inspector", path)
    if spec is None or spec.loader is None:
        raise WorkError("inspector_unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        return module.inspect(candidate, history_ref=settings.get("history_ref"),
                              candidate_ref=settings.get("candidate_ref"),
                              candidate_mode=settings.get("candidate_mode", "both"),
                              max_bytes=settings.get("max_bytes", 2_000_000))
    except Exception:
        raise WorkError("inspection_failed") from None
    finally:
        sys.modules.pop(spec.name, None)


def run_inspection(candidate: Path, settings: dict) -> dict:
    """Reuse the Git inspector, adapting an unversioned candidate without editing it."""
    control = candidate / ".git"
    validate_git_boundary(candidate)
    if control.is_dir() and not control.is_symlink():
        return _invoke_inspection(candidate, settings)
    if control.exists() or control.is_symlink():
        raise WorkError("indirect_git_worktree_requires_explicit_inspection")
    if settings.get("history_ref") or settings.get("candidate_ref"):
        raise WorkError("unversioned_candidate_has_no_history_or_ref")
    with tempfile.TemporaryDirectory(prefix="openbound-inspection-") as directory:
        temp = Path(directory)
        work = temp / "candidate"
        template = temp / "empty-template"
        template.mkdir()
        try:
            shutil.copytree(candidate, work)
            env = {"PATH": os.defpath, "HOME": str(temp),
                   "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                   "GIT_TERMINAL_PROMPT": "0", "GIT_NO_LAZY_FETCH": "1",
                   "GIT_CONFIG_COUNT": "0", "GIT_ALLOW_PROTOCOL": "",
                   "LC_ALL": "C", "LANG": "C"}
            git = shutil.which("git")
            if not git:
                raise WorkError("git_unavailable")
            for arguments in (("init", "--quiet", "--template=" + str(template)),
                              ("-c", "core.hooksPath=" + os.devnull, "add", "--force", "--all", "--")):
                proc = subprocess.run([git, "-C", str(work), *arguments], env=env,
                                      stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, timeout=60, check=False)
                if proc.returncode:
                    raise WorkError("disposable_inspection_index_failed")
            result = _invoke_inspection(work, settings)
            result["directory_adapter"] = {
                "kind": "disposable_git_index_of_all_candidate_files",
                "original_git_history": "absent", "candidate_modified": False,
                "ignored_files_included": True,
                "note": "Temporary index identity does not claim original repository history coverage."}
            return result
        except WorkError:
            raise
        except (OSError, subprocess.SubprocessError):
            raise WorkError("disposable_inspection_index_failed") from None


def summarize(receipt: dict, fresh: bool, reused: bool = False) -> dict:
    checks = receipt["checks"]
    witnesses = receipt["witnesses"]
    passed = all(c["passed"] for c in checks) and all(w["passed"] for w in witnesses)
    inspection = receipt["inspection"]
    return {"schema": "openbound-verification-summary/1", "fresh": fresh,
            "reused": reused, "candidate_sha256": receipt["candidate"]["sha256"],
            "executed_checks": len(checks), "failed_checks": sum(not c["passed"] for c in checks),
            "failed_witnesses": sum(not w["passed"] for w in witnesses),
            "all_requested_checks_passed": passed if checks else None,
            "scanner_findings": len(inspection.get("findings", [])),
            "scanner_selected_surfaces_exhausted": inspection.get("scan_complete", False),
            "publication_ready": False,
            "freshness_scope": "candidate-contract-engines-direct-executables-declared-files",
            "ambient_environment": "not_attested",
            "claim": "observed_local_checks_only" if fresh else "stale_evidence"}


def validate_receipt(data: dict, contract: dict):
    try:
        if data["schema"] != RECEIPT_SCHEMA or data["publication_ready"] is not False:
            raise ValueError()
        if data["contract_sha256"] is None or data["candidate_unchanged"] is not True:
            raise ValueError()
        checks = data["checks"]
        requested = contract.get("checks", [])
        if len(checks) != len(requested):
            raise ValueError()
        for observed, expected in zip(checks, requested):
            if observed["id"] != expected["id"] or observed["argv_sha256"] != digest(canonical(expected["argv"])):
                raise ValueError()
            if observed["expected_exit"] != expected.get("expected_exit", 0):
                raise ValueError()
            correct = (not any(observed[k] for k in ("launch_failed", "timed_out", "output_limited"))
                       and observed["exit_code"] == observed["expected_exit"]
                       and observed["json_assertion"] is not False)
            if observed["passed"] is not correct:
                raise ValueError()
            if "stdout_json_equals" in expected and observed["json_assertion"] is None:
                raise ValueError()
        witnesses = make_witnesses(contract, checks)
        if data["witnesses"] != witnesses:
            raise ValueError()
        if digest(canonical(data["inspection"])) != data["inspection_sha256"]:
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise WorkError("inconsistent_receipt") from None


def make_witnesses(contract: dict, checks: list) -> list:
    indexed = {c["id"]: c for c in checks}
    results = []
    for witness in contract.get("witnesses", []):
        a, b = indexed[witness["positive"]], indexed[witness["negative"]]
        usable = a["passed"] and b["passed"] and all("stdout_json_sha256" in c for c in (a, b))
        equal = usable and a["stdout_json_sha256"] == b["stdout_json_sha256"]
        passed = bool(usable and (equal if witness["relation"] == "equal_json" else not equal))
        results.append({**witness, "passed": passed,
                        "claim": "observed_json_relation_only"})
    return results


def status(candidate: Path, contract_path: Path, receipt_path: Path) -> dict:
    _outside(contract_path, candidate)
    _outside(receipt_path, candidate)
    contract, contract_sha = load_contract(contract_path)
    receipt, _ = read_json(receipt_path, MAX_RECEIPT_BYTES)
    validate_receipt(receipt, contract)
    fresh = (receipt["candidate"]["sha256"] == snapshot_tree(candidate)["sha256"]
             and receipt["contract_sha256"] == contract_sha
             and receipt["tools"] == tool_identity()
             and receipt.get("execution_identity") == execution_identity(contract, candidate))
    return summarize(receipt, fresh)


def check(candidate: Path, contract_path: Path, receipt_path: Path,
          execute_reviewed: bool = False) -> dict:
    _outside(contract_path, candidate)
    _outside(receipt_path, candidate)
    contract, contract_sha = load_contract(contract_path)
    if receipt_path.exists() or receipt_path.is_symlink():
        previous = status(candidate, contract_path, receipt_path)
        if not previous["fresh"]:
            raise WorkError("receipt_stale_choose_new_path", 3)
        previous["reused"] = True
        return previous
    if contract.get("checks") and not execute_reviewed:
        raise WorkError("reviewed_execution_flag_required", 4)
    if os.name != "posix" and contract.get("checks"):
        raise WorkError("command_runner_requires_posix")
    candidate = candidate.resolve()
    validate_git_boundary(candidate)
    before = snapshot_tree(candidate)
    tools_before = tool_identity()
    execution_before = execution_identity(contract, candidate)
    results = []
    for command in contract.get("checks", []):
        with tempfile.TemporaryDirectory(prefix="openbound-check-") as directory:
            temp = Path(directory)
            work = temp / "candidate"
            try:
                shutil.copytree(candidate, work, symlinks=False)
            except OSError:
                raise WorkError("verification_copy_failed") from None
            if snapshot_tree(work)["sha256"] != before["sha256"]:
                raise WorkError("verification_copy_mismatch", 3)
            validate_git_boundary(work)
            observed = run_command(command, work, temp)
            observed["input_sha256"] = before["sha256"]
            results.append(observed)
    inspection = run_inspection(candidate, contract.get("inspection", {}))
    if snapshot_tree(candidate)["sha256"] != before["sha256"]:
        raise WorkError("candidate_changed_during_verification", 3)
    if (tool_identity() != tools_before or load_contract(contract_path)[1] != contract_sha
            or execution_identity(contract, candidate) != execution_before):
        raise WorkError("verification_inputs_changed", 3)
    receipt = {"schema": RECEIPT_SCHEMA, "candidate": before, "tools": tools_before,
               "execution_identity": execution_before,
               "contract_sha256": contract_sha, "candidate_unchanged": True,
               "execution": {"workspace": "fresh_disposable_copy_per_check",
                             "environment": "minimal_no_inherited_credentials",
                             "os_sandbox": False, "network_restricted": False},
               "checks": results, "witnesses": make_witnesses(contract, results),
               "inspection": inspection, "inspection_sha256": digest(canonical(inspection)),
               "publication_ready": False}
    validate_receipt(receipt, contract)
    serialized = (json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("ascii")
    if len(serialized) > MAX_RECEIPT_BYTES:
        raise WorkError("receipt_exceeds_budget")
    try:
        # O_EXCL avoids clobbering old evidence. A partial write is invalid JSON and
        # fails closed; retain it for diagnosis and choose a new receipt path.
        descriptor = os.open(receipt_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(serialized.decode("ascii"))
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        raise WorkError("receipt_already_exists") from None
    except OSError:
        raise WorkError("receipt_write_failed") from None
    return summarize(receipt, True)


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise WorkError("invalid_arguments")


def main(argv=None) -> int:
    parser = SafeParser(description=__doc__)
    parser.add_argument("command", choices=("check", "status"))
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--execute-reviewed", action="store_true",
                        help="Guard only: the operator reviewed execution; this grants no authority.")
    try:
        args = parser.parse_args(argv)
        result = (check(args.candidate, args.contract, args.receipt, args.execute_reviewed)
                  if args.command == "check" else status(args.candidate, args.contract, args.receipt))
        print(json.dumps(result, sort_keys=True))
        if not result["fresh"]:
            return 3
        return 1 if result["all_requested_checks_passed"] is False else 0
    except WorkError as error:
        print(json.dumps({"error": error.code, "publication_ready": False}))
        return error.exit_code
    except Exception:
        # Do not leak raw exceptions/paths/subprocess text through the public CLI.
        print(json.dumps({"error": "unexpected_local_failure", "publication_ready": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
