# Current state

2026-11-01: [IndelibleVivi/openbound](https://github.com/IndelibleVivi/openbound) is public, with independent `main` history and no fork parent. Repository metadata and README content were read anonymously after publication. No Release, package publication or deployment is claimed.

The canonical installation unit is `skills/openbound/`. OpenBound is maintained independently in this repository.

This independent source passed its own local gate on macOS: 117 tests, structure/link checks, relocated CLI checks and Skill validation; see [validation](validation.md). Historical Agent trials, deterministic tests and live host activation are distinct.

Hosted CI passed `tools/validate.py` on Linux/Python 3.10 and macOS/Python 3.13 for implementation commit `9cc9be5`: [verified run](https://github.com/IndelibleVivi/openbound/actions/runs/41275709057). Current results are available in [Actions](https://github.com/IndelibleVivi/openbound/actions/workflows/ci.yml).

Downloading the public Skill into a disposable destination produced all 12 expected files with byte parity and working CLI entry points. Global installation, discovery and named-host implicit activation remain unverified.

No general license grant has been made; fixture MIT notices remain fixture-scoped. See [license status](../LICENSE-STATUS.md).
