# Provenance and derivation

OpenBound evolves Public Repo Craft's private-to-public preparation workflow. This independent repository is the canonical OpenBound source; the earlier integration source was a one-time migration input, not an ongoing synchronization upstream.

The inspector directly derives from the Public Repo Craft scanner. The preserved [baseline scanner](provenance/baseline/inspect_public_candidate.py) and [change patch](patches/public-repo-craft-inspector.patch) make the derivation locally inspectable without access to private history. Apply the patch to a temporary tree containing the baseline at `scripts/inspect_public_candidate.py`, then compare the result with [the active scanner](skills/openbound/scripts/inspect_public_candidate.py). Baseline material is a regression fixture, not a second active implementation.

Eleven original scanner test scenarios were retained, with installation-path and stricter output-boundary expectations adjusted. Added regressions exercise metadata, shallow history, LFS, coverage, identity and execution boundaries. OpenBound extends the scanner rather than claiming a new complete secret-scanning product.

The projector, verification runner, synthetic scenarios and OpenBound method organization are additional engineering work. Method references are optional and create no runtime dependency or permission grant. No assumption of common licensing follows from conceptual reuse.

Fixtures are synthetic. Their names, domains, paths and token shapes are test inputs, not evidence of real private projects being published. Historical Agent observations are separated from deterministic tests in [validation](docs/validation.md). Private discussions, handoffs and execution traces are excluded.

ZIP manifests verify payload bytes only; they do not establish authorship, rights or safety. See [license status](LICENSE-STATUS.md).
