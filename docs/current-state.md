# Current state

2026-11-01: [IndelibleVivi/openbound](https://github.com/IndelibleVivi/openbound) is public, with independent `main` history and no fork parent. Repository metadata and README content were read anonymously after publication. No Release, package publication or deployment is claimed.

The canonical installation unit is `skills/openbound/`. The earlier integration source is a one-time migration source; no automatic synchronization is promised.

This independent source passed its own local gate on macOS: 117 tests, structure/link checks, relocated CLI checks and Skill validation; see [validation](validation.md). Historical Agent trials, deterministic tests and live host activation are distinct.

CI invokes `tools/validate.py` on Linux/Python 3.10 and macOS/Python 3.13. The first hosted run passed Linux and exposed a macOS test-fixture background-maintenance race; the fixture now disables automatic maintenance and retains the full read-only assertion. Current hosted results are available in [Actions](https://github.com/IndelibleVivi/openbound/actions/workflows/ci.yml).

Downloading the public Skill into a disposable destination produced all 12 expected files with byte parity and working CLI entry points. Global installation, discovery and named-host implicit activation remain unverified.

No general license grant has been made; fixture MIT notices remain fixture-scoped. See [license status](../LICENSE-STATUS.md).
