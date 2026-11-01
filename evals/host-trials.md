# Running cross-harness trials

`tools/host_trials.py` prepares real synthetic task inputs and checks the resulting
files. It does not launch a model, install OpenBound, alter permissions, publish
anything, or conclude that a host has passed. Use the complete canonical Skill
and the host's native integration described in [installation](../docs/installation.md).

The tool depends on Python 3.10+, Git and POSIX, just like the existing tools.
Run it from a reviewed OpenBound checkout. Trial roots must be new directories
outside that checkout; their existing parent and all path components must be real
directories. Resolve macOS temporary aliases before supplying paths. Run data,
raw traces and evaluator records remain private and must not enter a public
candidate or a commit to this repository.

## Separate the observations

| Observation | Required evidence | What it does not establish |
| --- | --- | --- |
| Tool execution | Relocated installed-unit tool results with runtime version | Host discovery or agent task completion |
| Native discovery | Host's skill list/catalog or activation trace naming the actual installed unit | Explicit or implicit use during a task |
| Explicit invocation | Fresh-session transcript showing a supported native invocation and activation | Natural discovery |
| Implicit activation | Unnamed original task in a clean session plus activation trace | Outcome quality or value |
| Method loading | Reference-read trace, why each method was needed, continuation after loading | Merely loading all references is not useful behavior |
| End-to-end outcome | Actual candidate identity, independent functional/semantic review and trace | Files existing do not establish complete work |
| Authorization | Reviewed command/event trace and observed external state where applicable | A source snapshot cannot detect all external side effects |
| Recovery | Before/after candidate identity, resumed trace and preserved reader changes | A generated continuation prompt is not recovery execution |

The `assess` command separates locally observed facts from operator-reported
trace claims. `observed` is an observation label, not an acceptance score. A trace
file's hash binds the cited bytes; an independent reviewer must still inspect
their meaning. There is deliberately no aggregate compatibility pass flag.

## Prepare an uncontaminated task

For each condition, create a new trial. Never reuse a candidate or session from
another condition. `--host` records the operator's host label; it does not imply
that its binary or account is available.

```sh
python3 -B tools/host_trials.py prepare \
  --workdir /absolute/private/claude-A-explicit \
  --case A --mode explicit --host claude-code --invocation /openbound

python3 -B tools/host_trials.py prepare \
  --workdir /absolute/private/codex-A-explicit \
  --case A --mode explicit --host codex --invocation 'Use $openbound.'
```

These commands only prepare trials. They are not evidence of Claude Code or
Codex execution. The invocation examples use the hosts' documented native forms;
use the current installation guide for other hosts rather than assuming that
every host accepts `/openbound`.

Each trial contains two sibling directories:

- `subject/`: original task prompt, synthetic inputs, candidate destination and
  private working-state directory. A source-directed trial also gets one complete
  copy of `skills/openbound` in `subject/resources/openbound`.
- `evaluator/`: protected input snapshots, fixture/prompt/Skill identities and an
  observation template. Do not supply this directory to the subject agent.

Folder placement is **not an access-control boundary**. Restrict the subject's
filesystem/tool access to `subject/` and its approved installed Skill. Keep the
OpenBound checkout, review files, evaluator directory and other trial results out
of its mounted workspace and prompt. If the host cannot enforce this restriction,
record that contamination risk and inspect the trace for accidental access.

### Modes

| Mode | Prompt and setup |
| --- | --- |
| `source-directed` | Names the copied canonical Skill by its absolute path. Isolates behavior after instruction delivery; does not test native discovery. |
| `explicit` | Prepends exactly the operator-supplied native invocation. Install using the host's supported scope before running. |
| `implicit` | Original task only; no OpenBound name, invocation or Skill-path cue in the prompt. Install one entry and use a clean session. |
| `control` | Same original task and fixture, with OpenBound absent/disabled in all discovery scopes. Use an otherwise identical host/model/permission setup. |

The tool refuses an explicit trial without invocation text. It does not infer
native commands. In `implicit` and `control` modes it copies no Skill into the
subject workspace. Compare `fixture_content_sha256` and `task_template_sha256`
across conditions; raw prompt hashes differ because absolute paths differ.
Installation, global skills, cached sessions, model, version, tool permissions and
budgets are additional control variables and must be recorded by the operator.

## Cases and independent assessment

Use `--case A`, `B`, `C`, `D` or `N9`. The existing
[acceptance protocol](ACCEPTANCE.md) and evaluator-only `*.review.md` files remain
the semantic authority; do not give them to the subject.

