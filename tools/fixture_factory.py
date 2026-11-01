"""Synthetic, network-free case sources. No real private identifiers or credentials.

Builders create a new directory and refuse an existing destination. Fixtures are
inputs, not evidence that a model followed the skill. Use eval prompts separately.
"""
from pathlib import Path
import json

MIT = """MIT License

Copyright (c) 2026 Synthetic Fixture Author

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def write(root: Path, files: dict[str, str]):
    root.mkdir(parents=True, exist_ok=False)
    for name, content in files.items():
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")


def build_mature(root: Path):
    write(root, {
        "README.md": """# Batch Total

Add decimal amounts from a UTF-8 text file without binary floating point rounding.
This small command-line tool has no third-party dependencies. Python 3.10+.

## Try it

```sh
cd /Users/synthetic_author/work/batch-total
python3 -m batch_total --file examples/numbers.txt
```

The example prints `6.00`. One decimal amount per line; blank lines are ignored.
The `--file` option takes precedence over `BATCH_TOTAL_INPUT`, then a local default.

## Verify

```sh
python3 -m unittest discover -s tests -v
```

Invalid decimal input returns a nonzero exit. This is a small reference utility;
there is no support response-time commitment. Bug reports with a minimal example
and focused pull requests are welcome. Existing behavior and tests guide changes.

## License

MIT; see LICENSE. The examples are synthetic.
""",
        "LICENSE": MIT,
        "batch_total/__init__.py": '"""Decimal totals."""\n',
        "batch_total/core.py": """from decimal import Decimal


def total(lines):
    return sum((Decimal(line.strip()) for line in lines if line.strip()), Decimal('0'))
""",
        "batch_total/__main__.py": """import argparse
from pathlib import Path
import os
from .core import total

parser = argparse.ArgumentParser(description='Add decimal amounts from a UTF-8 file.')
parser.add_argument('--file', default=os.environ.get('BATCH_TOTAL_INPUT', '/Users/synthetic_author/data/numbers.txt'))
args = parser.parse_args()
print(f'{total(Path(args.file).read_text(encoding="utf-8").splitlines()):.2f}')
""",
        "tests/test_total.py": """import unittest
from decimal import Decimal
from batch_total.core import total


class TotalTests(unittest.TestCase):
    def test_decimal_exactness(self):
        self.assertEqual(total(['0.1', '0.2']), Decimal('0.3'))
    def test_empty_and_blank(self):
        self.assertEqual(total(['', '  ']), Decimal('0'))
    def test_negative_and_large(self):
        self.assertEqual(total(['1000000000000.01', '-0.01']), Decimal('1000000000000'))


if __name__ == '__main__':
    unittest.main()
""",
        "examples/numbers.txt": "1\n2\n3\n",
        "pyproject.toml": """[project]
name = "batch-total"
version = "1.0.0"
description = "Sum decimal amounts from text files"
requires-python = ">=3.10"
license = {file = "LICENSE"}

[tool.fixture]
purpose = "synthetic source for OpenBound exercises"
""",
        ".github/workflows/tests.yml": """name: tests
on: [push, pull_request]
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python3 -m unittest discover -s tests -v
      - run: python3 -m batch_total --file examples/numbers.txt
""",
        ".gitignore": "__pycache__/\n*.pyc\n.env\nprivate/\n",
        ".env": "BATCH_TOTAL_INPUT=/Users/synthetic_author/data/numbers.txt\nFIXTURE_TOKEN=ghp_" + "S" * 36 + "\n",
        "private/local.json": json.dumps({"host": "fixture.internal", "mode": "personal"}) + "\n",
    })


PAGER = """from private_ops.client import fetch_batch


def collect(limit=8):
    cursor = None
    result = []
    while True:
        page, cursor = fetch_batch(cursor, limit)
        result.extend(page)
        if cursor is None:
            return result
"""


def build_extraction(root: Path):
    write(root, {
        "README.md": """# Personal operations system

