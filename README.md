# OpenBound

English | [简体中文](README.zh-CN.md)

**Make a public version of your private project, component or research idea that other people can use, understand and build on.**

OpenBound is a Skill for your existing agent. You still ask in ordinary language. It gives the agent a reusable method and local tools for choosing what to publish, adapting it to a public audience, checking the result and completing authorized delivery. The output can be a complete project, an independent component or a research blueprint.

## Why use a Skill instead of asking the agent directly?

You can ask directly. A capable agent with a sufficiently complete prompt may do the same work. OpenBound packages that process so you can inspect, reuse and maintain it across tasks. It combines instructions for the agent's judgment with programs for the parts that can be checked mechanically.

Removing private information is one part of making a public work:

| Question | What OpenBound asks the agent to finish |
| --- | --- |
| What should become public? | Choose the whole project, a useful component or an explanation, with explicit promises and limits. Full source can carry no maintenance commitment; an unfinished idea can become a blueprint. |
| Will it work away from the author's machine? | Replace private dependencies with a usable interface or public alternative, provide appropriate examples and check the public entry point from the candidate itself. |
| Did the transformation preserve what matters? | Keep mature behavior, tests, documentation, licenses and CI; check that synthetic examples still demonstrate the mechanism and that research claims retain their evidence and counterexamples. |
| What is actually being delivered? | Inspect the selected files and Git surfaces, bind checks to that version, complete authorized delivery and preserve public contributions during later updates. |

The bundled tools can materialize an explicit selection without overwriting unknown output, inspect selected worktree/index/history surfaces and invalidate verification evidence when its inputs change. They do not decide what is worth publishing or certify safety. If you only need a small text redaction or an ordinary public README correction, that usually stays in your normal workflow.

## A concrete example: share a private pagination helper

The repository's [synthetic extraction scenario](tools/run_scenarios.py) starts with a helper that imports a private service client. Its useful behavior is collecting all pages, in order. Hiding the endpoint would leave the reader without that service client.

The prepared public work contains:

- `pager.py`: a small `collect(fetch_batch, limit=8)` interface; the caller supplies the client.
- `README.md`, a local `witness.py`, tests and the retained fixture license: a reader can run it without the author's private service.
- A mechanism check: 37 synthetic records with a page limit of 8. Complete traversal returns 37; an intentionally incomplete first-page reader returns 8. Shrinking the example to 5 records erases that distinction, and the witness rejects it.

Inspect the generated work without installing a Skill or calling a model. With Python 3.10+, Git and POSIX available, run from a reviewed checkout:

```bash
run_root="$(python3 -c 'from pathlib import Path; import tempfile; print(Path(tempfile.mkdtemp(prefix="openbound-")).resolve())')"
TMPDIR="$run_root" python3 -B tools/run_scenarios.py --workdir "$run_root/scenarios"
```

Open `$run_root/scenarios/B/public-candidate/README.md` for the component and `$run_root/scenarios/C/public-candidate/README.md` for a research blueprint developed from unfinished notes. All four scenarios are generated in the temporary directory, with private working records kept beside their candidates. The script constructs these works deterministically; it does not demonstrate an agent choosing the right method. There is no controlled result here showing that OpenBound outperforms a direct prompt; see [evidence and limits](docs/validation.md).

## What can you bring?

| Your starting point | What OpenBound helps you deliver |
| --- | --- |
| A finished project with personal configuration or development history | A complete public candidate with working setup instructions, appropriate examples and verified behavior |
| A useful component inside a private system | An independently usable component with explicit dependencies, provenance and meaningful tests |
| Experimental notes, a method or an unfinished idea | A coherent public work that explains the mechanism, evidence, open questions and ways to challenge it |
| An existing public work that is changing | An updated candidate that preserves public contributions and respects the relationship with private source |

These uses can combine. The methods expand around the work's actual needs, without requiring every project to follow the same checklist.

## Get started

Clone this repository, review the selected revision, then install the complete
Skill into an existing project where your Agent works:

