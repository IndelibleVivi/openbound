#!/usr/bin/env python3
"""Check portable source structure/links/integrity; this does not test activation."""
import argparse
import hashlib
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', action='store_true')
    options = parser.parse_args()
    required = ['README.md', 'ENGINEERING_DESIGN.md', 'AGENTS.md', 'PROVENANCE.md',
                'LICENSE-STATUS.md', 'docs/current-state.md', 'docs/validation.md', 'evals/ACCEPTANCE.md',
                'skills/openbound/SKILL.md', 'skills/openbound/agents/openai.yaml',
                'skills/openbound/scripts/inspect_public_candidate.py',
                'skills/openbound/scripts/project_candidate.py',
                'skills/openbound/scripts/verify_public_work.py']
    errors = [name + ': missing' for name in required if not (ROOT / name).is_file()]
    skill = (ROOT / 'skills/openbound/SKILL.md').read_text()
    parts = skill.split('---', 2)
    keys = re.findall(r'^([a-z_]+):', parts[1], re.M) if len(parts) == 3 else []
    if set(keys) != {'name', 'description'} or len(skill.splitlines()) >= 500:
        errors.append('root skill contract invalid')
    for path in ROOT.rglob('*.md'):
        if 'dogfood' in path.parts:
            continue
        for url in re.findall(r'\]\(([^\s)]+)(?:\s+"[^"]*")?\)', path.read_text()):
            if '://' in url or url.startswith(('#', 'mailto:', 'sandbox:', '{{')):
                continue
            target = (path.parent / url.split('#')[0]).resolve()
            if not target.exists():
                errors.append(str(path.relative_to(ROOT)) + ': broken local link ' + url)
    metadata = (ROOT / 'skills/openbound/agents/openai.yaml').read_text()
    if 'allow_implicit_invocation: true' not in metadata or '$openbound' not in metadata:
        errors.append('OpenBound host metadata invalid')
    if options.manifest:
        manifest = ROOT / 'MANIFEST.sha256'
        if not manifest.exists():
            errors.append('MANIFEST.sha256 missing')
        else:
            for line in manifest.read_text().splitlines():
                sha, name = line.split('  ', 1)
                path = ROOT / name
                if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                    errors.append(name + ': manifest mismatch')
    for error in errors:
        print(error)
    if errors:
        return 1
    print('Source structure, local links' + (', manifest integrity' if options.manifest else '') + ': PASS. Host activation: not tested.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
