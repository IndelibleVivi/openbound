#!/usr/bin/env python3
"""Install one canonical Skill and inspect local prerequisites without launching a model.

This is a source-maintenance helper, not a host adapter or permission service.
It never edits host settings, trust databases, credentials or existing installs.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/openbound"
spec = importlib.util.spec_from_file_location(
    "openbound_installer_projector", SKILL / "scripts/project_candidate.py")
p = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = p
spec.loader.exec_module(p)

# Installation hints only. These are not launch commands or claims of activation.
# Shared .agents paths minimize duplicate bodies; Claude has its native location.
HOSTS = {
    "codex": {"project": ".agents/skills", "user": ".agents/skills",
              "alternatives": (".codex/skills",), "executables": ("codex",)},
    "claude-code": {"project": ".claude/skills", "user": ".claude/skills",
                    "alternatives": (), "executables": ("claude",)},
    "opencode": {"project": ".agents/skills", "user": ".agents/skills",
                 "alternatives": (".opencode/skills", ".claude/skills", ".config/opencode/skills"),
                 "executables": ("opencode",)},
    "pi": {"project": ".agents/skills", "user": ".agents/skills",
           "alternatives": (".pi/skills", ".pi/agent/skills"), "executables": ("pi",)},
    "gemini-cli": {"project": ".agents/skills", "user": ".agents/skills",
                   "alternatives": (".gemini/skills",), "executables": ("gemini",)},
    "cursor": {"project": ".agents/skills", "user": ".agents/skills",
               "alternatives": (".cursor/skills", ".claude/skills", ".codex/skills"),
               "executables": ("cursor-agent", "agent")},
}
SCHEMA = "openbound-host-support/1"
REQUIRED = {"SKILL.md", "scripts/project_candidate.py",
            "scripts/inspect_public_candidate.py", "scripts/verify_public_work.py"}


def unit(path):
    """Use the canonical projector's bounded, no-follow tree observation."""
    path = p._absolute(path)
    tree = p._observe_tree(path)
    records = tree["files"]
    names = {entry["path"] for entry in records}
    if not REQUIRED <= names:
        raise ValueError("incomplete_skill_unit")
    if any(Path(name).parts[0] not in {"SKILL.md", "references", "scripts", "agents", "assets"}
           or "__pycache__" in Path(name).parts or name.endswith((".pyc", ".pyo"))
           for name in names):
        raise ValueError("unexpected_skill_payload")
    body = p._read_private(path / "SKILL.md", p.MAX_FILE_BYTES).decode("utf-8")
    parts = body.split("---", 2)
    if (len(parts) != 3 or parts[0].strip() or
            not re.search(r"^name:\s*openbound\s*$", parts[1], re.M) or
            not re.search(r"^description:\s*\S", parts[1], re.M)):
        raise ValueError("invalid_skill_frontmatter")
    # The installed payload must include every relative root-method link.
    for link in re.findall(r"\]\(([^\s)#]+)(?:#[^\s)]*)?\)", body):
        if "://" not in link and not link.startswith("#") and link not in names:
            raise ValueError("missing_skill_resource")
    expected_dirs = {str(parent) for name in names for parent in Path(name).parents
                     if str(parent) != "."}
    if {entry["path"] for entry in tree["directories"]} != expected_dirs:
        raise ValueError("empty_or_unexpected_skill_directory")
    return {"sha256": p._digest(records), "file_count": len(records), "files": records,
            "root_mode": tree["root_mode"], "directories": tree["directories"]}


def installed_matches(installed, source):
    # The projector normalizes installed directories; do not demand that the
    # author's source directories already have those modes or silently chmod.
    return (installed["files"] == source["files"] and installed["root_mode"] == p.ROOT_MODE
            and all(item["mode"] == p.DIR_MODE for item in installed["directories"]))


def destination(host, scope, root, override=None):
    root = p._absolute(root)
    with p._directory(root):
        pass
    target = p._absolute(override) if override else root / HOSTS[host][scope] / "openbound"
    if target.name != "openbound":
        raise ValueError("destination_must_be_named_openbound")
    return root, target


def ensure_parents(root, target):
    """Create discovery directories under an explicit existing root, preserving modes."""
    if root not in target.parents:
        # Custom destinations may be elsewhere, but their parent must already exist.
        with p._directory(target.parent):
            pass
        return
    with p._directory(root) as fd:
        current = os.dup(fd)
        try:
            for part in target.parent.relative_to(root).parts:
                try:
                    os.mkdir(part, 0o755, dir_fd=current)
                except FileExistsError:
                    pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | p._platform_flags(), dir_fd=current)
                os.close(current)
                current = child
        finally:
            os.close(current)