| Case | Prepared task | Automated checks | Additional review |
| --- | --- | --- | --- |
| A | Mature decimal CLI, ignored private config, local private-path repairs and synthetic removed-file Git history | Source protection, required mature artifacts present, existing license retained, selected private sentinels; optional original tests and explicit public example in a disposable copy | Actual delivered history, CLI error paths, documented default/env/explicit precedence and installed use, README usability, justified mature asset changes and unnecessary method overhead |
| B | Pagination code coupled to a private client | Source protection, candidate/README presence, selected private file/sentinel exclusion | Chosen independent interface, 37/8 mechanism, callback errors, clean-root execution, provenance and meaningful tests |
| C | Unfinished notes with an author-reported observation and ID-replacement counterexample | Source protection, candidate/README presence, selected private file/sentinel exclusion | Complete readable work, hypothesis/observation boundaries, counterexample, attribution and falsification design |
| D | New private Unicode behavior plus a real prior projection receipt and a public reader correction | Both source roots protected, public artifacts present and license retained; optional public tests and Unicode behavior | Reconcile old receipt drift, preserve public reader corrections/provenance through edits, review untrusted contribution text and future maintenance choice |
| N9 | Small public README link repair | Existing other files unchanged and actual link repaired | No unnecessary OpenBound activation or first-publication ceremony |

`N9` only permits `implicit` or `control`: explicitly requesting OpenBound would
invalidate a negative discovery test. The A history seed is synthetic; current
text checks do not establish that all history is safe. The tool intentionally
does not invent one fixed interface for every valid B extraction or score C prose
by a list of mandatory keywords. Those cases need actual independent review.

Fixture Git commits disable automatic maintenance and GC for that invocation,
so background housekeeping cannot race the recorded input snapshot. Operator
Git configuration is not changed.

The source snapshot covers all ordinary source files and Git state except Git's
index storage bytes and reflogs. New trials separately bind the semantic index
(`ls-files --stage -z`: paths, modes, blob IDs and stages) using the existing
inspector's protected Git invocation. A stat-cache refresh remains acceptable;
staging an existing blob under another path is detected even when worktree,
objects and refs do not change. Index state is checked before and after optional
candidate execution. Older trial records without that baseline report this
surface as `not_observed`; their source-preservation claim excludes it.
Symlinks and unusual file types are refused by the existing snapshot engine.
Paths containing lexical `..` are refused before normalization, so an alias cannot
disappear behind a parent traversal.

Candidate identity uses the verification engine's exact snapshot, including Git
index storage and reflogs. This same identity binds assessments, operator outcome
observations, checkpoints and post-execution comparisons. Candidate-only staging
invalidates old observations and recovery identity; even a benign candidate index
refresh selects a new fixed-check receipt instead of colliding with stale evidence.
The source-only stat-cache tolerance does not apply to the delivered candidate.
README presence requires an ordinary file, not a directory with the same name;
readability and completeness still need independent review.

`baseline_file_changes` records baseline/current hashes and `unchanged`, `changed`
or `missing` for A's mature assets and D's public files. Changed bytes require
independent review; they do not automatically fail the trial. A necessary packaging
fix or a guide adaptation may preserve the mature work and its reader correction.
Required artifact removal and replacement of the existing fixture license remain
hard failures. The evaluator must judge the justification and semantic preservation
of other changes; byte parity alone cannot settle that decision.

Start the selected host in `subject/`, with the intended integration and bounded
permissions. Send `subject/prompt.md`. Let the agent finish the public work, then
inspect the candidate and capture its transcript privately.

```sh
python3 -B tools/host_trials.py assess \
  --record /absolute/private/claude-A-explicit/evaluator/trial.json \
  --output /absolute/private/claude-A-explicit/evaluator/assessment.json
```

Without `--execute-reviewed`, assessment is read-only and executes no candidate
code. Exit 1 means a deterministic fact failed (a missing candidate also fails);
exit 2 means invalid input or an execution error. Exit 0 means only the named,
limited deterministic checks passed. All unobserved host stages remain
`not_observed`, and missing metrics remain `null`. Assessment/checkpoint/resume
JSON outputs must be new files directly in `evaluator/`; continuation Markdown
must be a new file directly in `subject/`. These paths are checked before any
optional candidate execution.

After reviewing the candidate code and arranging appropriate host isolation,
optionally add `--execute-reviewed` for the fixed A/D checks. They reuse
`verify_public_work.py` and disposable candidate copies; no commands from an
observation file or agent receipt are executed. The flag is not an OS/network
sandbox. B/C have no fixed executable contract; prepare and review their actual
public-use commands separately using the ordinary verification tool.

