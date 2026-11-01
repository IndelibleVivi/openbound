"""Exercise the source archive boundary in a disposable staged repository."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

SPEC = importlib.util.spec_from_file_location('package_tool', Path(__file__).resolve().parents[1] / 'tools/package.py')
PACKAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGE)


class PackageTests(unittest.TestCase):
    def test_tracked_only_source_preserved_manifest_and_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / 'repo'
            root.mkdir()
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            skill = root / 'skills/openbound/scripts/tool.py'
            skill.parent.mkdir(parents=True)
            skill.write_text('print(1)\n')
            skill.chmod(0o755)
            (root / '.gitignore').write_text('ignored-secret\n')
            (root / 'README.zh-CN.md').write_text('中文入口\n')
            (root / '.env').write_text('secret')
            (root / 'docs/private').mkdir(parents=True)
            (root / 'docs/private/notes.md').write_text('secret')
            (root / 'RAW.md').write_text('secret')
            (root / 'docs/.env.example').write_text('EXAMPLE=placeholder\n')
            subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
            (root / 'untracked-secret').write_text('secret')
            (root / 'ignored-secret').write_text('secret')
            before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            output = base / 'source.zip'
            PACKAGE.package(root, output)
            self.assertEqual(before, {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()})
            with zipfile.ZipFile(output) as archive:
                prefix = 'openbound-engineering-package/'
                names = archive.namelist()
                self.assertFalse(any('secret' in n or n.endswith('/.env') for n in names))
                self.assertIn(prefix + 'skills/openbound/scripts/tool.py', names)
                self.assertIn(prefix + 'docs/.env.example', names)
                self.assertIn(prefix + 'README.zh-CN.md', names)
                self.assertNotIn(prefix + 'docs/private/notes.md', names)
                self.assertNotIn(prefix + 'RAW.md', names)
                self.assertEqual(0o755, (archive.getinfo(prefix + 'skills/openbound/scripts/tool.py').external_attr >> 16) & 0o777)
                for line in archive.read(prefix + 'MANIFEST.sha256').decode().splitlines():
                    sha, name = line.split('  ', 1)
                    self.assertEqual(sha, hashlib.sha256(archive.read(prefix + name)).hexdigest())
            with self.assertRaises(ValueError):
                PACKAGE.package(root, output)
            with self.assertRaises(ValueError):
                PACKAGE.package(root, root / 'inside.zip')
            skill.unlink()
            skill.symlink_to(base / 'outside')
            with self.assertRaises(ValueError):
                PACKAGE.package(root, base / 'linked.zip')
