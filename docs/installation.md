# Install and use OpenBound

Install the complete `skills/openbound/` directory from a reviewed source revision.
Its one `SKILL.md`, seven references, three Python tools and optional
`agents/openai.yaml` travel together. No other Skill is required. Read
[license status](../LICENSE-STATUS.md) before reuse.

The deterministic tools require Python 3.10+, Git and Linux/macOS POSIX behavior.
Native Windows execution is unsupported. A Host running on Windows may use a
Linux/WSL execution environment; record that environment separately.

## Install a reviewed local copy

From an existing OpenBound checkout, run:

```bash
python3 -B tools/host_support.py install --host claude-code --root /absolute/work-project
python3 -B tools/host_support.py doctor --host claude-code --root /absolute/work-project
```

Replace `claude-code` with `codex`, `opencode`, `pi`, `gemini-cli` or `cursor`.
`--root` must be an existing real directory. It is the project where the Host will
work, not the OpenBound Skill source directory. Run from any cwd by using the
absolute path to `tools/host_support.py`.

| Host selection | Default project destination | Default user destination relative to the explicit user root |
| --- | --- | --- |
| `claude-code` | `.claude/skills/openbound` | `.claude/skills/openbound` |
| `codex`, `opencode`, `pi`, `gemini-cli`, `cursor` | `.agents/skills/openbound` | `.agents/skills/openbound` |

The shared path is documented by those five Hosts. Installing for another Host
into the same shared directory reuses an identical payload. It does not create
another authored Skill. Claude uses its native path. Hosts that discover both
locations can see duplicate names; keep one selected installation visible for a
trial and use `doctor` to spot copies under the supplied root.

User installation is explicit:

```bash
python3 -B tools/host_support.py install --host pi --scope user --root /absolute/user-directory
```

The root must be the user root that the selected Host actually reads, or a root
selected through that Host's documented configuration. This option only chooses
where to install; it does not configure native discovery. An arbitrary directory
does not automatically become a discovered user scope. The isolated Gemini
observation used its documented `GEMINI_CLI_HOME` setting.

There is no implicit HOME write. `--destination /absolute/path/openbound` overrides
the profile; an outside-root parent must already exist. `--dry-run` prints the
proposed installation without writing. `--source` selects another reviewed
complete Skill directory. Ordinary installs use the canonical source alongside
the helper.

The canonical payload includes `agents/openai.yaml`, and the installer preserves
it on every Host. A reviewed custom source may omit this optional metadata;
parity is always measured against the selected source. Removing it from a copy
installed from the canonical source is drift and is reported as such.

The installer reuses the existing projector for bounded reads and atomic,
no-overwrite publication. It preserves existing discovery-directory modes,
refuses links and incomplete units, and accepts a repeat only after exact file
bytes/modes and normalized installed root/directory modes match. Directory-mode
drift is reported, never silently repaired. It does not change settings,
credentials, trust, tool grants,
MCP servers or model configuration. An interruption after publication can be
recovered by rerunning the same install: the complete matching directory is
recognized as unchanged. A partial or different directory is preserved for review.

## Verify the actual Host

`doctor` is read-only. It reports Python/platform/Git prerequisites, the selected
copy and alternate locations under the supplied root, and executable names found
on PATH. It does not execute them, identify a generic `agent` binary as Cursor,
enumerate every user/admin/remote installation, or assert effective permission.
Its discovery, activation and task-completion fields remain `not_run`.

Use the actual Host inventory, then a new fixture session:

| Host | Explicit route | Native observation / refresh |
| --- | --- | --- |
| Codex | `$openbound`, or `/skills` selection | Confirm selected path/version; Codex normally detects local changes |
| Claude Code | `/openbound` | Confirm command and selected directory; do not use a mode that disables Skill discovery |
| OpenCode 1.x | Ask to load `openbound` with the `skill` tool | `opencode debug skill` lists available skills |
| pi | `/skill:openbound` | `/reload`; project trust can affect project resource loading |
| Gemini CLI | Ask to activate `openbound` with `activate_skill` | `gemini skills list --all`, then `/skills reload`; activation may require consent |
| Cursor | `/` menu, select `openbound` | Confirm the actual local/SSH/cloud runtime has the complete payload |

OpenCode 1.x and Gemini do not have a universally established `/openbound`
command. OpenCode v2 documents a different `skill({id})` and `@skill-id` interface;
use the installed version's documented route. Native inventory exit status alone
is insufficient: require the exact name and expected path. For example, a
successful command may skip an untrusted project's Skill.

Start with this task, using the explicit route above:

```text
Use OpenBound to prepare this completed private project as a complete public candidate.
Preserve its behavior, tests and documentation. Address private configuration and the
history that will actually be exposed. Verify the candidate and complete authorized delivery.
```

Test natural discovery in a separate fresh session with an ordinary task that
does not name OpenBound or point to its source. A direct file-read fallback is
useful, but its evidence is `source-directed`, not native discovery or implicit
activation. See [compatibility](host-compatibility.md) and
[executable host trials](../evals/host-trials.md).

## Updates, collisions and recovery

Keep source authoritative. Compare the installed copy with the reviewed source
using `doctor` before an update. A differing directory may contain local work;
the installer intentionally has no force-overwrite option. Preserve that copy
outside active discovery locations, review its changes, then select a new clean
destination or carry out the Host's supported update procedure. Do not move
unknown directories automatically.

Record source revision/payload digest and the actually selected runtime path.
After an update, verify new instruction delivery in a fresh session; existing
conversation content may retain the old body. Recover ongoing work from its
private task record and candidate/receipt identities, with the next unfinished
action and original authorization intact. A Host session ID is an optional local
locator, not a cross-Host state protocol.

## Other native installation routes

Codex's bundled `$skill-installer` can install
`IndelibleVivi/openbound`, path `skills/openbound`, at a reviewed ref. Its exact
installation scope depends on the installed Codex version.

Gemini also documents installation from the canonical repository:

```bash
gemini skills install https://github.com/IndelibleVivi/openbound --path skills/openbound --scope workspace
```

Follow normal consent and trust prompts. A local copy supports inspection without
requiring a network installer, symlink semantics or the source checkout at runtime.

## Source gate

```bash
python3 -B tools/validate.py
```

This runs the provider-neutral structural checks, deterministic regressions,
six installation profiles and relocated real tool operations. It does not call a
model. Hosted CI invokes the same entry. Current observations and unrun layers
are recorded separately in [validation](validation.md).