A's fixed checks do not impose one no-argument default: a documented portable
local default may legitimately require the reader to create an input file.
Independently test the chosen default, environment override, explicit argument
precedence and installed use against the delivered README. These are required
review items; passing the explicit example alone does not verify them.

Fixed-check evidence names bind the candidate, reviewed contract, evaluator,
verification engine and scanner identities. A legitimate evaluator revision
creates a distinct contract/receipt pair for the same candidate and preserves
prior evidence. Modification of the selected identity's contract is still refused.

## Trace evidence and overhead

Copy `observations.template.json` to an evaluator-owned `observations.json` and
fill only what was observed. Record host/version/model, the prompt identity and
the assessed candidate identity. For example, the following **illustrates the
schema only** and is not a report of a real run:

```json
{
  "schema": "openbound-host-observation/1",
  "prompt_sha256": "copy the exact trial value",
  "host": "claude-code",
  "host_version": "record the actual version",
  "model": "record the actual model",
  "candidate_sha256": "copy the current assessment value",
  "stages": {
    "discovery": {
      "status": "observed",
      "evidence": [
        {"path": "/absolute/private/trace.txt", "note": "Location and event that show native discovery."}
      ]
    }
  },
  "metrics": {"elapsed_seconds": 240, "tool_calls": 18, "repeated_reads": 1},
  "reference_reads": ["privacy-and-history.md", "continuation-and-tools.md"],
  "semantic_review": "not_observed"
}
```

Permitted stage states are `observed`, `failed`, `unavailable`, `not_observed`.
Observed/failed stages require evidence-file references and explanatory notes.
End-to-end/recovery observations require the current candidate identity; changed
candidate evidence is refused. Every stage remains explicitly operator-reported.
Supported optional measures are elapsed seconds, input/output tokens, model/tool
calls, scan count, new questions, repeated reads and method-load count. Preserve
the chronological `reference_reads` list, including repeats.

```sh
python3 -B tools/host_trials.py assess \
  --record /absolute/private/claude-A-explicit/evaluator/trial.json \
  --observations /absolute/private/claude-A-explicit/evaluator/observations.json \
  --output /absolute/private/claude-A-explicit/evaluator/reviewed-assessment.json
```

Compare benefit and cost within the same host/model/version, fixture, permission
and budget conditions. Use artifact quality and boundary failures alongside
elapsed/token/tool overhead. Reading more methods is useful only when it improves
the delivered work or resolves a concrete problem. One successful trial cannot
support a general performance claim. Repeat only to resolve a specific uncertainty
or required acceptance condition; do not create an unbounded benchmark campaign.

## Interrupted work and changed-candidate recovery

Before interrupting a real task, record the current candidate. This creates no
host observation:

```sh
python3 -B tools/host_trials.py checkpoint \
  --record /absolute/private/claude-A-explicit/evaluator/trial.json \
  --output /absolute/private/claude-A-explicit/evaluator/checkpoint.json
```

As the operator, add a synthetic reader correction or another relevant candidate
change after interruption. Keep the exact change and expected response in the
evaluator directory. Generate a continuation prompt:

```sh
python3 -B tools/host_trials.py resume \
  --record /absolute/private/claude-A-explicit/evaluator/trial.json \
  --checkpoint /absolute/private/claude-A-explicit/evaluator/checkpoint.json \
  --prompt-output /absolute/private/claude-A-explicit/subject/resume.md \
  --output /absolute/private/claude-A-explicit/evaluator/resume-observation.json
```

Only send `subject/resume.md` to the resumed/fresh host session. It preserves the
original scope and permissions without revealing the hidden change. The evaluator
records whether candidate identity changed; it does not infer that the host noticed
or handled it. Assess the resulting candidate again and independently review that
the correction survived, obsolete evidence was not reused, method switching did
not restart intake, and no unauthorized delivery was repeated.

## Minimum useful live run

Prioritize two actually available hosts. In each, record native discovery, run A
explicitly, run A implicitly in a new session, then N9 and one method-heavy task
(B, C or D). Include an A control and one changed-candidate recovery. If a host,
account, model, sandbox or trace is unavailable, record that stage and its concrete
next action. Do not substitute a file-format check for the missing behavior run.

The repository's unit tests exercise this preparation/assessment machinery and
its refusal cases. They do not run either named host or establish live activation.