def install(host, scope, root, source=SKILL, override=None, dry_run=False):
    source = p._absolute(source)
    root, target = destination(host, scope, root, override)
    if source == target or source in target.parents or target in source.parents:
        raise ValueError("source_target_overlap")
    observed = unit(source)
    base = {"schema": SCHEMA, "host": host, "scope": scope, "source": str(source),
            "destination": str(target), "payload_sha256": observed["sha256"],
            "file_count": observed["file_count"], "native_discovery": "not_run",
            "activation": "not_run", "end_to_end": "not_run"}
    if os.path.lexists(target):
        if not installed_matches(unit(target), observed):
            raise ValueError("installation_differs_preserve_and_review")
        return dict(base, status="unchanged")
    if dry_run:
        return dict(base, status="planned")
    ensure_parents(root, target)
    plan = {"schema": p.PLAN_SCHEMA,
            "files": [{"source": x["path"], "target": x["path"]} for x in observed["files"]]}
    # Receipts stay outside discovery. A fully matching interrupted install is
    # recoverable through the idempotent byte/mode comparison above.
    with tempfile.TemporaryDirectory(prefix="openbound-install-",
                                     dir=Path(tempfile.gettempdir()).resolve()) as directory:
        p.materialize(source, plan, target, Path(directory) / "projection.json")
    if unit(source) != observed or not installed_matches(unit(target), observed):
        raise ValueError("installation_or_source_changed_review_target")
    return dict(base, status="installed")


def doctor(host, scope, root, source=SKILL, override=None):
    root, target = destination(host, scope, root, override)
    observed = unit(source)
    paths = {target, root / HOSTS[host][scope] / "openbound"}
    paths.update(root / name / "openbound" for name in HOSTS[host]["alternatives"])
    copies = []
    for path in sorted(paths):
        if not os.path.lexists(path):
            continue
        try:
            installed = unit(path)
            copies.append({"path": str(path), "state": "matches_source" if installed_matches(installed, observed)
                           else "differs", "payload_sha256": installed["sha256"]})
        except (ValueError, OSError, p.ProjectionError) as error:
            copies.append({"path": str(path), "state": "invalid_or_unreadable",
                           "code": getattr(error, "code", "invalid_skill_unit")})
    selected = next((copy for copy in copies if copy["path"] == str(target)), None)
    executables = [{"name": name, "path": shutil.which(name), "identity": "not_verified"}
                   for name in HOSTS[host]["executables"]]
    git = shutil.which("git")
    return {"schema": SCHEMA, "host": host, "scope": scope,
            "source_payload_sha256": observed["sha256"], "file_count": observed["file_count"],
            "destination": str(target), "installation": selected["state"] if selected else "missing",
            "copies": copies, "multiple_locations": len(copies) > 1,
            "inspection_scope": "supplied_root_only; parent, other user, admin, remote and configured locations not scanned",
            "prerequisites": {"python": sys.version.split()[0], "python_supported": sys.version_info >= (3, 10),
                              "platform": sys.platform, "posix": os.name == "posix", "git_path": git},
            "executable_candidates": executables,
            "native_discovery": "not_run", "explicit_activation": "not_run",
            "implicit_activation": "not_run", "task_completion": "not_run",
            "permissions": "unknown", "claims": {"host_compatible": None, "publication_ready": False},
            "next": "Use the documented native inventory/invocation in a fresh fixture session; retain version and trace."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("install", "doctor"))
    parser.add_argument("--host", required=True, choices=HOSTS)
    parser.add_argument("--scope", choices=("project", "user"), default="project")
    parser.add_argument("--root", required=True, type=Path,
                        help="Existing project root, or explicit user root for --scope user; no implicit HOME writes")
    parser.add_argument("--source", type=Path, default=SKILL)
    parser.add_argument("--destination", type=Path, help="Override location; directory must be named openbound")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor" and args.dry_run:
            raise ValueError("doctor_is_already_read_only")
        kwargs = dict(host=args.host, scope=args.scope, root=args.root, source=args.source,
                      override=args.destination)
        result = install(**kwargs, dry_run=args.dry_run) if args.command == "install" else doctor(**kwargs)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (p.ProjectionError, ValueError, OSError) as error:
        print(json.dumps({"schema": SCHEMA, "status": "error",
                          "code": error.code if isinstance(error, p.ProjectionError) else
                          str(error) if isinstance(error, ValueError) else "filesystem_error"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
