# OpenBound engineering contract

## Authority

This repository is the independent canonical OpenBound source, with its own public history. Preserve attribution and rights for reused Public Repo Craft material. The sole
active authored Skill is `skills/openbound/`; do not restore the retired root
`SKILL.md`, root `agents/`, old reference tree, or a second scanner implementation.
The original scanner in `provenance/baseline/` is a regression fixture only.

An installed Skill is derived state. Change and verify source here first. Source,
commit, push, installation, discovery and named-host activation are
separate states. See `docs/current-state.md` and `docs/migration.md` before an
installation or migration; do not hot-edit an installed copy.

## Source owners

| Path | Authority |
| --- | --- |
| `skills/openbound/SKILL.md` | Trigger, complete outcome, direct mature path, method selection |
| `skills/openbound/references/` | Conditional methods and tool contract |
| `skills/openbound/scripts/` | One canonical projector, inspector and verification engine |
| `tests/`, `tools/fixture_factory.py`, `tools/run_scenarios.py` | Synthetic behavioral checks and deterministic scenarios |
| `evals/` | Task prompts and evaluator-only reviews; never give both to a subject |
| `tools/validate.py` | Provider-neutral verification owner; CI invokes this entry |
| `docs/architecture-model.json` | Editable diagram model; renderer generates SVG and Excalidraw |
| `README.md`, `ENGINEERING_DESIGN.md` | Supported use and design/protocol contracts |
| `docs/current-state.md`, `docs/validation.md` | Volatile delivery facts and bounded observed evidence |

Preserve existing mature work. Methods are selected by concrete unresolved facts,
not a mandatory A/B/C/D pipeline. Skills are instructions, not permission tokens
or isolation enforcement. Keep external contributions untrusted until reviewed.

## Privacy and external boundaries

Publication, license grants, deployment, installation and account changes require their own authorization. Passing tests does not authorize them.

Keep raw discussions, personal handoffs, private working continuity, live eval
traces, projection plans and receipts outside this repository.
Track only intentionally shareable engineering docs and synthetic test sources.
Do not import the original package's `CODEX_HANDOFF.md` or `validation/` dump.
Inspect exact staged paths; never use catch-all staging. Packaging must not collect
untracked/ignored material or write a manifest back into the source worktree.

Retain existing rights and provenance; there is no public license grant for the
OpenBound source. Synthetic fixture licenses apply only to their fixtures.

## Verification and closure

```bash
python3 -B tools/validate.py
skill-validate skills/openbound
git diff --check
```

The first command is the CI gate and supplies a real temporary directory on POSIX.
Do not relax source/target no-follow guards to accommodate symlinked temp aliases.
Test state transitions, refusal and source protection for projector/verification
changes. Scanner changes retain baseline metadata/shallow/LFS counterexamples.
The historical baseline patch need not match future repaired scanner bytes; if
the scanner changes, update its patch and provenance deliberately.
Unified diff context contains significant single-space blank lines; the scoped
`.gitattributes` rule preserves that patch syntax without relaxing source checks.

Real model evaluations need their own explicit scope/authorization. Deterministic
fixtures, prior reported Agent trials, source-directed trials, installed discovery,
implicit activation and human comprehension must never be reported as equivalent.

Update README for changed usage/support/privacy; AGENTS for canonical paths and
gates; current-state for source/installation/remote status; migration for install
steps; validation for new observations; design and reference contracts for schema
or behavior changes. Keep private continuity outside tracked docs. When changing
the diagram, regenerate SVG/Excalidraw and PNG, inspect the actual render and keep
the model and exports aligned. Do not claim a source change is released.
