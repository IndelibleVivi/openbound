# Provenance

OpenBound's inspector extends an earlier implementation by the same maintainer. The preserved [baseline](provenance/baseline/inspect_public_candidate.py) is the comparison starting point; the [patch](patches/inspector-baseline.patch) records the changes. Apply it to a temporary tree containing the baseline at `scripts/inspect_public_candidate.py`, then compare with [the active inspector](skills/openbound/scripts/inspect_public_candidate.py). The baseline is a regression fixture, not a second active implementation.

Eleven original test scenarios are retained, with installation-path and stricter output-boundary expectations adjusted. Added regressions cover metadata, shallow history, LFS, coverage, identity and execution boundaries. The implementation is an extension, not a claim of development from scratch or a complete secret-scanning product.

Fixtures are synthetic; their identities, domains, paths and token shapes are test inputs. Deterministic tests, reported Agent trials and host activation are separate evidence layers; see [validation](docs/validation.md). Private execution traces are excluded.

Existing rights remain applicable. Fixture MIT notices apply only to their fixtures; see [license status](LICENSE-STATUS.md). ZIP manifests establish payload bytes, not authorship, rights or safety.