The pagination loop in services/pager.py may be reusable. The service client
depends on my private deployment and cannot be published. Preserve its ordering
and page traversal behavior. A stable cursor is assumed; mutation and retry
semantics have not been established. MIT applies to author-written source.
""",
        "LICENSE": MIT,
        "services/pager.py": PAGER,
        "private_ops/__init__.py": "",
        "private_ops/client.py": """# Synthetic stand-in for an unavailable private service.
def fetch_batch(cursor, limit):
    raise RuntimeError('private client requires author deployment')
""",
        "notes/observations.md": """On one manually constructed private queue of 37 items,
the first query returned only 8. Continuing with the cursor reached all 37.
This was a local observation; the private system is not a general benchmark.
If IDs reorder or a cursor is reused under mutation, this implementation has no
proof of exactly-once processing. Keep that limit visible in a public component.
""",
        "private/operations.json": '{"deployment":"fixture.internal","account":"synthetic-owner"}\n',
    })


def build_research(root: Path):
    write(root, {
        "author-notes.md": """# Queue continuation idea — unfinished

Intent: explain why the size of one query response is not the size of the work.
One private manual simulation contained 37 items with a page limit of 8.
I observed the first response had 8; continuing cursors retrieved all 37.
The original raw trace is not available for publication. No independent test,
prototype, benchmark, production evaluation, or measured speedup exists here.

Hypothesis: an explicit continuation ledger could make interrupted processing
easier to reason about. I have not implemented the proposed ledger. I suspect
it might reduce duplicate handling, but do not know under concurrent mutation.

Mechanism sketch: separate total work, page boundary, processed identity, and
resume cursor. On restart, reconcile identities before accepting continuation.
Question: what survives if cursors expire or item IDs are replaced/reordered?
Counterexample: ID replacement can make a ledger skip new work or repeat old
work even if the cursor is preserved. Do not silently assume stable IDs.

Public goal: a clear research blueprint with a useful falsification plan.
Keep the author's private observation distinct from a new synthetic illustration.
No claim of deployment readiness or performance improvement. No license decision
has been made for these notes; prepare a reviewable candidate, not publication.
""",
        "private-context.md": "Private endpoint: https://fixture.internal/queue\nLocal path: /Users/synthetic_author/lab\n",
    })


def build_maintenance(root: Path):
    write(root, {
        "private-source/core.py": """def normalize(value):
    return value.strip().casefold()
""",
        "private-source/README.md": "Private operations notes; do not overwrite the public reader guide.\n",
        "private-source/private.json": '{"endpoint":"fixture.internal"}\n',
        "public-v1/core.py": """def normalize(value):
    return value.strip().lower()
""",
        "public-v1/README.md": """# Normalize text

This public reader guide is maintained by contributors. Whitespace is trimmed;
Unicode case normalization is the intended behavior. Run `python3 test_core.py`.
The public project accepts focused contributions. The original private system
does not provide a stable API or accept automatic changes from this repository.
""",
        "public-v1/test_core.py": """from core import normalize
assert normalize(' X ') == 'x'
print('ok')
""",
        "public-v1/LICENSE": MIT,
        "relationship.json": json.dumps({
            "schema": "openbound-relationship-example/1", "mode": "selective_projection",
            "public_owned": ["README.md", "test_core.py"],
            "private_owned_exports": {"core.py": "private-source/core.py"},
            "inbound": "review_patch_then_port_approved_logic_in_an_isolated_private_branch",
            "permission": "local_candidates_only",
        }, indent=2) + "\n",
    })


BUILDERS = {"A": build_mature, "B": build_extraction, "C": build_research, "D": build_maintenance}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=BUILDERS)
    parser.add_argument("target", type=Path)
    options = parser.parse_args()
    BUILDERS[options.case](options.target)
    print("Synthetic case created; task prompts live in evals/scenarios.")
