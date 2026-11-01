# Host compatibility: contracts and evidence

Documentation checked 2026-11-01. Host names identify products; versions, trust,
extensions, permissions and execution surfaces determine the actual runtime.
The table describes documented routes. Observations belong in
[validation](validation.md), independently of this support contract.

## One portable core

| Layer | Owner and contract |
| --- | --- |
| Portable core | `skills/openbound/SKILL.md`, seven conditional methods, three standalone stdlib tools; public object/promises, transformation, privacy scope, verification, delivery semantics |
| Host integration | Native discovery directory and invocation, file/tool interfaces, cwd, sandbox/trust, optional UI metadata and native session continuation |
| Local support | `tools/host_support.py` copies the canonical unit and reports filesystem prerequisites; it does not launch Hosts or alter their policies |
| Behavioral evidence | `tools/host_trials.py` prepares comparable tasks and assesses artifacts; human/trace evidence separately records actual Host behavior |

Native tool names can differ. Resolve resources from the delivered Skill location;
pass explicit source/candidate/state paths to the Python tools. The Host can
provide a local shell, sandbox shell or equivalent file/execute interface. Source
changes precede installation changes. No host-specific body, common tool RPC
protocol, launcher framework or permission emulation is introduced.

## Documented native differences

| Host | Discovery and explicit use | Runtime consequence |
| --- | --- | --- |
| Codex | Repo/ancestor and user `.agents/skills`; `$openbound` or `/skills`; metadata first, body on demand | `agents/openai.yaml` is optional Codex metadata. A local Skill does not set sandbox, network or approval policy; Desktop, CLI and cloud observations stay distinct. |
| Claude Code | `.claude/skills` in project/user scope; `/openbound`; optional additional dirs/plugins | `allowed-tools` can preapprove tools for the invoking turn. Keep it out of the portable body. `--bare`/safe modes can suppress ordinary discovery. A loaded body can persist after files change. |
| OpenCode 1.x | `.opencode/skills`, `.agents/skills`, Claude-compatible paths; native `skill({name})` tool | Skill allow/ask/deny and read/edit/bash/external-directory policies are separate. A denied Skill is hidden from the agent's available-skill list; CLI discovery and effective agent permissions remain separate observations. Last matching permission rules matter. |
| pi | `.pi/skills`, `.agents/skills`, user/package paths; `/skill:openbound`, explicit `--skill` | Project trust can skip project resources in noninteractive modes. Tools use process permissions; cwd does not confine them. Do not treat project trust as a runtime sandbox. |
| Gemini CLI | `.gemini/skills`, `.agents/skills`, user/extensions; `activate_skill` | Project trust and activation consent are distinct. Activation exposes Skill resources; shell/network rights remain governed by policy. Inventory may exit successfully while excluding an untrusted project. |
| Cursor | `.cursor/skills`, `.agents/skills`, compatibility paths; `/` Skill selection | Local user copies do not automatically move into SSH/cloud/self-hosted sessions. Check the actual runtime. `agent` on PATH is only a candidate executable until identified. |

OpenCode v2 has a separate documented `skill({id})`/`@skill-id` interface and
selection metadata. A v1 run establishes no v2 compatibility. Keep the exact
version and selected Skill path in each observation.

Primary references:

- [Codex Skill discovery](https://learn.chatgpt.com/docs/build-skills),
  [Codex security index](https://learn.chatgpt.com/docs/security).
- [Claude Code Skills](https://code.claude.com/docs/en/skills),
  [permissions](https://code.claude.com/docs/en/permissions),
  [headless operation](https://code.claude.com/docs/en/headless).
- [OpenCode Skills](https://opencode.ai/docs/skills/),
  [v2 Skills](https://opencode.ai/v2/docs/skills),
  [permissions](https://opencode.ai/docs/permissions/),
  [CLI discovery commands](https://opencode.ai/docs/cli/).
- [pi Skills](https://pi.dev/docs/latest/skills),
  [security and trust](https://pi.dev/docs/latest/security),
  [CLI](https://pi.dev/docs/latest/cli).
- [Gemini CLI Skills](https://geminicli.com/docs/cli/skills/),
  [trusted folders](https://geminicli.com/docs/cli/trusted-folders/),
  [policy engine](https://geminicli.com/docs/reference/policy-engine/).
- [Cursor Skills](https://cursor.com/docs/skills),
  [CLI permissions](https://cursor.com/docs/cli/reference/permissions),
  [parameters](https://cursor.com/docs/cli/reference/parameters).

Check installed-version help and permission documentation before using automation
flags. Executable discovery does not establish effective read-only permissions.
No installer enables bypass flags or changes trust to make a test pass.

## Capability failures preserve the task

| Missing/blocked capability | Continue with | Report precisely |
| --- | --- | --- |
| Native Skill discovery | Explicit canonical `SKILL.md` read plus its referenced resources | Source-directed loading; native discovery unverified |
| Ordinary file access to Skill resources | Host's allowed read/import route or a complete local copy in an authorized area | Exact missing resource/path; do not synthesize unread method contents |
| Shell/Python/Git | Complete available edits and reviewable candidate; prepare exact verification commands | Checks unrun, not passed; identify execution environment needed |
| Network / publication connector | Finish local conversion, facilities and verification | Local candidate complete; remote action pending or blocked |
| Diagram renderer / image inspection | Deliver editable factual diagram source and text equivalent | Distinguish syntax check, actual render and visual review |
| Native session continuation | Reopen private task record, source revision, candidate and evidence | Revalidate stale identities; resume the unfinished action |
| Requested external action lacks authorization | Finish independent local work and ask for the specific remaining action | Existing grants persist; a method switch introduces no new grant |

A fallback has a reduced evidence claim, not a silently reduced objective.
Do not force every Host to emulate another's tool or interaction model.

## Evidence levels

1. **Format/structure:** a valid package and resolvable relative resources.
2. **Tool execution:** actual projector/inspector/verifier operations in the named OS/runtime.
3. **Installed bytes:** exact complete payload at the selected location.
4. **Native discovery:** real Host inventory/trace identifies that name and path.
5. **Invocation/activation:** explicit and implicit cases have separate fresh sessions.
6. **Method use:** the required reference changes the relevant action; record redundant loads.
7. **Outcome:** candidate behavior, preserved functionality, source protection, usable facilities and authorization evidence.
8. **Benefit:** controlled same-task/Host/model comparisons; report quality and overhead together.

Passing one level never implies the next. Missing tokens/trace/runtime evidence
stays unknown. A Subject's report is attributed testimony until supported by
artifact or trace observations. A fixture cannot certify arbitrary public safety,
reader comprehension or productive deployment.

## Publication and facilities

The three runtime tools intentionally have no remote publication command. Use the
Host's native Git, forge connector or release/deployment interface for the exact
authorized action. Inspect the final commit/tag/assets actually sent and observe
the remote result. Retry only after checking whether an interrupted action
already completed. Git availability does not imply credentials or push rights.

README, architecture diagrams, CI and contribution instructions remain selected
by reader needs in `reader-and-facilities.md`. The core does not create a mandatory
facility bundle. Existing gates and license/provenance are preserved; a Blueprint
can complete without executable checks or a software-release claim.
