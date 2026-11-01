#!/usr/bin/env python3
"""Provider-neutral source and isolated installed-unit validation."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    # Resolve the system temporary root: macOS aliases must not weaken product guards.
    base = Path(tempfile.gettempdir()).resolve()
    with tempfile.TemporaryDirectory(prefix='openbound-validation-', dir=base) as directory:
        temp = Path(directory)
        if temp == ROOT or ROOT in temp.parents:
            raise RuntimeError('Validation temporary root must be outside the repository')
        env = dict(os.environ, TMPDIR=str(temp), PYTHONDONTWRITEBYTECODE='1')
        commands = [[sys.executable, '-B', str(ROOT / 'tools/check_package.py')],
                    [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-v']]
        installed = temp / 'installed' / 'openbound'
        shutil.copytree(ROOT / 'skills/openbound', installed)
        for script in ('project_candidate.py', 'inspect_public_candidate.py', 'verify_public_work.py'):
            commands.append([sys.executable, '-B', str(installed / 'scripts' / script), '--help'])
        for index, command in enumerate(commands):
            result = subprocess.run(command, cwd=ROOT if index < 2 else temp, env=env)
            if result.returncode:
                return result.returncode
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