```bash
git clone https://github.com/IndelibleVivi/openbound.git
cd openbound
python3 -B tools/host_support.py install --host claude-code --root /absolute/work-project
python3 -B tools/host_support.py doctor --host claude-code --root /absolute/work-project
```

Select `codex`, `claude-code`, `opencode`, `pi`, `gemini-cli` or `cursor`. These are thin installation profiles over one canonical payload. See [installation](docs/installation.md) for reviewed refs, updates and native invocation, and [Host compatibility](docs/host-compatibility.md) for permissions and fallbacks. The complete unit is [skills/openbound](skills/openbound/SKILL.md).

In a compatible Agent Skills host, request:

```text
Use OpenBound to prepare this completed private project as a complete public candidate.
Preserve its behavior, tests, and documentation. Address private configuration and the
history that will actually be exposed. Verify the candidate and complete authorized delivery.
```

Methods load when a concrete uncertainty requires them. Ordinary development or a small public README repair without a private boundary stays in the normal workflow. Optional editing and engineering methods are not runtime dependencies.

## Local tools

![OpenBound architecture](docs/architecture.png)

See the [editable architecture and exports](docs/architecture.md). The agent owns the complete work; the three tools handle specific mechanical checks.

| Tool | Purpose | Evidence limit |
| --- | --- | --- |
| `project_candidate.py` | Explicit selection and exact replacements into a new isolated candidate; receipts and recovery | Protects source and refuses drift; does not judge meaning or grant permission |
| `inspect_public_candidate.py` | Selected worktree, index, ref, history and metadata inspection | Reports rules and coverage gaps; LFS pointers do not cover payloads; no safety certification |
| `verify_public_work.py` | Reviewed checks in disposable copies, mechanism witnesses and reusable evidence | Minimal environment and bounded output; no OS or network sandbox |

```bash
python3 skills/openbound/scripts/project_candidate.py inventory --source /absolute/source
```

Inventory proposes tracked files for review. Read the [tool contracts](skills/openbound/references/continuation-and-tools.md) and [examples](examples/) before materializing or executing checks. A projection plan should include everything needed for the public candidate's promised use.

## Development and evidence

Python 3.10+, Git and POSIX are required. Windows is unsupported. Tools refuse symlinks, special files and symlink ancestors; resolve macOS temporary aliases to real paths. Clone `https://github.com/IndelibleVivi/openbound.git`, enter the checkout and run `python3 -B tools/validate.py`. This provider-neutral gate checks structure and links, all unittest scenarios, and three CLI entry points from a relocated complete Skill. Optional authoring validation: `skill-validate skills/openbound`.

[Validation](docs/validation.md) separates deterministic tests, native Host inventory, source-directed Agent tasks and unverified activation layers. [Executable Host trials](evals/host-trials.md) prepare A/B/C/D tasks, a negative-trigger case, controls and continuation checks. Tests do not establish reader comprehension or real research effects.

For a source ZIP, review and stage the intended files, then run `python3 -B tools/package.py --output /absolute/outside-repository/openbound-source.zip`. Packaging selects tracked allowed files, preserves modes and writes the manifest only inside the ZIP. After extraction run `python3 -B tools/check_package.py --manifest`.

## Boundaries and rights

Keep original private material, selection plans, reports and receipts private. Scanning cannot establish all semantic, binary, media, LFS, cumulative-disclosure or third-party-rights properties. Executing project checks requires appropriate authorization and host isolation. External contributions are untrusted input.

**No general public license is granted.** Source visibility is not an OSI open-source claim. MIT notices in synthetic fixtures apply only to those fixtures. Read [license status](LICENSE-STATUS.md) and [provenance](PROVENANCE.md).

- [Engineering design](ENGINEERING_DESIGN.md): ownership, protocols, recovery and limits.
- [Acceptance](evals/ACCEPTANCE.md): deterministic checks, Agent behavior and host activation.
- [Contributor contract](AGENTS.md): canonical paths, privacy and verification.
