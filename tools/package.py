#!/usr/bin/env python3
"""Archive only reviewed Git tracked files; write the manifest inside the ZIP."""
import argparse
import hashlib
from pathlib import Path
import stat
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'.git', '__pycache__', '.pytest_cache', '.ds_store', 'dogfood',
            'raw', 'traces', 'continuity', 'private', '.private', 'validation'}
SOURCE_FILES = {'.gitignore', '.gitattributes', 'README.md', 'README.zh-CN.md', 'AGENTS.md', 'ENGINEERING_DESIGN.md',
                'PROVENANCE.md', 'LICENSE-STATUS.md'}
SOURCE_DIRS = {'skills', 'tests', 'tools', 'examples', 'evals', 'docs', '.github',
               'patches', 'provenance'}


def package(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output == root or root in output.parents:
        raise ValueError('Write the archive outside the source package.')
    if output.exists():
        raise ValueError('Output exists; choose a new path.')
    raw = subprocess.check_output(['git', '-C', str(root), 'ls-files', '--cached', '-z'])
    payload = []
    for name in sorted(set(raw.decode('utf-8').split('\0')) - {''}):
        rel = Path(name)
        if rel.is_absolute() or '..' in rel.parts:
            raise ValueError('Unsafe tracked path.')
        if rel.parts[0] not in SOURCE_DIRS and name not in SOURCE_FILES:
            continue
        if ({part.casefold() for part in rel.parts} & EXCLUDED or
                (rel.name.startswith('.env') and rel.name != '.env.example') or
                rel.suffix in {'.pyc', '.pyo'} or rel.name in {'MANIFEST.sha256', 'CODEX_HANDOFF.md'} or
                any(token in rel.name.casefold() for token in ('handoff', 'continuity', '.trace'))):
            continue
        path = root / rel
        if any(p.is_symlink() for p in [path, *path.parents] if p != root.parent):
            raise ValueError('Source package contains a symlink.')
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('Tracked payload must be ordinary files.')
        payload.append((name, path.read_bytes(), stat.S_IMODE(info.st_mode)))
    manifest = ''.join(hashlib.sha256(data).hexdigest() + '  ' + name + '\n'
                       for name, data, _ in payload).encode()
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data, mode in payload + [('MANIFEST.sha256', manifest, 0o644)]:
            item = zipfile.ZipInfo('openbound-engineering-package/' + name)
            item.create_system = 3
            item.external_attr = (stat.S_IFREG | mode) << 16
            item.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(item, data)
    return len(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        count = package(ROOT, args.output)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.error(str(error))
    print(f'Created archive with {count} source files and an internal byte manifest.')


if __name__ == '__main__':
    main()
